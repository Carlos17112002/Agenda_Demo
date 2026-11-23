# Inventario con objetos y archivos — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ampliar el inventario con objetos físicos (`Product.kind=asset`) y una biblioteca de documentos privados con vínculo opcional, gestionable desde Flutter —incluido offline— y visible en modo lectura desde la web.

**Architecture:** Se extiende el modelo `Product` existente con un discriminador `kind` y campos de objeto; los objetos no participan del ledger de stock. `Document` guarda metadatos y un archivo en almacenamiento privado fuera de `MEDIA_ROOT`. La API expone CRUD, foto, documentos, descarga autenticada y cuota. Flutter sincroniza metadatos, encola subidas persistentes y cachea descargas por empresa. La web solo lista y descarga. Todo se filtra por empresa en el servidor.

**Tech Stack:** Django 6 + DRF, SQLite (hasta la migración a PostgreSQL), Pillow, Flutter 3.13 + provider + sembast + file_picker + open_filex, React 18 + TanStack Query + Vitest/MSW.

**Spec:** `docs/superpowers/specs/2026-11-11-inventario-objetos-archivos-design.md`

## Global Constraints

- **Aislamiento por empresa:** ninguna empresa puede leer, modificar ni eliminar datos de otra. Toda consulta, descarga, subida y operación parte de `company=request.tenant` y de `X-Tenant-Context`. Un id ajeno responde `404`.
- La base de datos sigue siendo SQLite por ahora; más adelante se cambia a PostgreSQL. No se usan funciones exclusivas de PostgreSQL.
- Los binarios viven en `private-media/`, nunca en `media/`, porque en `DEBUG` `/media/` se sirve sin autenticación.
- Límites fijos: 50 MB por documento, 10 MB por foto, 5 GB por empresa.
- Los objetos (`kind=asset`) no generan stock, movimientos, compras, transferencias, conteos ni ventas.
- La interfaz de usuario está en español. Errores del servidor se muestran por campo cuando existan.
- **Commits:** Carlos no autorizó commits. Cada paso de commit requiere autorización explícita antes de ejecutarse.
- No se instalan dependencias globales. Flutter usa `flutter pub add`; la web usa `npm install` dentro de `web/`.
- Todas las pruebas backend se ejecutan con `DJANGO_TESTING=true` para desactivar el throttle.

---

## Estructura de archivos

```text
backend/
  config/settings.py                         PRIVATE_MEDIA_ROOT
  apps/inventory/
    storage.py                               storage privado y rutas UUID
    files.py                                 validación de formatos, tamaños y cuota
    models.py                                Product.kind/campos, Document
    serializers.py                           ProductSerializer, Document*, foto
    views.py                                 filtros, foto, documentos, descarga, cuota
    services.py                              guardas de stock
    admin.py                                 Product y Document
    migrations/0003_*.py                     campos de objeto
    migrations/0004_*.py                     Document
    tests/test_assets.py                     modelo, SKU, stock-only
    tests/test_documents_api.py              documentos, descarga, cuota
    tests/test_asset_photos.py               foto de objeto
  apps/mobile/
    sync.py                                  categories, suppliers, documents
    resources.py                             whitelist duplicada
    operations.py                            asset.create/update, document.delete
    tests/test_inventory_mobile.py           sync y operaciones
  apps/sales/
    services.py                              venta rechaza objetos
    tests/test_assets_guard.py               guarda unitaria

mobile/lib/
  data/api_client.dart                       getBytes + fields en multipart
  data/models.dart                           ProductRecord, DocumentRecord, UploadItem
  data/local_store.dart                      almacén de subidas
  data/file_store.dart                       rutas de uploads/downloads por empresa
  data/upload_queue.dart                     cola persistente de binarios
  data/app_state.dart                        getters, alta/edición, descarga, cuota
  screens/inventory_screen.dart              pestañas Objetos/Archivos/Stock
  widgets/asset_form_sheet.dart              formulario de objeto
  widgets/asset_detail_sheet.dart            detalle y documentos vinculados
  widgets/inventory_files_tab.dart           biblioteca de archivos
  test/inventory_assets_test.dart            modelos y estado
  test/inventory_files_test.dart             cola, caché y descarga

web/                                          ver Task 19A del plan web
```

---

### Task 1: Modelo de objeto y almacenamiento privado

**Files:**
- Create: `backend/apps/inventory/storage.py`
- Modify: `backend/apps/inventory/models.py:43-78`
- Modify: `backend/config/settings.py:70-74`
- Modify: `.gitignore`
- Create: `backend/apps/inventory/tests/test_assets.py`
- Migration: `backend/apps/inventory/migrations/0003_product_asset_fields.py` (generada)

**Interfaces:**
- Produces: `Product.Kind`, `Product.AssetStatus`, campos de objeto en `Product`, `private_storage`, `asset_photo_upload_path(instance, filename)`, `document_upload_path(instance, filename)`.
- Consumes: `Branch`, `Supplier`, `TenantScopedModel`, `settings.PRIVATE_MEDIA_ROOT`.

- [ ] **Step 1: Escribir la prueba que falla**

`backend/apps/inventory/tests/test_assets.py`:

```python
from decimal import Decimal

from django.test import TestCase

from apps.inventory.models import Product
from .utils import InventoryScenarioMixin


class ProductAssetModelTests(InventoryScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()

    def test_stock_is_the_default_kind(self):
        self.assertEqual(self.product.kind, Product.Kind.STOCK)
        self.assertEqual(self.product.status, Product.AssetStatus.AVAILABLE)
        self.assertEqual(self.product.quantity, 1)

    def test_asset_accepts_identification_location_and_purchase_fields(self):
        asset = Product.objects.create(
            company=self.company,
            kind=Product.Kind.ASSET,
            sku="ACT-MAQUINA",
            name="Máquina de corte",
            category=self.category,
            branch=self.branch,
            serial_number="SN-9988",
            internal_code="INT-01",
            quantity=2,
            purchase_date="2026-01-15",
            supplier=self.supplier,
            cost=Decimal("250000"),
            warranty_until="2027-01-15",
            notes="Incluye dos cuchillas.",
        )
        asset.refresh_from_db()
        self.assertEqual(asset.kind, Product.Kind.ASSET)
        self.assertEqual(asset.branch, self.branch)
        self.assertEqual(asset.supplier, self.supplier)
        self.assertEqual(asset.quantity, 2)
        self.assertEqual(str(asset.purchase_date), "2026-01-15")
```

- [ ] **Step 2: Ejecutar la prueba y verificar que falla**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test apps.inventory.tests.test_assets.ProductAssetModelTests -v 2
```

Expected: FAIL con `AttributeError: type object 'Product' has no attribute 'Kind'`.

- [ ] **Step 3: Crear el almacenamiento privado**

`backend/apps/inventory/storage.py`:

```python
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

private_storage = FileSystemStorage(
    location=settings.PRIVATE_MEDIA_ROOT,
    base_url=None,
)


def _suffix(filename):
    return Path(filename).suffix.lower()


def document_upload_path(instance, filename):
    return f"documents/{instance.company_id}/{uuid.uuid4().hex}{_suffix(filename)}"


def asset_photo_upload_path(instance, filename):
    return f"assets/{instance.company_id}/{uuid.uuid4().hex}{_suffix(filename)}"
```

En `backend/config/settings.py`, después de `MEDIA_ROOT`:

```python
PRIVATE_MEDIA_ROOT = Path(
    os.environ.get("AGENDA_PRIVATE_MEDIA_ROOT", BASE_DIR / "private-media")
)
```

En `.gitignore`, agregar:

```gitignore
backend/private-media/
```

- [ ] **Step 4: Extender `Product`**

En `backend/apps/inventory/models.py`, importar:

```python
from .storage import asset_photo_upload_path, private_storage
```

Dentro de `Product`, antes de `id`:

```python
    class Kind(models.TextChoices):
        STOCK = "stock", "Insumo con stock"
        ASSET = "asset", "Objeto"

    class AssetStatus(models.TextChoices):
        AVAILABLE = "available", "Disponible"
        ASSIGNED = "assigned", "Asignado"
        MAINTENANCE = "maintenance", "En mantenimiento"
        RETIRED = "retired", "Dado de baja"
```

Después de `active`:

```python
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.STOCK)
    status = models.CharField(
        max_length=12, choices=AssetStatus.choices, default=AssetStatus.AVAILABLE,
    )
    branch = models.ForeignKey(
        Branch, null=True, blank=True, on_delete=models.PROTECT,
        related_name="asset_products",
    )
    assigned_worker = models.ForeignKey(
        "workforce.WorkerProfile", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assigned_assets",
    )
    serial_number = models.CharField(max_length=120, blank=True)
    internal_code = models.CharField(max_length=64, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    purchase_date = models.DateField(null=True, blank=True)
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assets",
    )
    warranty_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    photo = models.FileField(
        upload_to=asset_photo_upload_path, storage=private_storage, blank=True,
        max_length=255,
    )
    photo_content_type = models.CharField(max_length=120, blank=True)
    photo_size = models.PositiveBigIntegerField(default=0)
```

En `Meta.indexes` agregar:

```python
            models.Index(fields=["company", "kind", "active"]),
            models.Index(fields=["company", "branch", "kind"]),
```

- [ ] **Step 5: Generar y aplicar la migración**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py makemigrations inventory
DJANGO_TESTING=true python manage.py migrate
```

Expected: `0003_product_asset_fields.py` creada y aplicada; ninguna migración pendiente.

- [ ] **Step 6: Ejecutar la prueba y verificar que pasa**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test apps.inventory.tests.test_assets.ProductAssetModelTests -v 2
```

Expected: PASS (2 tests).

- [ ] **Step 7: Commit (requiere autorización explícita de Carlos)**

```bash
git add backend/apps/inventory/storage.py backend/apps/inventory/models.py \
  backend/apps/inventory/migrations/0003_product_asset_fields.py \
  backend/config/settings.py backend/apps/inventory/tests/test_assets.py .gitignore
git commit -m "feat(inventory): add asset fields and private storage"
```

---

### Task 2: API de objetos, SKU automático y guardas de stock

**Files:**
- Modify: `backend/apps/inventory/serializers.py:45-71`
- Modify: `backend/apps/inventory/views.py:64-77`
- Modify: `backend/apps/inventory/services.py:50-140,251-264,369-382`
- Modify: `backend/apps/sales/services.py:48-87`
- Create: `backend/apps/sales/tests/test_assets_guard.py`
- Modify: `backend/apps/inventory/tests/test_assets.py`

**Interfaces:**
- Consumes: `Product.Kind`, `Product.AssetStatus`, `request_tenant`, `_ensure_company`.
- Produces: `ProductSerializer` con `kind/status/branch/assigned_worker/serial_number/internal_code/quantity/purchase_date/supplier/warranty_until/notes/photo_url`; `_generate_asset_sku(company)`; filtros `kind` y `status`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar a `backend/apps/inventory/tests/test_assets.py`:

```python
from rest_framework import status
from rest_framework.test import APITestCase


class ProductAssetApiTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()

    def test_asset_gets_automatic_sku(self):
        response = self.client.post("/api/v1/inventory/products/", {
            "kind": "asset",
            "name": "Secador",
            "serial_number": "SN-1",
            "branch": str(self.branch.id),
            "assigned_worker": None,
            "quantity": 1,
            "supplier": str(self.supplier.id),
            "cost": "120000",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["sku"].startswith("ACT-"))
        self.assertEqual(response.data["kind"], "asset")
        self.assertEqual(response.data["branch"], str(self.branch.id))

    def test_stock_requires_sku(self):
        response = self.client.post("/api/v1/inventory/products/", {
            "kind": "stock", "name": "Peine",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sku", response.data)

    def test_kind_cannot_change(self):
        asset = Product.objects.create(
            company=self.company, kind=Product.Kind.ASSET,
            sku="ACT-FIJO", name="Silla",
        )
        response = self.client.patch(
            f"/api/v1/inventory/products/{asset.id}/",
            {"kind": "stock"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("kind", response.data)

    def test_kind_filter_and_tenant_scope(self):
        Product.objects.create(
            company=self.company, kind=Product.Kind.ASSET,
            sku="ACT-1", name="Máquina",
        )
        foreign = self.foreign_objects()
        Product.objects.create(
            company=foreign["company"], kind=Product.Kind.ASSET,
            sku="ACT-EXT", name="Externa",
        )
        response = self.client.get("/api/v1/inventory/products/", {"kind": "asset"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {row["name"] for row in response.data["results"]}
        self.assertEqual(names, {"Máquina"})

    def test_asset_cannot_receive_stock(self):
        asset = Product.objects.create(
            company=self.company, kind=Product.Kind.ASSET,
            sku="ACT-2", name="Taladro",
        )
        response = self.entry(product=asset)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("product", response.data)

    def test_purchase_rejects_asset_line(self):
        asset = Product.objects.create(
            company=self.company, kind=Product.Kind.ASSET,
            sku="ACT-3", name="Compresor",
        )
        response = self.client.post(
            "/api/v1/inventory/purchases/",
            self.purchase_payload(lines=[
                {"product": str(asset.id), "quantity": "1", "unit_cost": "1000"},
            ]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lines", response.data)
```

`backend/apps/sales/tests/test_assets_guard.py`:

```python
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.sales.services import _normalize_sale_lines


class SaleAssetGuardTests(SimpleTestCase):
    def test_sale_rejects_asset_product(self):
        company = SimpleNamespace(id="company-1")
        product = SimpleNamespace(
            pk="product-1", company_id="company-1", kind="asset",
            active=True, sku="ACT-1", price=0, name="Máquina",
        )
        with self.assertRaisesMessage(ValidationError, "no maneja stock"):
            _normalize_sale_lines(
                [{"product": product, "service": None, "quantity": "1"}], company,
            )
```

- [ ] **Step 2: Ejecutar las pruebas y verificar que fallan**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test \
  apps.inventory.tests.test_assets.ProductAssetApiTests \
  apps.sales.tests.test_assets_guard -v 2
```

Expected: FAIL; el SKU automático no existe, los objetos aceptan movimientos y la venta no rechaza el objeto.

- [ ] **Step 3: Implementar `ProductSerializer`**

En `backend/apps/inventory/serializers.py`, importar:

```python
import uuid

from apps.workforce.models import WorkerProfile
```

Reemplazar `ProductSerializer` por:

```python
def _generate_asset_sku(company):
    for _ in range(20):
        sku = f"ACT-{uuid.uuid4().hex[:8].upper()}"
        if not Product.objects.filter(company=company, sku=sku).exists():
            return sku
    raise serializers.ValidationError({"sku": "No se pudo generar un SKU único."})


class ProductSerializer(TenantOwnedSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True,
    )
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True,
    )
    assigned_worker = serializers.PrimaryKeyRelatedField(
        queryset=WorkerProfile.objects.all(), required=False, allow_null=True,
    )
    supplier = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(), required=False, allow_null=True,
    )
    sku = serializers.CharField(required=False, allow_blank=True, max_length=64)
    quantity = serializers.IntegerField(required=False, min_value=1)
    category_name = serializers.CharField(source="category.name", read_only=True)
    unit_display = serializers.CharField(source="get_unit_display", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    assigned_worker_name = serializers.SerializerMethodField()
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "company", "kind", "kind_display", "status", "status_display",
            "sku", "name", "description", "category", "category_name", "unit",
            "unit_display", "cost", "price", "reorder_point", "barcode",
            "branch", "branch_name", "assigned_worker", "assigned_worker_name",
            "serial_number", "internal_code", "quantity", "purchase_date",
            "supplier", "supplier_name", "warranty_until", "notes",
            "photo_url", "photo_content_type", "photo_size", "active",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "photo_content_type", "photo_size", "created_at", "updated_at",
        ]

    def get_assigned_worker_name(self, obj):
        return str(obj.assigned_worker) if obj.assigned_worker_id else ""

    def get_photo_url(self, obj):
        if not obj.photo:
            return ""
        return f"/api/v1/inventory/products/{obj.id}/photo/"

    def validate_category(self, category):
        return _ensure_company(category, request_tenant(self.context["request"]), "category")

    def validate_branch(self, branch):
        return _ensure_company(branch, request_tenant(self.context["request"]), "branch")

    def validate_assigned_worker(self, worker):
        return _ensure_company(worker, request_tenant(self.context["request"]), "assigned_worker")

    def validate_supplier(self, supplier):
        return _ensure_company(supplier, request_tenant(self.context["request"]), "supplier")

    def validate(self, attrs):
        tenant = request_tenant(self.context["request"])
        instance = self.instance
        kind = attrs.get("kind", getattr(instance, "kind", Product.Kind.STOCK))
        if instance is not None and "kind" in attrs and attrs["kind"] != instance.kind:
            raise serializers.ValidationError(
                {"kind": "El tipo de producto no se puede cambiar."}
            )
        if kind == Product.Kind.STOCK:
            attrs["status"] = Product.AssetStatus.AVAILABLE
            sku = (attrs.get("sku") or getattr(instance, "sku", "")).strip()
            if not sku:
                raise serializers.ValidationError(
                    {"sku": "El SKU es obligatorio para insumos con stock."}
                )
            attrs["sku"] = sku
        else:
            sku = (attrs.get("sku") or getattr(instance, "sku", "")).strip()
            attrs["sku"] = sku or _generate_asset_sku(tenant)

        existing = Product.objects.filter(company=tenant, sku=attrs["sku"])
        if instance is not None:
            existing = existing.exclude(pk=instance.pk)
        if existing.exists():
            raise serializers.ValidationError({"sku": "Ya existe un producto con este SKU."})
        return attrs
```

- [ ] **Step 4: Implementar filtros de la vista**

En `ProductViewSet.queryset_for_tenant`:

```python
        queryset = (Product.objects.filter(company=tenant)
                    .select_related("category", "branch", "assigned_worker", "supplier"))
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category_id=category)
        kind = self.request.query_params.get("kind")
        if kind:
            if kind not in Product.Kind.values:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"kind": "Tipo de producto inválido."})
            queryset = queryset.filter(kind=kind)
        status_value = self.request.query_params.get("status")
        if status_value:
            if status_value not in Product.AssetStatus.values:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"status": "Estado de objeto inválido."})
            queryset = queryset.filter(status=status_value)
        branch = self.request.query_params.get("branch")
        if branch:
            queryset = queryset.filter(branch_id=branch)
        return _active(self, queryset)
```

- [ ] **Step 5: Implementar las guardas de stock**

En `services.py`, dentro de `record_movement`, después de `ensure_company(product, company, "product")`:

```python
    if product.kind != Product.Kind.STOCK:
        raise ValidationError({"product": "Los objetos no manejan stock."})
```

En `_normalize_purchase_lines`, después de `if not product.active`:

```python
        if product.kind != Product.Kind.STOCK:
            raise ValidationError({"lines": f"El objeto {product.sku} no maneja stock."})
```

En `_normalize_transfer_lines`, después de `product = ensure_company(...)`:

```python
        if product.kind != Product.Kind.STOCK:
            raise ValidationError({"lines": f"El objeto {product.sku} no maneja stock."})
```

En `_normalize_stocktake_lines`, después de `product = ensure_company(...)`:

```python
        if product.kind != Product.Kind.STOCK:
            raise ValidationError({"lines": f"El objeto {product.sku} no maneja stock."})
```

En `apps/sales/services.py`, dentro de `_normalize_sale_lines`, después de `if not product.active`:

```python
            if product.kind != "stock":
                raise ValidationError({"lines": f"El objeto {product.sku} no maneja stock."})
```

- [ ] **Step 6: Ejecutar las pruebas y verificar que pasan**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test \
  apps.inventory.tests.test_assets \
  apps.sales.tests.test_assets_guard -v 2
```

Expected: PASS. Luego ejecutar la regresión:

```bash
DJANGO_TESTING=true python manage.py test apps.inventory apps.sales -v 1
```

Expected: toda la suite de inventario y ventas en verde.

- [ ] **Step 7: Commit (requiere autorización explícita de Carlos)**

```bash
git add backend/apps/inventory/serializers.py backend/apps/inventory/views.py \
  backend/apps/inventory/services.py backend/apps/sales/services.py \
  backend/apps/inventory/tests/test_assets.py backend/apps/sales/tests/test_assets_guard.py
git commit -m "feat(inventory): add asset API and block stock on assets"
```

---

### Task 3: Modelo `Document`

**Files:**
- Modify: `backend/apps/inventory/models.py` (después de `Product`)
- Modify: `backend/apps/inventory/admin.py`
- Create: `backend/apps/inventory/migrations/0004_document.py` (generada)
- Create: `backend/apps/inventory/tests/test_documents_model.py`

**Interfaces:**
- Consumes: `private_storage`, `document_upload_path`, `TenantScopedModel`, `Product`.
- Produces: `Document` con `client_id`, `name`, `original_name`, `content_type`, `size`, `file`, `product`, `uploaded_by`.

- [ ] **Step 1: Escribir la prueba que falla**

`backend/apps/inventory/tests/test_documents_model.py`:

```python
import shutil

from django.conf import settings
from django.core.files.base import ContentFile
from django.test import TestCase

from apps.inventory.models import Document
from .utils import InventoryScenarioMixin


class DocumentModelTests(InventoryScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()

    def tearDown(self):
        shutil.rmtree(settings.PRIVATE_MEDIA_ROOT, ignore_errors=True)

    def test_document_stores_metadata_and_private_path(self):
        document = Document.objects.create(
            company=self.company,
            client_id="0c3f7c2e-7b1a-4a6e-9f5a-2a1b3c4d5e6f",
            name="Factura",
            original_name="factura.pdf",
            content_type="application/pdf",
            size=12,
            product=self.product,
            file=ContentFile(b"%PDF-1.4 test", name="factura.pdf"),
        )
        self.assertTrue(document.file.name.startswith(f"documents/{self.company.id}/"))
        self.assertTrue(document.file.name.endswith(".pdf"))
        self.assertTrue(document.file.storage.exists(document.file.name))
        self.assertEqual(document.product, self.product)
```

- [ ] **Step 2: Ejecutar la prueba y verificar que falla**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test apps.inventory.tests.test_documents_model -v 2
```

Expected: FAIL con `ImportError: cannot import name 'Document'`.

- [ ] **Step 3: Implementar `Document`**

En `models.py`, importar:

```python
from django.conf import settings

from .storage import asset_photo_upload_path, document_upload_path, private_storage
```

Después de `Product`:

```python
class Document(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.UUIDField(null=True, blank=True)
    name = models.CharField(max_length=180)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    file = models.FileField(
        upload_to=document_upload_path, storage=private_storage, max_length=255,
    )
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="documents",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="uploaded_documents",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "created_at"]),
            models.Index(fields=["company", "product"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "client_id"],
                condition=models.Q(client_id__isnull=False),
                name="unique_document_client_id_per_company",
            ),
        ]

    def __str__(self):
        return self.name
```

- [ ] **Step 4: Registrar en admin**

En `backend/apps/inventory/admin.py`, importar `Document` y agregar:

```python
@admin.register(Document)
class DocumentAdmin(TenantScopedAdmin):
    list_display = ("name", "original_name", "content_type", "size", "product", "company")
    list_filter = ("company", "content_type")
    search_fields = ("name", "original_name")
    readonly_fields = ("size", "created_at", "updated_at")
```

- [ ] **Step 5: Generar y aplicar la migración**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py makemigrations inventory
DJANGO_TESTING=true python manage.py migrate
```

Expected: `0004_document.py` aplicada.

- [ ] **Step 6: Ejecutar la prueba y verificar que pasa**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test apps.inventory.tests.test_documents_model -v 2
```

Expected: PASS.

- [ ] **Step 7: Commit (requiere autorización explícita de Carlos)**

```bash
git add backend/apps/inventory/models.py backend/apps/inventory/admin.py \
  backend/apps/inventory/migrations/0004_document.py \
  backend/apps/inventory/tests/test_documents_model.py
git commit -m "feat(inventory): add private document model"
```

---

### Task 4: Validación, cuota y API de documentos

**Files:**
- Create: `backend/apps/inventory/files.py`
- Modify: `backend/apps/inventory/serializers.py`
- Modify: `backend/apps/inventory/views.py`
- Modify: `backend/config/urls.py:72-80`
- Create: `backend/apps/inventory/tests/test_documents_api.py`

**Interfaces:**
- Produces:
  - `sanitize_filename(name)`, `validate_document(upload)`, `validate_asset_photo(upload)`.
  - `storage_usage(company)` → `{used_bytes, limit_bytes, documents_bytes, photos_bytes, document_count, asset_photo_count}`.
  - `DocumentSerializer`, `DocumentUploadSerializer`.
  - `DocumentViewSet` con `list`, `create`, `destroy`, `download`, `storage`.
- Consumes: `Document`, `Product`, `record_event`, `HasTenantPermission`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/apps/inventory/tests/test_documents_api.py`:

```python
import shutil
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import Document
from .utils import InventoryScenarioMixin


PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"


class DocumentApiTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()

    def tearDown(self):
        shutil.rmtree(settings.PRIVATE_MEDIA_ROOT, ignore_errors=True)

    def upload(self, *, name="factura.pdf", content=PDF, content_type="application/pdf",
               product=None, client_id=None):
        payload = {
            "file": SimpleUploadedFile(name, content, content_type=content_type),
            "name": "Factura",
        }
        if product is not None:
            payload["product"] = str(product.id)
        if client_id is not None:
            payload["client_id"] = str(client_id)
        return self.client.post("/api/v1/inventory/documents/", payload, format="multipart")

    def test_upload_lists_and_downloads_with_private_headers(self):
        response = self.upload(product=self.product)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["product"], str(self.product.id))
        self.assertEqual(response.data["content_type"], "application/pdf")
        self.assertGreater(response.data["size"], 0)

        listing = self.client.get("/api/v1/inventory/documents/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 1)

        download = self.client.get(
            f"/api/v1/inventory/documents/{response.data['id']}/download/"
        )
        self.assertEqual(download.status_code, status.HTTP_200_OK)
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")
        self.assertEqual(download["Cache-Control"], "private, no-store")
        self.assertIn("attachment", download["Content-Disposition"])

    def test_client_id_is_idempotent(self):
        client_id = "8f1f6a60-4f7a-4c6f-9c1f-2c3d4e5f6a7b"
        first = self.upload(client_id=client_id)
        second = self.upload(client_id=client_id)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Document.objects.count(), 1)

    def test_invalid_format_is_rejected(self):
        response = self.upload(
            name="script.exe", content=b"MZ...", content_type="application/octet-stream",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file", response.data)

    def test_foreign_product_is_rejected(self):
        foreign = self.foreign_objects()
        response = self.upload(product=foreign["product"])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("product", response.data)

    def test_quota_exceeded(self):
        with patch("apps.inventory.views.COMPANY_STORAGE_LIMIT_BYTES", 10):
            response = self.upload()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_foreign_document_is_not_visible(self):
        response = self.upload()
        foreign = self.foreign_objects()
        foreign_doc = Document.objects.create(
            company=foreign["company"], name="Externo", original_name="externo.pdf",
            content_type="application/pdf", size=4,
            file=SimpleUploadedFile("externo.pdf", PDF, content_type="application/pdf"),
        )
        listing = self.client.get("/api/v1/inventory/documents/")
        ids = {row["id"] for row in listing.data["results"]}
        self.assertNotIn(str(foreign_doc.id), ids)
        download = self.client.get(
            f"/api/v1/inventory/documents/{foreign_doc.id}/download/"
        )
        self.assertEqual(download.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_removes_file(self):
        response = self.upload()
        document = Document.objects.get(pk=response.data["id"])
        path = document.file.path
        file_name = document.file.name
        deleted = self.client.delete(f"/api/v1/inventory/documents/{document.id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Document.objects.filter(pk=document.id).exists())
        self.assertFalse(settings.PRIVATE_MEDIA_ROOT.joinpath(file_name).exists())
        self.assertTrue(path)

    def test_storage_usage(self):
        self.upload()
        response = self.client.get("/api/v1/inventory/documents/storage/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data["used_bytes"], 0)
        self.assertEqual(response.data["limit_bytes"], 5_368_709_120)
        self.assertEqual(response.data["document_count"], 1)
```

- [ ] **Step 2: Ejecutar las pruebas y verificar que fallan**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test apps.inventory.tests.test_documents_api -v 2
```

Expected: FAIL; la ruta `/documents/` responde 404.

- [ ] **Step 3: Crear `files.py`**

`backend/apps/inventory/files.py`:

```python
from pathlib import Path

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Sum
from PIL import Image
from rest_framework.exceptions import ValidationError

from .models import Document, Product

DOCUMENT_MAX_BYTES = 50 * 1024 * 1024
ASSET_PHOTO_MAX_BYTES = 10 * 1024 * 1024
COMPANY_STORAGE_LIMIT_BYTES = 5 * 1024 * 1024 * 1024

EXTENSIONS = {
    "pdf": {"application/pdf"},
    "doc": {"application/msword"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "xls": {"application/vnd.ms-excel"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "csv": {"text/csv", "application/csv", "text/plain"},
    "txt": {"text/plain"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
    "webp": {"image/webp"},
    "ppt": {"application/vnd.ms-powerpoint"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "zip": {"application/zip", "application/x-zip-compressed"},
}

PHOTO_EXTENSIONS = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "webp": "image/webp"}
PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}


def sanitize_filename(name):
    cleaned = Path(str(name or "archivo")).name
    cleaned = "".join(char for char in cleaned if char.isprintable())
    return cleaned[:255] or "archivo"


def _head(upload, size=12):
    upload.seek(0)
    head = upload.read(size)
    upload.seek(0)
    return head


def _matches_signature(extension, head):
    if extension == "pdf":
        return head.startswith(b"%PDF-")
    if extension in {"docx", "xlsx", "pptx", "zip"}:
        return head.startswith(b"PK\x03\x04")
    if extension in {"doc", "xls", "ppt"}:
        return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if extension in {"jpg", "jpeg"}:
        return head.startswith(b"\xff\xd8\xff")
    if extension == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == "webp":
        return head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    return True


def validate_document(upload):
    if upload is None or upload.size <= 0:
        raise ValidationError({"file": "El archivo está vacío."})
    if upload.size > DOCUMENT_MAX_BYTES:
        raise ValidationError({"file": "El archivo no puede superar 50 MB."})
    original = sanitize_filename(upload.name)
    extension = Path(original).suffix.lower().lstrip(".")
    if extension not in EXTENSIONS:
        raise ValidationError({"file": "Formato no permitido."})
    declared = (getattr(upload, "content_type", "") or "").lower()
    if declared and declared not in EXTENSIONS[extension]:
        raise ValidationError({"file": "El tipo declarado no coincide con el formato."})
    if not _matches_signature(extension, _head(upload)):
        raise ValidationError({"file": "El contenido no coincide con el formato."})
    return original


def validate_asset_photo(upload):
    if upload is None or upload.size <= 0:
        raise ValidationError({"photo": "La foto está vacía."})
    if upload.size > ASSET_PHOTO_MAX_BYTES:
        raise ValidationError({"photo": "La foto no puede superar 10 MB."})
    original = sanitize_filename(upload.name)
    extension = Path(original).suffix.lower().lstrip(".")
    if extension not in PHOTO_EXTENSIONS:
        raise ValidationError({"photo": "La foto debe ser PNG, JPEG o WebP."})
    try:
        image = Image.open(upload)
        image_format = image.format
        image.verify()
    except Exception:
        raise ValidationError({"photo": "La foto debe ser una imagen válida."})
    finally:
        upload.seek(0)
    if image_format not in PHOTO_FORMATS:
        raise ValidationError({"photo": "La foto debe ser PNG, JPEG o WebP."})
    return original


def storage_usage(company):
    documents_bytes = Document.objects.filter(company=company).aggregate(
        total=Sum("size"),
    )["total"] or 0
    photos_bytes = Product.objects.filter(company=company).aggregate(
        total=Sum("photo_size"),
    )["total"] or 0
    return {
        "used_bytes": int(documents_bytes) + int(photos_bytes),
        "limit_bytes": COMPANY_STORAGE_LIMIT_BYTES,
        "documents_bytes": int(documents_bytes),
        "photos_bytes": int(photos_bytes),
        "document_count": Document.objects.filter(company=company).count(),
        "asset_photo_count": Product.objects.filter(
            company=company, kind=Product.Kind.ASSET, photo__gt="",
        ).count(),
    }
```

- [ ] **Step 4: Implementar serializers**

En `serializers.py`, importar:

```python
from django.db import transaction
from django.utils import timezone
from pathlib import Path

from apps.audit.services import record_event
from apps.tenancy.models import Company

from .files import (
    COMPANY_STORAGE_LIMIT_BYTES, sanitize_filename, storage_usage, validate_document,
)
from .models import Document
```

Agregar:

```python
class DocumentSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    product = serializers.UUIDField(source="product_id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    uploaded_by_email = serializers.EmailField(
        source="uploaded_by.email", read_only=True, allow_null=True,
    )
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "company", "client_id", "name", "original_name", "content_type",
            "size", "product", "product_name", "product_sku", "uploaded_by_email",
            "download_url", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_download_url(self, obj):
        return f"/api/v1/inventory/documents/{obj.id}/download/"


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    name = serializers.CharField(required=False, allow_blank=True, max_length=180)
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=False, allow_null=True,
    )
    client_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_file(self, upload):
        self.original_name = validate_document(upload)
        return upload

    def validate_product(self, product):
        if product is None:
            return product
        company = request_tenant(self.context["request"])
        if product.company_id != company.id:
            raise serializers.ValidationError("El producto debe pertenecer a la empresa activa.")
        if not product.active:
            raise serializers.ValidationError("El producto está inactivo.")
        return product

    def create(self, validated_data):
        request = self.context["request"]
        company = request_tenant(request)
        upload = validated_data["file"]
        original_name = getattr(self, "original_name", sanitize_filename(upload.name))
        product = validated_data.get("product")
        client_id = validated_data.get("client_id")

        with transaction.atomic():
            Company.objects.select_for_update().get(pk=company.pk)
            if client_id is not None:
                existing = Document.objects.filter(
                    company=company, client_id=client_id,
                ).first()
                if existing is not None:
                    return existing, False
            usage = storage_usage(company)
            if usage["used_bytes"] + upload.size > COMPANY_STORAGE_LIMIT_BYTES:
                raise serializers.ValidationError(
                    {"detail": "La empresa alcanzó el límite de 5 GB de almacenamiento."}
                )
            document = Document.objects.create(
                company=company,
                client_id=client_id,
                name=(validated_data.get("name") or Path(original_name).stem)[:180],
                original_name=original_name,
                content_type=(upload.content_type or "application/octet-stream")[:120],
                size=upload.size,
                file=upload,
                product=product,
                uploaded_by=request.user if request.user.is_authenticated else None,
            )
        record_event(
            company=company, actor=request.user, action="inventory.document.created",
            instance=document, metadata={"name": document.name, "product_id": str(product.id) if product else None},
        )
        return document, True
```

- [ ] **Step 5: Implementar `DocumentViewSet`**

En `views.py`, imports:

```python
from django.http import FileResponse
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from django.db import transaction
from apps.audit.services import record_event
from apps.tenancy.models import Company

from .files import COMPANY_STORAGE_LIMIT_BYTES, sanitize_filename, storage_usage
from .models import Document
from .serializers import DocumentSerializer, DocumentUploadSerializer
```

Agregar antes de `CategoryViewSet`:

```python
class DocumentViewSet(
    ListModelMixin, RetrieveModelMixin, GenericViewSet,
):
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "post", "delete", "head", "options"]
    permission_map = {
        "list": "inventory.read", "retrieve": "inventory.read",
        "download": "inventory.read", "storage": "inventory.read",
        "create": "inventory.write", "destroy": "inventory.write",
    }

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated
        from apps.tenancy.permissions import HasTenantContext, HasTenantPermission
        return [IsAuthenticated(), HasTenantContext(), HasTenantPermission()]

    def get_required_tenant_permission(self):
        return self.permission_map.get(self.action)

    def get_tenant(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            from apps.tenancy.authentication import resolve_tenant
            tenant = resolve_tenant(self.request, self.request.user)
        return tenant

    def get_queryset(self):
        return self.queryset_for_tenant(self.get_tenant())

    def queryset_for_tenant(self, tenant):
        queryset = (Document.objects.filter(company=tenant)
                    .select_related("product", "uploaded_by"))
        product = self.request.query_params.get("product")
        if product:
            queryset = queryset.filter(product_id=product)
        linked = self.request.query_params.get("linked")
        if linked == "true":
            queryset = queryset.filter(product__isnull=False)
        elif linked == "false":
            queryset = queryset.filter(product__isnull=True)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) | models.Q(original_name__icontains=search)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = DocumentUploadSerializer(
            data=request.data, context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        document, created = serializer.save()
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            DocumentSerializer(document, context=self.get_serializer_context()).data,
            status=status_code,
        )

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        record_event(
            company=self.get_tenant(), actor=request.user,
            action="inventory.document.deleted", instance=document,
            metadata={"name": document.name},
        )
        document.file.delete(save=False)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()
        try:
            handle = document.file.open("rb")
        except FileNotFoundError:
            raise NotFound("El archivo ya no está disponible.")
        response = FileResponse(
            handle,
            as_attachment=True,
            filename=sanitize_filename(document.original_name),
            content_type=document.content_type or "application/octet-stream",
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        record_event(
            company=self.get_tenant(), actor=request.user,
            action="inventory.document.downloaded", instance=document,
            metadata={"name": document.name},
        )
        return response

    @action(detail=False, methods=["get"])
    def storage(self, request):
        return Response(storage_usage(self.get_tenant()))
```

`DocumentViewSet` no hereda `TenantModelViewSet`; se agrega el import de `models` de Django para `Q`:

```python
from django.db import models
```

- [ ] **Step 6: Registrar la ruta**

En `backend/config/urls.py`, importar `DocumentViewSet` y registrar:

```python
inventory_router.register("documents", DocumentViewSet, basename="inventory-document")
```

- [ ] **Step 7: Ejecutar las pruebas y verificar que pasan**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test apps.inventory.tests.test_documents_api -v 2
```

Expected: PASS (8 tests). Si falla `test_quota_exceeded` por el tamaño del PDF, usar un archivo de prueba de más de 10 bytes; el límite se parchea a 10.

- [ ] **Step 8: Commit (requiere autorización explícita de Carlos)**

```bash
git add backend/apps/inventory/files.py backend/apps/inventory/serializers.py \
  backend/apps/inventory/views.py backend/config/urls.py \
  backend/apps/inventory/tests/test_documents_api.py
git commit -m "feat(inventory): add private document API with quota and download"
```

---

### Task 5: Foto de objeto

**Files:**
- Modify: `backend/apps/inventory/serializers.py`
- Modify: `backend/apps/inventory/views.py`
- Create: `backend/apps/inventory/tests/test_asset_photos.py`

**Interfaces:**
- Produces: `AssetPhotoSerializer`; acciones `photo` (GET/POST/DELETE) en `ProductViewSet`.
- Consumes: `validate_asset_photo`, `storage_usage`, `private_storage`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/apps/inventory/tests/test_asset_photos.py`:

```python
import base64
import shutil

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import Product
from .utils import InventoryScenarioMixin

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z1ZkAAAAASUVORK5CYII="
)


class AssetPhotoTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()
        self.asset = Product.objects.create(
            company=self.company, kind=Product.Kind.ASSET,
            sku="ACT-FOTO", name="Máquina",
        )

    def tearDown(self):
        shutil.rmtree(settings.PRIVATE_MEDIA_ROOT, ignore_errors=True)

    def upload(self, content=PNG, name="foto.png", content_type="image/png"):
        return self.client.post(
            f"/api/v1/inventory/products/{self.asset.id}/photo/",
            {"photo": SimpleUploadedFile(name, content, content_type=content_type)},
            format="multipart",
        )

    def test_upload_get_replace_and_delete_photo(self):
        response = self.upload()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.asset.refresh_from_db()
        first_name = self.asset.photo.name
        self.assertTrue(first_name.startswith(f"assets/{self.company.id}/"))

        image = self.client.get(f"/api/v1/inventory/products/{self.asset.id}/photo/")
        self.assertEqual(image.status_code, status.HTTP_200_OK)
        self.assertEqual(image["Content-Type"], "image/png")

        response = self.upload()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.asset.refresh_from_db()
        self.assertNotEqual(self.asset.photo.name, first_name)
        self.assertFalse(settings.PRIVATE_MEDIA_ROOT.joinpath(first_name).exists())

        deleted = self.client.delete(
            f"/api/v1/inventory/products/{self.asset.id}/photo/"
        )
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.asset.refresh_from_db()
        self.assertFalse(self.asset.photo)

    def test_stock_product_rejects_photo(self):
        response = self.client.post(
            f"/api/v1/inventory/products/{self.product.id}/photo/",
            {"photo": SimpleUploadedFile("foto.png", PNG, content_type="image/png")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_invalid_image_is_rejected(self):
        response = self.upload(content=b"no es una imagen", name="foto.png")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("photo", response.data)
```

- [ ] **Step 2: Ejecutar las pruebas y verificar que fallan**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test apps.inventory.tests.test_asset_photos -v 2
```

Expected: FAIL con 404 en la ruta `photo/`.

- [ ] **Step 3: Implementar `AssetPhotoSerializer`**

En `serializers.py`, importar `validate_asset_photo` y agregar:

```python
class AssetPhotoSerializer(serializers.Serializer):
    photo = serializers.ImageField()

    def validate_photo(self, photo):
        validate_asset_photo(photo)
        return photo
```

- [ ] **Step 4: Implementar las acciones**

En `views.py`, imports:

```python
from rest_framework.parsers import FormParser, MultiPartParser
from apps.audit.services import record_event
from .files import storage_usage, validate_asset_photo
from .models import Product
from .serializers import AssetPhotoSerializer
```

En `ProductViewSet.permission_map` agregar:

```python
        "photo": "inventory.write",
```

En `ProductViewSet`, agregar:

```python
    def get_required_tenant_permission(self):
        if self.action == "photo" and self.request.method == "GET":
            return "inventory.read"
        return super().get_required_tenant_permission()

    @action(
        detail=True, methods=["get", "post", "delete"], url_path="photo",
        parser_classes=[MultiPartParser, FormParser],
    )
    def photo(self, request, pk=None):
        product = self.get_object()
        if request.method == "GET":
            if not product.photo:
                raise NotFound("El objeto no tiene foto.")
            try:
                handle = product.photo.open("rb")
            except FileNotFoundError:
                raise NotFound("La foto ya no está disponible.")
            response = FileResponse(
                handle, as_attachment=False,
                filename=sanitize_filename(Path(product.photo.name).name),
                content_type=product.photo_content_type or "application/octet-stream",
            )
            response["X-Content-Type-Options"] = "nosniff"
            response["Cache-Control"] = "private, max-age=300"
            return response

        if product.kind != Product.Kind.ASSET:
            raise ValidationError({"detail": "Solo los objetos admiten foto."})

        if request.method == "DELETE":
            old_name = product.photo.name
            product.photo.delete(save=False)
            product.photo_content_type = ""
            product.photo_size = 0
            product.save(update_fields=[
                "photo", "photo_content_type", "photo_size", "updated_at",
            ])
            if old_name:
                private_storage.delete(old_name)
            record_event(
                company=self.get_tenant(), actor=request.user,
                action="inventory.asset.photo_removed", instance=product,
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = AssetPhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["photo"]
        usage = storage_usage(self.get_tenant())
        if usage["used_bytes"] + upload.size > COMPANY_STORAGE_LIMIT_BYTES:
            raise ValidationError(
                {"detail": "La empresa alcanzó el límite de 5 GB de almacenamiento."}
            )
        old_name = product.photo.name
        product.photo = upload
        product.photo_content_type = upload.content_type or "image/png"
        product.photo_size = upload.size
        product.save(update_fields=[
            "photo", "photo_content_type", "photo_size", "updated_at",
        ])
        if old_name:
            private_storage.delete(old_name)
        record_event(
            company=self.get_tenant(), actor=request.user,
            action="inventory.asset.photo_set", instance=product,
        )
        return Response(
            ProductSerializer(product, context=self.get_serializer_context()).data,
        )
```

Agregar imports:

```python
from pathlib import Path
from .storage import private_storage
from .files import COMPANY_STORAGE_LIMIT_BYTES
```

- [ ] **Step 5: Ejecutar las pruebas y verificar que pasan**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test apps.inventory.tests.test_asset_photos -v 2
```

Expected: PASS (3 tests).

- [ ] **Step 6: Commit (requiere autorización explícita de Carlos)**

```bash
git add backend/apps/inventory/serializers.py backend/apps/inventory/views.py \
  backend/apps/inventory/tests/test_asset_photos.py
git commit -m "feat(inventory): add private asset photos"
```

---

### Task 6: Sincronización y operaciones móviles

**Files:**
- Modify: `backend/apps/mobile/sync.py`
- Modify: `backend/apps/mobile/resources.py`
- Modify: `backend/apps/mobile/operations.py`
- Create: `backend/apps/mobile/tests/test_inventory_mobile.py`

**Interfaces:**
- Consumes: `Document`, `Category`, `Supplier`, `ProductSerializer`, `DocumentSerializer`, `record_event`.
- Produces: recursos `categories`, `suppliers`, `documents`; operaciones `inventory.asset.create`, `inventory.asset.update`, `inventory.document.delete`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`backend/apps/mobile/tests/test_inventory_mobile.py`:

```python
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.identity.models import Membership
from apps.inventory.models import Document, Product
from apps.inventory.tests.utils import InventoryScenarioMixin
from apps.tenancy.tests.utils import make_context, make_membership, make_user, tenant_client


class InventoryMobileTests(InventoryScenarioMixin, APITestCase):
    def setUp(self):
        self.build_scenario()

    def test_bootstrap_includes_inventory_resources(self):
        response = self.client.get("/api/v1/mobile/bootstrap/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for resource in ("categories", "suppliers", "documents", "products"):
            self.assertIn(resource, response.data["sync_resources"])

    def test_documents_sync_is_tenant_scoped(self):
        Document.objects.create(
            company=self.company, name="Propio", original_name="propio.pdf",
            content_type="application/pdf", size=4,
            file=SimpleUploadedFile("propio.pdf", b"%PDF", content_type="application/pdf"),
        )
        foreign = self.foreign_objects()
        Document.objects.create(
            company=foreign["company"], name="Ajeno", original_name="ajeno.pdf",
            content_type="application/pdf", size=4,
            file=SimpleUploadedFile("ajeno.pdf", b"%PDF", content_type="application/pdf"),
        )
        response = self.client.get("/api/v1/mobile/sync/documents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {row["name"] for row in response.data["results"]}
        self.assertEqual(names, {"Propio"})

    def test_asset_create_operation_is_idempotent(self):
        payload = {
            "operations": [{
                "client_id": "11111111-1111-4111-8111-111111111111",
                "type": "inventory.asset.create",
                "payload": {
                    "kind": "asset", "name": "Máquina", "branch": str(self.branch.id),
                    "quantity": 1, "cost": "1000",
                },
            }],
        }
        first = self.client.post("/api/v1/mobile/operations/", payload, format="json")
        second = self.client.post("/api/v1/mobile/operations/", payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["results"][0]["status"], "applied")
        self.assertEqual(second.data["results"][0]["status"], "applied")
        self.assertEqual(
            first.data["results"][0]["data"]["id"],
            second.data["results"][0]["data"]["id"],
        )
        self.assertEqual(Product.objects.filter(kind=Product.Kind.ASSET).count(), 1)

    def test_document_delete_operation(self):
        document = Document.objects.create(
            company=self.company, name="Borrar", original_name="borrar.pdf",
            content_type="application/pdf", size=4,
            file=SimpleUploadedFile("borrar.pdf", b"%PDF", content_type="application/pdf"),
        )
        response = self.client.post("/api/v1/mobile/operations/", {
            "operations": [{
                "client_id": "22222222-2222-4222-8222-222222222222",
                "type": "inventory.document.delete",
                "payload": {"document": str(document.id)},
            }],
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["status"], "applied")
        self.assertFalse(Document.objects.filter(pk=document.id).exists())
```

- [ ] **Step 2: Ejecutar las pruebas y verificar que fallan**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test apps.mobile.tests.test_inventory_mobile -v 2
```

Expected: FAIL; los recursos y operaciones no existen.

- [ ] **Step 3: Agregar recursos al registro**

En `sync.py`, importar:

```python
from apps.inventory.models import (
    Category, Document, InventoryMovement, Product, StockBalance, Supplier, Warehouse,
)
from apps.inventory.serializers import (
    CategorySerializer, DocumentSerializer, InventoryMovementSerializer,
    ProductSerializer, StockBalanceSerializer, SupplierSerializer, WarehouseSerializer,
)
```

Agregar al diccionario:

```python
    "categories": SyncResource(
        Category, CategorySerializer, ("inventory.read",), feature="inventory",
    ),
    "suppliers": SyncResource(
        Supplier, SupplierSerializer, ("inventory.read",), feature="inventory",
    ),
    "documents": SyncResource(
        Document, DocumentSerializer, ("inventory.read",), feature="inventory",
        select_related=("product", "uploaded_by"),
    ),
```

En `resources.py`:

```python
    "categories": {"permissions": ("inventory.read",), "feature": "inventory"},
    "suppliers": {"permissions": ("inventory.read",), "feature": "inventory"},
    "documents": {"permissions": ("inventory.read",), "feature": "inventory"},
```

- [ ] **Step 4: Agregar operaciones**

En `operations.py`, importar:

```python
from apps.audit.services import record_event
from apps.inventory.models import Document, Product
from apps.inventory.serializers import ProductSerializer
```

Agregar a `OPERATION_TYPES`:

```python
    "inventory.asset.create", "inventory.asset.update", "inventory.document.delete",
```

Implementar antes de `HANDLERS`:

```python
def _asset_create(*, company, membership, user, payload, request):
    _ensure_permission(membership, "inventory.write")
    data = {key: value for key, value in payload.items() if key != "company"}
    data["kind"] = Product.Kind.ASSET
    serializer = ProductSerializer(data=data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    product = serializer.save(company=company)
    record_event(
        company=company, actor=user, action="inventory.asset.created",
        instance=product, metadata={"sku": product.sku},
    )
    return ProductSerializer(product).data


def _asset_update(*, company, membership, user, payload, request):
    _ensure_permission(membership, "inventory.write")
    product_id = payload.get("product")
    product = Product.objects.filter(
        company=company, pk=product_id, kind=Product.Kind.ASSET,
    ).first()
    if product is None:
        raise NotFound("El objeto no existe en la empresa activa.")
    data = {
        key: value for key, value in payload.items()
        if key not in {"company", "product"}
    }
    serializer = ProductSerializer(
        product, data=data, partial=True, context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    product = serializer.save()
    record_event(
        company=company, actor=user, action="inventory.asset.updated",
        instance=product, metadata={"sku": product.sku},
    )
    return ProductSerializer(product).data


def _document_delete(*, company, membership, user, payload, request):
    _ensure_permission(membership, "inventory.write")
    document = Document.objects.filter(
        company=company, pk=payload.get("document"),
    ).first()
    if document is None:
        raise NotFound("El documento no existe en la empresa activa.")
    record_event(
        company=company, actor=user, action="inventory.document.deleted",
        instance=document, metadata={"name": document.name},
    )
    document.file.delete(save=False)
    document.delete()
    return {"deleted": True}
```

Agregar a `HANDLERS`:

```python
    "inventory.asset.create": _asset_create,
    "inventory.asset.update": _asset_update,
    "inventory.document.delete": _document_delete,
```

- [ ] **Step 5: Ejecutar las pruebas y verificar que pasan**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test apps.mobile.tests.test_inventory_mobile -v 2
```

Expected: PASS (4 tests). Regresión móvil:

```bash
DJANGO_TESTING=true python manage.py test apps.mobile -v 1
```

Expected: toda la suite móvil en verde.

- [ ] **Step 6: Commit (requiere autorización explícita de Carlos)**

```bash
git add backend/apps/mobile/sync.py backend/apps/mobile/resources.py \
  backend/apps/mobile/operations.py backend/apps/mobile/tests/test_inventory_mobile.py
git commit -m "feat(mobile): sync inventory assets and documents"
```

---

### Task 7: Cliente Flutter con descarga y multipart completo

**Files:**
- Modify: `mobile/lib/data/api_client.dart`
- Create: `mobile/test/api_client_files_test.dart`

**Interfaces:**
- Produces: `ApiClient.getBytes(path, {query})` → `Uint8List`; `ApiClient.postMultipart(..., fields)`.
- Consumes: `_send`, `_headers`, `_uri`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`mobile/test/api_client_files_test.dart`:

```dart
import 'dart:convert';
import 'dart:typed_data';

import 'package:agenda_mobile/data/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('getBytes returns raw bytes with authentication', () async {
    late http.Request captured;
    final client = MockClient((request) async {
      captured = request;
      return http.Response.bytes(
        Uint8List.fromList([0x25, 0x50, 0x44, 0x46]),
        200,
      );
    });
    final api = ApiClient(baseUrl: 'http://fake', client: client)
      ..accessToken = 'access';

    final bytes = await api.getBytes('/api/v1/inventory/documents/1/download/');

    expect(bytes, [0x25, 0x50, 0x44, 0x46]);
    expect(captured.headers['Authorization'], 'Bearer access');
  });

  test('postMultipart includes extra fields', () async {
    late http.MultipartRequest captured;
    final client = MockClient((request) async {
      captured = request as http.MultipartRequest;
      return http.Response(jsonEncode({'id': 'doc-1'}), 201,
          headers: {'content-type': 'application/json'});
    });
    final api = ApiClient(baseUrl: 'http://fake', client: client)
      ..accessToken = 'access';

    await api.postMultipart(
      '/api/v1/inventory/documents/',
      field: 'file',
      bytes: [1, 2, 3],
      filename: 'factura.pdf',
      fields: {'client_id': 'abc', 'name': 'Factura'},
    );

    expect(captured.fields['client_id'], 'abc');
    expect(captured.fields['name'], 'Factura');
    expect(captured.files.single.field, 'file');
  });
}
```

- [ ] **Step 2: Ejecutar las pruebas y verificar que fallan**

Run:

```bash
cd mobile
flutter test test/api_client_files_test.dart
```

Expected: FAIL; `getBytes` no existe y `postMultipart` no acepta `fields`.

- [ ] **Step 3: Implementar los cambios**

En `api_client.dart`, importar:

```dart
import 'dart:typed_data';
```

Agregar después de `getMap`:

```dart
  Future<Uint8List> getBytes(
    String path, {
    Map<String, String>? query,
  }) async {
    final response = await _send('GET', path, query: query);
    return Uint8List.fromList(response.bodyBytes);
  }
```

Modificar `postMultipart`:

```dart
  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required String field,
    required List<int> bytes,
    required String filename,
    Map<String, String>? fields,
    bool retry = true,
  }) async {
    http.Response response;
    try {
      final headers = _headers()..remove('Content-Type');
      final request = http.MultipartRequest('POST', _uri(path))
        ..headers.addAll(headers)
        ..fields.addAll(fields ?? const {})
        ..files.add(
          http.MultipartFile.fromBytes(field, bytes, filename: filename),
        );
      response = await http.Response.fromStream(await _client.send(request));
    } catch (_) {
      throw ApiException(0, 'No se pudo conectar con el servidor.');
    }
    if (response.statusCode == 401 && retry && refreshToken != null) {
      if (await _refresh()) {
        return postMultipart(
          path,
          field: field,
          bytes: bytes,
          filename: filename,
          fields: fields,
          retry: false,
        );
      }
    }
    if (response.statusCode >= 400) {
      throw ApiException(response.statusCode, _errorMessage(response));
    }
    return _decodeMap(response);
  }
```

- [ ] **Step 4: Ejecutar la prueba y verificar que pasa**

Run:

```bash
cd mobile
flutter test test/api_client_files_test.dart
```

Expected: PASS (2 tests).

- [ ] **Step 5: Commit (requiere autorización explícita de Carlos)**

```bash
git add mobile/lib/data/api_client.dart mobile/test/api_client_files_test.dart
git commit -m "feat(mobile): support byte downloads and multipart fields"
```

---

### Task 8: Modelos y estado Flutter de inventario

**Files:**
- Modify: `mobile/lib/data/models.dart`
- Modify: `mobile/lib/state/app_state.dart`
- Create: `mobile/test/inventory_assets_test.dart`

**Interfaces:**
- Produces:
  - `ProductRecord.kind/status/statusDisplay/branchName/assignedWorkerName/serialNumber/internalCode/quantity/purchaseDate/supplierName/warrantyUntil/notes/photoUrl/isAsset`.
  - `CategoryRecord`, `SupplierRecord`, `DocumentRecord`, `UploadItem`, `StorageUsage`.
  - `AppState.assetObjects`, `stockProducts`, `documents`, `categories`, `suppliers`, `storageUsage`, `createAsset`, `updateAsset`, `deactivateAsset`, `uploadAssetPhoto`, `removeAssetPhoto`.
- Consumes: `_cache`, `_loadCachedData`, `syncAll`, `api`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`mobile/test/inventory_assets_test.dart`:

```dart
import 'package:agenda_mobile/data/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('ProductRecord parses asset fields', () {
    final asset = ProductRecord({
      'id': 'a1',
      'kind': 'asset',
      'kind_display': 'Objeto',
      'status': 'assigned',
      'status_display': 'Asignado',
      'sku': 'ACT-1',
      'name': 'Máquina',
      'branch_name': 'Centro',
      'assigned_worker_name': 'Ana',
      'serial_number': 'SN-1',
      'internal_code': 'INT-1',
      'quantity': 2,
      'purchase_date': '2026-01-15',
      'supplier_name': 'Proveedor',
      'warranty_until': '2027-01-15',
      'notes': 'Nota',
      'photo_url': '/api/v1/inventory/products/a1/photo/',
      'active': true,
    });

    expect(asset.isAsset, isTrue);
    expect(asset.statusDisplay, 'Asignado');
    expect(asset.branchName, 'Centro');
    expect(asset.assignedWorkerName, 'Ana');
    expect(asset.quantity, 2);
    expect(asset.photoUrl, contains('/photo/'));
  });

  test('DocumentRecord parses metadata and link', () {
    final document = DocumentRecord({
      'id': 'd1',
      'name': 'Factura',
      'original_name': 'factura.pdf',
      'content_type': 'application/pdf',
      'size': 1024,
      'product': 'a1',
      'product_name': 'Máquina',
      'created_at': '2026-11-11T10:00:00Z',
    });

    expect(document.name, 'Factura');
    expect(document.sizeLabel, isNotEmpty);
    expect(document.productId, 'a1');
    expect(document.linked, isTrue);
  });
}
```

- [ ] **Step 2: Ejecutar las pruebas y verificar que fallan**

Run:

```bash
cd mobile
flutter test test/inventory_assets_test.dart
```

Expected: FAIL; las propiedades no existen.

- [ ] **Step 3: Ampliar `ProductRecord`**

En `models.dart`, reemplazar `ProductRecord`:

```dart
class ProductRecord {
  ProductRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get sku => (raw['sku'] ?? '').toString();
  String get name => (raw['name'] ?? 'Producto').toString();
  String get kind => (raw['kind'] ?? 'stock').toString();
  bool get isAsset => kind == 'asset';
  String get status => (raw['status'] ?? 'available').toString();
  String get statusDisplay =>
      (raw['status_display'] ?? status).toString();
  String get branchId => (raw['branch'] ?? '').toString();
  String get branchName => (raw['branch_name'] ?? '').toString();
  String get assignedWorkerName =>
      (raw['assigned_worker_name'] ?? '').toString();
  String get serialNumber => (raw['serial_number'] ?? '').toString();
  String get internalCode => (raw['internal_code'] ?? '').toString();
  int get quantity => int.tryParse('${raw['quantity']}') ?? 1;
  String get purchaseDate => (raw['purchase_date'] ?? '').toString();
  String get supplierName => (raw['supplier_name'] ?? '').toString();
  String get warrantyUntil => (raw['warranty_until'] ?? '').toString();
  String get notes => (raw['notes'] ?? '').toString();
  String get photoUrl => (raw['photo_url'] ?? '').toString();
  String get price => (raw['price'] ?? '0').toString();
  bool get active => raw['active'] != false;
  double get reorderPoint => double.tryParse('${raw['reorder_point']}') ?? 0;
}
```

Agregar:

```dart
class CategoryRecord {
  CategoryRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get name => (raw['name'] ?? 'Categoría').toString();
  bool get active => raw['active'] != false;
}

class SupplierRecord {
  SupplierRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get name => (raw['name'] ?? 'Proveedor').toString();
  bool get active => raw['active'] != false;
}

class DocumentRecord {
  DocumentRecord(this.raw);

  final Map<String, dynamic> raw;

  String get id => (raw['id'] ?? '').toString();
  String get name => (raw['name'] ?? 'Archivo').toString();
  String get originalName => (raw['original_name'] ?? name).toString();
  String get contentType =>
      (raw['content_type'] ?? 'application/octet-stream').toString();
  int get size => int.tryParse('${raw['size']}') ?? 0;
  String get productId => (raw['product'] ?? '').toString();
  String get productName => (raw['product_name'] ?? '').toString();
  bool get linked => productId.isNotEmpty && productId != 'null';
  DateTime? get createdAt =>
      DateTime.tryParse((raw['created_at'] ?? '').toString());
  String get downloadUrl =>
      (raw['download_url'] ?? '/api/v1/inventory/documents/$id/download/')
          .toString();

  String get sizeLabel {
    if (size >= 1024 * 1024) {
      return '${(size / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    if (size >= 1024) return '${(size / 1024).toStringAsFixed(0)} KB';
    return '$size B';
  }
}

class StorageUsage {
  StorageUsage(this.raw);

  final Map<String, dynamic> raw;

  int get usedBytes => int.tryParse('${raw['used_bytes']}') ?? 0;
  int get limitBytes => int.tryParse('${raw['limit_bytes']}') ?? 0;
  int get documentsBytes => int.tryParse('${raw['documents_bytes']}') ?? 0;
  int get photosBytes => int.tryParse('${raw['photos_bytes']}') ?? 0;

  double get fraction =>
      limitBytes <= 0 ? 0 : (usedBytes / limitBytes).clamp(0, 1);
}

class UploadItem {
  UploadItem({
    required this.uploadId,
    required this.kind,
    required this.clientId,
    required this.companyId,
    required this.filePath,
    required this.filename,
    required this.size,
    required this.createdAt,
    this.name = '',
    this.productId,
    this.status = 'pending',
    this.error,
  });

  final String uploadId;
  final String kind;
  final String clientId;
  final String companyId;
  final String filePath;
  final String filename;
  final int size;
  final String createdAt;
  final String name;
  final String? productId;
  String status;
  String? error;

  bool get pending => status == 'pending';

  Map<String, dynamic> toJson() => {
    'upload_id': uploadId,
    'kind': kind,
    'client_id': clientId,
    'company_id': companyId,
    'file_path': filePath,
    'filename': filename,
    'size': size,
    'created_at': createdAt,
    'name': name,
    'product_id': productId,
    'status': status,
    'error': error,
  };

  factory UploadItem.fromJson(Map<String, dynamic> json) => UploadItem(
    uploadId: (json['upload_id'] ?? '').toString(),
    kind: (json['kind'] ?? 'document').toString(),
    clientId: (json['client_id'] ?? '').toString(),
    companyId: (json['company_id'] ?? '').toString(),
    filePath: (json['file_path'] ?? '').toString(),
    filename: (json['filename'] ?? 'archivo').toString(),
    size: int.tryParse('${json['size']}') ?? 0,
    createdAt: (json['created_at'] ?? '').toString(),
    name: (json['name'] ?? '').toString(),
    productId: json['product_id']?.toString(),
    status: (json['status'] ?? 'pending').toString(),
    error: json['error']?.toString(),
  );
}
```

- [ ] **Step 4: Ampliar `AppState`**

En `app_state.dart`, agregar getters después de `products`:

```dart
  List<ProductRecord> get assetObjects => products
      .where((product) => product.isAsset)
      .toList();

  List<ProductRecord> get stockProducts => products
      .where((product) => !product.isAsset)
      .toList();

  List<CategoryRecord> get categories => cached('categories')
      .map(CategoryRecord.new)
      .where((category) => category.active)
      .toList();

  List<SupplierRecord> get suppliers => cached('suppliers')
      .map(SupplierRecord.new)
      .where((supplier) => supplier.active)
      .toList();

  List<DocumentRecord> get documents => cached('documents')
      .map(DocumentRecord.new)
      .toList();
```

En `_loadCachedData`, agregar a la lista de recursos:

```dart
        'categories',
        'suppliers',
        'documents',
```

Si el plan `docs/superpowers/plans/2026-11-11-agenda-calendario.md` ya se aplicó,
no quites `'working-hours'` de esa lista.

Agregar métodos antes de `queueOperation`:

```dart
  Future<bool> createAsset(
    Map<String, dynamic> payload, {
    List<int>? photoBytes,
    String? photoFilename,
  }) async {
    _startBusy();
    try {
      final data = await api.postMap(
        '/api/v1/inventory/products/',
        body: {...payload, 'kind': 'asset'},
      );
      final id = data['id']?.toString();
      if (photoBytes != null && photoFilename != null && id != null) {
        await api.postMultipart(
          '/api/v1/inventory/products/$id/photo/',
          field: 'photo',
          bytes: photoBytes,
          filename: photoFilename,
        );
      }
      await syncAll();
      await _loadCachedData();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      _stopBusy();
    }
  }

  Future<bool> updateAsset(
    String id,
    Map<String, dynamic> payload, {
    List<int>? photoBytes,
    String? photoFilename,
  }) async {
    _startBusy();
    try {
      await api.patchMap('/api/v1/inventory/products/$id/', body: payload);
      if (photoBytes != null && photoFilename != null) {
        await api.postMultipart(
          '/api/v1/inventory/products/$id/photo/',
          field: 'photo',
          bytes: photoBytes,
          filename: photoFilename,
        );
      }
      await syncAll();
      await _loadCachedData();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      _stopBusy();
    }
  }

  Future<bool> deactivateAsset(String id) async {
    _startBusy();
    try {
      await api.delete('/api/v1/inventory/products/$id/');
      await syncAll();
      await _loadCachedData();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      _stopBusy();
    }
  }

  Future<bool> removeAssetPhoto(String id) async {
    _startBusy();
    try {
      await api.delete('/api/v1/inventory/products/$id/photo/');
      await syncAll();
      await _loadCachedData();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      _stopBusy();
    }
  }
```

- [ ] **Step 5: Ejecutar las pruebas y verificar que pasan**

Run:

```bash
cd mobile
flutter test test/inventory_assets_test.dart test/models_test.dart
```

Expected: PASS.

- [ ] **Step 6: Commit (requiere autorización explícita de Carlos)**

```bash
git add mobile/lib/data/models.dart mobile/lib/state/app_state.dart \
  mobile/test/inventory_assets_test.dart
git commit -m "feat(mobile): model inventory assets and documents"
```

---

### Task 9: Pestañas de inventario y formulario de objeto

**Files:**
- Modify: `mobile/lib/screens/inventory_screen.dart`
- Create: `mobile/lib/widgets/asset_form_sheet.dart`
- Create: `mobile/lib/widgets/asset_detail_sheet.dart`
- Create: `mobile/test/inventory_screen_test.dart`

**Interfaces:**
- Consumes: `AppState.assetObjects`, `createAsset`, `updateAsset`, `deactivateAsset`, `removeAssetPhoto`, `categories`, `suppliers`, `workers`, `bootstrap.branches`.
- Produces: pestañas `Objetos`, `Archivos`, `Stock`; formulario y detalle de objeto.

- [ ] **Step 1: Escribir la prueba que falla**

`mobile/test/inventory_screen_test.dart`:

```dart
import 'package:agenda_mobile/screens/inventory_screen.dart';
import 'package:agenda_mobile/state/app_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('inventory screen shows object and stock tabs', (tester) async {
    final app = AppState();
    await tester.pumpWidget(
      ChangeNotifierProvider<AppState>.value(
        value: app,
        child: const MaterialApp(home: InventoryScreen()),
      ),
    );

    expect(find.text('Objetos'), findsOneWidget);
    expect(find.text('Archivos'), findsOneWidget);
    expect(find.text('Stock'), findsOneWidget);
  });
}
```

- [ ] **Step 2: Ejecutar la prueba y verificar que falla**

Run:

```bash
cd mobile
flutter test test/inventory_screen_test.dart
```

Expected: FAIL; las pestañas no existen.

- [ ] **Step 3: Crear el formulario de objeto**

`mobile/lib/widgets/asset_form_sheet.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../core/theme.dart';
import '../data/models.dart';
import '../state/app_state.dart';

class AssetFormResult {
  AssetFormResult({
    required this.payload,
    this.photoBytes,
    this.photoFilename,
  });

  final Map<String, dynamic> payload;
  final List<int>? photoBytes;
  final String? photoFilename;
}

class AssetFormSheet extends StatefulWidget {
  const AssetFormSheet({super.key, this.asset});

  final ProductRecord? asset;

  @override
  State<AssetFormSheet> createState() => _AssetFormSheetState();
}

class _AssetFormSheetState extends State<AssetFormSheet> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _serial;
  late final TextEditingController _internal;
  late final TextEditingController _quantity;
  late final TextEditingController _cost;
  late final TextEditingController _notes;
  DateTime? _purchaseDate;
  DateTime? _warrantyUntil;
  String? _categoryId;
  String? _branchId;
  String? _workerId;
  String? _supplierId;
  String _status = 'available';
  List<int>? _photoBytes;
  String? _photoName;

  @override
  void initState() {
    super.initState();
    final raw = widget.asset?.raw ?? const <String, dynamic>{};
    _name = TextEditingController(text: '${raw['name'] ?? ''}');
    _serial = TextEditingController(text: '${raw['serial_number'] ?? ''}');
    _internal = TextEditingController(text: '${raw['internal_code'] ?? ''}');
    _quantity = TextEditingController(text: '${raw['quantity'] ?? 1}');
    _cost = TextEditingController(text: '${raw['cost'] ?? '0'}');
    _notes = TextEditingController(text: '${raw['notes'] ?? ''}');
    _categoryId = raw['category']?.toString();
    _branchId = raw['branch']?.toString();
    _workerId = raw['assigned_worker']?.toString();
    _supplierId = raw['supplier']?.toString();
    _status = (raw['status'] ?? 'available').toString();
    _purchaseDate = DateTime.tryParse('${raw['purchase_date'] ?? ''}');
    _warrantyUntil = DateTime.tryParse('${raw['warranty_until'] ?? ''}');
  }

  @override
  void dispose() {
    _name.dispose();
    _serial.dispose();
    _internal.dispose();
    _quantity.dispose();
    _cost.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto() async {
    final file = await ImagePicker().pickImage(
      source: ImageSource.gallery,
      maxWidth: 2000,
      imageQuality: 85,
    );
    if (file == null) return;
    final bytes = await file.readAsBytes();
    if (bytes.length > 10 * 1024 * 1024) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('La foto no puede superar 10 MB.')),
      );
      return;
    }
    setState(() {
      _photoBytes = bytes;
      _photoName = file.name;
    });
  }

  Future<void> _pickDate({required bool purchase}) async {
    final initial = (purchase ? _purchaseDate : _warrantyUntil) ?? DateTime.now();
    final value = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(1990),
      lastDate: DateTime(2100),
    );
    if (value == null) return;
    setState(() {
      if (purchase) {
        _purchaseDate = value;
      } else {
        _warrantyUntil = value;
      }
    });
  }

  String? _iso(DateTime? date) => date == null
      ? null
      : '${date.year.toString().padLeft(4, '0')}-'
            '${date.month.toString().padLeft(2, '0')}-'
            '${date.day.toString().padLeft(2, '0')}';

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    Navigator.pop(
      context,
      AssetFormResult(
        payload: {
          'name': _name.text.trim(),
          'serial_number': _serial.text.trim(),
          'internal_code': _internal.text.trim(),
          'quantity': int.tryParse(_quantity.text) ?? 1,
          'cost': _cost.text.trim().isEmpty ? '0' : _cost.text.trim(),
          'notes': _notes.text.trim(),
          'status': _status,
          'category': _categoryId,
          'branch': _branchId,
          'assigned_worker': _workerId,
          'supplier': _supplierId,
          'purchase_date': _iso(_purchaseDate),
          'warranty_until': _iso(_warrantyUntil),
        },
        photoBytes: _photoBytes,
        photoFilename: _photoName,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final branches = app.bootstrap?.branches ?? const <Map<String, dynamic>>[];
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          left: 22,
          right: 22,
          top: 22,
          bottom: MediaQuery.of(context).viewInsets.bottom + 22,
        ),
        child: Form(
          key: _formKey,
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  widget.asset == null ? 'Nuevo objeto' : 'Editar objeto',
                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _name,
                  decoration: const InputDecoration(labelText: 'Nombre *'),
                  validator: (value) => (value ?? '').trim().isEmpty
                      ? 'Ingresa un nombre.'
                      : null,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: _categoryId,
                  decoration: const InputDecoration(labelText: 'Categoría'),
                  items: [
                    for (final category in app.categories)
                      DropdownMenuItem(
                        value: category.id,
                        child: Text(category.name),
                      ),
                  ],
                  onChanged: (value) => setState(() => _categoryId = value),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: _pickPhoto,
                  icon: const Icon(Icons.photo_camera_outlined),
                  label: Text(
                    _photoBytes == null ? 'Agregar foto' : 'Foto seleccionada',
                  ),
                ),
                if (widget.asset?.photoUrl.isNotEmpty ?? false)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      'Ya tiene una foto; al guardar se reemplaza.',
                      style: TextStyle(color: context.palette.muted, fontSize: 12),
                    ),
                  ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _serial,
                  decoration: const InputDecoration(labelText: 'Número de serie'),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _internal,
                  decoration: const InputDecoration(labelText: 'Código interno'),
                ),
                const Divider(height: 30),
                DropdownButtonFormField<String>(
                  value: _status,
                  decoration: const InputDecoration(labelText: 'Estado'),
                  items: const [
                    DropdownMenuItem(value: 'available', child: Text('Disponible')),
                    DropdownMenuItem(value: 'assigned', child: Text('Asignado')),
                    DropdownMenuItem(
                      value: 'maintenance', child: Text('En mantenimiento'),
                    ),
                    DropdownMenuItem(value: 'retired', child: Text('Dado de baja')),
                  ],
                  onChanged: (value) =>
                      setState(() => _status = value ?? 'available'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: _branchId,
                  decoration: const InputDecoration(labelText: 'Sucursal'),
                  items: [
                    for (final branch in branches)
                      DropdownMenuItem(
                        value: '${branch['id']}',
                        child: Text('${branch['name']}'),
                      ),
                  ],
                  onChanged: (value) => setState(() => _branchId = value),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: _workerId,
                  decoration: const InputDecoration(labelText: 'Responsable'),
                  items: [
                    for (final worker in app.workers)
                      DropdownMenuItem(value: worker.id, child: Text(worker.name)),
                  ],
                  onChanged: (value) => setState(() => _workerId = value),
                ),
                const Divider(height: 30),
                TextFormField(
                  controller: _quantity,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Cantidad'),
                  validator: (value) {
                    final parsed = int.tryParse(value ?? '');
                    return parsed == null || parsed < 1
                        ? 'La cantidad debe ser al menos 1.'
                        : null;
                  },
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _notes,
                  maxLines: 3,
                  decoration: const InputDecoration(labelText: 'Notas'),
                ),
                const Divider(height: 30),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Fecha de compra'),
                  subtitle: Text(_iso(_purchaseDate) ?? 'Sin fecha'),
                  trailing: const Icon(Icons.calendar_month_outlined),
                  onTap: () => _pickDate(purchase: true),
                ),
                DropdownButtonFormField<String>(
                  value: _supplierId,
                  decoration: const InputDecoration(labelText: 'Proveedor'),
                  items: [
                    for (final supplier in app.suppliers)
                      DropdownMenuItem(
                        value: supplier.id,
                        child: Text(supplier.name),
                      ),
                  ],
                  onChanged: (value) => setState(() => _supplierId = value),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _cost,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Costo de compra'),
                  validator: (value) {
                    final parsed = double.tryParse(value ?? '');
                    return parsed == null || parsed < 0
                        ? 'El costo no puede ser negativo.'
                        : null;
                  },
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Fin de garantía'),
                  subtitle: Text(_iso(_warrantyUntil) ?? 'Sin fecha'),
                  trailing: const Icon(Icons.verified_outlined),
                  onTap: () => _pickDate(purchase: false),
                ),
                const SizedBox(height: 18),
                FilledButton(
                  onPressed: _submit,
                  child: Text(widget.asset == null ? 'Crear objeto' : 'Guardar'),
                ),
                const SizedBox(height: 8),
                Text(
                  'El SKU se genera automáticamente si no se informa.',
                  style: TextStyle(color: context.palette.muted, fontSize: 12),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Crear el detalle del objeto**

`mobile/lib/widgets/asset_detail_sheet.dart`:

```dart
import 'package:flutter/material.dart';

import '../core/formatters.dart';
import '../core/theme.dart';
import '../data/models.dart';

class AssetDetailSheet extends StatelessWidget {
  const AssetDetailSheet({
    super.key,
    required this.asset,
    required this.canWrite,
    required this.onEdit,
    required this.onDeactivate,
  });

  final ProductRecord asset;
  final bool canWrite;
  final VoidCallback onEdit;
  final VoidCallback onDeactivate;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(22),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              asset.name,
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 4),
            Text(
              '${asset.sku} · ${asset.statusDisplay}',
              style: TextStyle(color: context.palette.muted, fontSize: 12.5),
            ),
            const SizedBox(height: 16),
            if (asset.branchName.isNotEmpty)
              _Row(label: 'Sucursal', value: asset.branchName),
            if (asset.assignedWorkerName.isNotEmpty)
              _Row(label: 'Responsable', value: asset.assignedWorkerName),
            if (asset.serialNumber.isNotEmpty)
              _Row(label: 'Serie', value: asset.serialNumber),
            if (asset.internalCode.isNotEmpty)
              _Row(label: 'Código interno', value: asset.internalCode),
            _Row(label: 'Cantidad', value: '${asset.quantity}'),
            if (asset.supplierName.isNotEmpty)
              _Row(label: 'Proveedor', value: asset.supplierName),
            if (asset.purchaseDate.isNotEmpty)
              _Row(label: 'Compra', value: asset.purchaseDate),
            if (asset.warrantyUntil.isNotEmpty)
              _Row(label: 'Garantía hasta', value: asset.warrantyUntil),
            if (asset.notes.isNotEmpty)
              _Row(label: 'Notas', value: asset.notes),
            if (canWrite) ...[
              const SizedBox(height: 18),
              FilledButton.icon(
                onPressed: onEdit,
                icon: const Icon(Icons.edit_outlined),
                label: const Text('Editar'),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: onDeactivate,
                icon: const Icon(Icons.archive_outlined),
                label: const Text('Dar de baja'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: TextStyle(color: context.palette.muted, fontSize: 12.5),
            ),
          ),
          Expanded(
            child: Text(value, style: const TextStyle(fontSize: 13.5)),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 5: Agregar las pestañas a la pantalla**

En `inventory_screen.dart`, agregar el import:

```dart
import '../widgets/asset_detail_sheet.dart';
import '../widgets/asset_form_sheet.dart';
```

Agregar el enum al inicio:

```dart
enum _InventoryTab { objects, files, stock }
```

En `_InventoryScreenState`, agregar:

```dart
  _InventoryTab _tab = _InventoryTab.objects;
```

Reemplazar el `build` para que el encabezado y las pestañas sean comunes y el cuerpo cambie:

```dart
  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final enabled = app.moduleEnabled('inventory');
    return Scaffold(
      floatingActionButton: !enabled ? null : switch (_tab) {
        _InventoryTab.objects => app.can('inventory.write')
            ? FloatingActionButton.extended(
                onPressed: () => _openAssetForm(context),
                icon: const Icon(Icons.add_rounded),
                label: const Text('Nuevo objeto'),
              )
            : null,
        _InventoryTab.files => app.can('inventory.write')
            ? FloatingActionButton.extended(
                onPressed: () => _openUpload(context),
                icon: const Icon(Icons.upload_file_outlined),
                label: const Text('Subir archivo'),
              )
            : null,
        _InventoryTab.stock => app.can('inventory.write')
            ? FloatingActionButton.extended(
                onPressed: () => _openMovement(context),
                icon: const Icon(Icons.swap_vert_rounded),
                label: const Text('Movimiento'),
              )
            : null,
      },
      body: SafeArea(
        child: Column(
          children: [
            ScreenHeader(
              title: 'Inventario',
              subtitle:
                  '${app.assetObjects.length} objetos · ${app.documents.length} archivos',
              trailing: IconButton(
                tooltip: 'Sincronizar',
                onPressed: app.busy
                    ? null
                    : () => context.read<AppState>().refreshAll(),
                icon: const Icon(Icons.sync_rounded),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
              child: SegmentedButton<_InventoryTab>(
                segments: const [
                  ButtonSegment(
                    value: _InventoryTab.objects,
                    label: Text('Objetos'),
                    icon: Icon(Icons.inventory_2_outlined),
                  ),
                  ButtonSegment(
                    value: _InventoryTab.files,
                    label: Text('Archivos'),
                    icon: Icon(Icons.folder_outlined),
                  ),
                  ButtonSegment(
                    value: _InventoryTab.stock,
                    label: Text('Stock'),
                    icon: Icon(Icons.warehouse_outlined),
                  ),
                ],
                selected: {_tab},
                onSelectionChanged: (value) =>
                    setState(() => _tab = value.first),
              ),
            ),
            Expanded(child: _body(app, enabled)),
          ],
        ),
      ),
    );
  }

  Widget _body(AppState app, bool enabled) {
    if (!enabled) {
      return const EmptyState(
        icon: Icons.lock_outline_rounded,
        title: 'Inventario no incluido',
        message: 'El plan actual no incluye inventario o tu rol no tiene acceso.',
      );
    }
    return switch (_tab) {
      _InventoryTab.objects => InventoryObjectsTab(onOpen: (asset) {
          _openAssetDetail(context, asset);
        }),
      _InventoryTab.files => const InventoryFilesTab(),
      _InventoryTab.stock => _StockTab(
          onlyLow: _onlyLow,
          onOnlyLowChanged: (value) => setState(() => _onlyLow = value),
          onOpenDetail: (product, rows) => _openDetail(context, product, rows),
        ),
    };
  }
```

Mover el contenido actual del `ListView` de stock a `_StockTab` (misma lógica de métricas, chips, tarjetas y `_PendingMovements`) en el mismo archivo:

```dart
class _StockTab extends StatelessWidget {
  const _StockTab({
    required this.onlyLow,
    required this.onOnlyLowChanged,
    required this.onOpenDetail,
  });

  final bool onlyLow;
  final ValueChanged<bool> onOnlyLowChanged;
  final void Function(ProductRecord, List<StockRow>) onOpenDetail;

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final products = app.stockProducts;
    final rows = app.stockRows;
    final totals = <String, double>{};
    for (final row in rows) {
      final product = row.product;
      if (product != null) {
        totals[product.id] = (totals[product.id] ?? 0) + row.quantity;
      }
    }
    final lowCount = products
        .where((product) => _InventoryScreenState._isLow(
              product, totals[product.id] ?? 0,
            ))
        .length;
    final visible = onlyLow
        ? products.where((product) => _InventoryScreenState._isLow(
              product, totals[product.id] ?? 0,
            )).toList()
        : products;
    final canWrite = app.can('inventory.write');

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.only(bottom: 120),
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Row(
            children: [
              _Metric(value: '${products.length}', label: 'INSUMOS'),
              const SizedBox(width: 10),
              _Metric(value: '$lowCount', label: 'BAJO MÍNIMO'),
              const SizedBox(width: 10),
              _Metric(value: '${app.warehouses.length}', label: 'BODEGAS'),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 4),
          child: Wrap(
            spacing: 8,
            children: [
              ChoiceChip(
                label: const Text('Todo el stock'),
                selected: !onlyLow,
                onSelected: (_) => onOnlyLowChanged(false),
              ),
              ChoiceChip(
                label: Text('Bajo mínimo ($lowCount)'),
                selected: onlyLow,
                onSelected: (_) => onOnlyLowChanged(true),
              ),
            ],
          ),
        ),
        if (visible.isEmpty)
          EmptyState(
            icon: Icons.inventory_2_outlined,
            title: onlyLow ? 'Sin alertas de stock' : 'Sin insumos',
            message: onlyLow
                ? 'Ningún insumo está en su punto de reorden.'
                : 'Desliza hacia abajo para sincronizar el catálogo.',
            action: canWrite
                ? OutlinedButton(
                    onPressed: () => _openMovement(context),
                    child: const Text('Registrar movimiento'),
                  )
                : null,
          )
        else ...[
          const SectionLabel('Insumos'),
          for (final product in visible)
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
              child: _ProductCard(
                product: product,
                quantity: totals[product.id] ?? 0,
                rows: rows.where((row) => row.product?.id == product.id).toList(),
                low: _InventoryScreenState._isLow(
                  product, totals[product.id] ?? 0,
                ),
                canWrite: canWrite,
                onTap: () => onOpenDetail(
                  product,
                  rows.where((row) => row.product?.id == product.id).toList(),
                ),
              ),
            ),
        ],
        _PendingMovements(),
      ],
    );
  }
}
```

`_isLow` debe ser `static` accesible; ya lo es en `_InventoryScreenState` como `static bool _isLow(...)`, pero es privado de la clase, accesible desde el mismo archivo.

Agregar `InventoryObjectsTab` en un archivo nuevo `mobile/lib/widgets/inventory_objects_tab.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../data/models.dart';
import '../state/app_state.dart';
import 'common.dart';

class InventoryObjectsTab extends StatefulWidget {
  const InventoryObjectsTab({super.key, required this.onOpen});

  final ValueChanged<ProductRecord> onOpen;

  @override
  State<InventoryObjectsTab> createState() => _InventoryObjectsTabState();
}

class _InventoryObjectsTabState extends State<InventoryObjectsTab> {
  final _search = TextEditingController();
  String _status = 'all';
  String? _branchId;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final query = _search.text.trim().toLowerCase();
    final branches = app.bootstrap?.branches ?? const <Map<String, dynamic>>[];
    final visible = app.assetObjects.where((asset) {
      final matchesQuery = query.isEmpty ||
          asset.name.toLowerCase().contains(query) ||
          asset.sku.toLowerCase().contains(query) ||
          asset.serialNumber.toLowerCase().contains(query) ||
          asset.internalCode.toLowerCase().contains(query);
      final matchesStatus = _status == 'all' || asset.status == _status;
      final matchesBranch = _branchId == null || asset.branchId == _branchId;
      return matchesQuery && matchesStatus && matchesBranch;
    }).toList();

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.only(bottom: 120),
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: TextField(
            controller: _search,
            onChanged: (_) => setState(() {}),
            decoration: const InputDecoration(
              labelText: 'Buscar objeto',
              prefixIcon: Icon(Icons.search_rounded),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: _status,
                  decoration: const InputDecoration(labelText: 'Estado'),
                  items: const [
                    DropdownMenuItem(value: 'all', child: Text('Todos')),
                    DropdownMenuItem(value: 'available', child: Text('Disponible')),
                    DropdownMenuItem(value: 'assigned', child: Text('Asignado')),
                    DropdownMenuItem(
                      value: 'maintenance', child: Text('Mantenimiento'),
                    ),
                    DropdownMenuItem(value: 'retired', child: Text('Dado de baja')),
                  ],
                  onChanged: (value) =>
                      setState(() => _status = value ?? 'all'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: _branchId,
                  decoration: const InputDecoration(labelText: 'Sucursal'),
                  items: [
                    const DropdownMenuItem(value: null, child: Text('Todas')),
                    for (final branch in branches)
                      DropdownMenuItem(
                        value: '${branch['id']}',
                        child: Text('${branch['name']}'),
                      ),
                  ],
                  onChanged: (value) => setState(() => _branchId = value),
                ),
              ),
            ],
          ),
        ),
        if (visible.isEmpty)
          const EmptyState(
            icon: Icons.inventory_2_outlined,
            title: 'Sin objetos',
            message: 'Crea un objeto o ajusta los filtros.',
          )
        else ...[
          const SectionLabel('Objetos'),
          for (final asset in visible)
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
              child: Card(
                child: ListTile(
                  leading: CircleAvatar(
                    backgroundColor: context.palette.surfaceAlt,
                    child: const Icon(Icons.handyman_outlined),
                  ),
                  title: Text(asset.name),
                  subtitle: Text(
                    '${asset.sku} · ${asset.statusDisplay}'
                    '${asset.branchName.isEmpty ? '' : ' · ${asset.branchName}'}',
                  ),
                  trailing: const Icon(Icons.chevron_right_rounded),
                  onTap: () => widget.onOpen(asset),
                ),
              ),
            ),
        ],
      ],
    );
  }
}
```

En `inventory_screen.dart`, importar `inventory_objects_tab.dart` y usar `InventoryObjectsTab` en `_body`. Agregar `_openAssetForm` y `_openAssetDetail`:

```dart
  Future<void> _openAssetForm(BuildContext context, {ProductRecord? asset}) async {
    final result = await showModalBottomSheet<AssetFormResult>(
      context: context,
      isScrollControlled: true,
      backgroundColor: context.palette.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => AssetFormSheet(asset: asset),
    );
    if (result == null || !context.mounted) return;
    final app = context.read<AppState>();
    final ok = asset == null
        ? await app.createAsset(
            result.payload,
            photoBytes: result.photoBytes,
            photoFilename: result.photoFilename,
          )
        : await app.updateAsset(
            asset.id,
            result.payload,
            photoBytes: result.photoBytes,
            photoFilename: result.photoFilename,
          );
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(ok
            ? (asset == null ? 'Objeto creado' : 'Objeto actualizado')
            : app.errorMessage ?? 'No se pudo guardar el objeto.'),
      ),
    );
  }

  Future<void> _openAssetDetail(BuildContext context, ProductRecord asset) async {
    final app = context.read<AppState>();
    final canWrite = app.can('inventory.write');
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: context.palette.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => AssetDetailSheet(
        asset: asset,
        canWrite: canWrite,
        onEdit: () {
          Navigator.pop(sheetContext);
          _openAssetForm(context, asset: asset);
        },
        onDeactivate: () async {
          Navigator.pop(sheetContext);
          final ok = await app.deactivateAsset(asset.id);
          if (!context.mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(ok ? 'Objeto dado de baja' : app.errorMessage ?? 'Error')),
          );
        },
      ),
    );
  }
```

`InventoryFilesTab` y `_openUpload` se implementan en la Task 10. Para que esta tarea compile, crear un stub mínimo al final de `inventory_files_tab.dart`:

```dart
class InventoryFilesTab extends StatelessWidget {
  const InventoryFilesTab({super.key});

  @override
  Widget build(BuildContext context) {
    return const EmptyState(
      icon: Icons.folder_outlined,
      title: 'Archivos',
      message: 'La biblioteca se habilita en la tarea 10.',
    );
  }
}
```

y `_openUpload` en `inventory_screen.dart`:

```dart
  Future<void> _openUpload(BuildContext context) async {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('La subida se habilita en la tarea 10.')),
    );
  }
```

- [ ] **Step 6: Ejecutar la prueba y verificar que pasa**

Run:

```bash
cd mobile
flutter analyze
flutter test test/inventory_screen_test.dart
```

Expected: analyze sin errores; test PASS.

- [ ] **Step 7: Commit (requiere autorización explícita de Carlos)**

```bash
git add mobile/lib/screens/inventory_screen.dart \
  mobile/lib/widgets/asset_form_sheet.dart \
  mobile/lib/widgets/asset_detail_sheet.dart \
  mobile/lib/widgets/inventory_objects_tab.dart \
  mobile/lib/widgets/inventory_files_tab.dart mobile/test/inventory_screen_test.dart
git commit -m "feat(mobile): add inventory object tabs and forms"
```

---

### Task 10: Biblioteca de archivos, subida offline y descarga en caché

**Files:**
- Modify: `mobile/pubspec.yaml` (`file_picker`, `open_filex`)
- Create: `mobile/lib/data/file_store.dart`
- Modify: `mobile/lib/data/local_store.dart`
- Create: `mobile/lib/data/upload_queue.dart`
- Modify: `mobile/lib/state/app_state.dart`
- Modify: `mobile/lib/widgets/inventory_files_tab.dart`
- Modify: `mobile/lib/screens/inventory_screen.dart`
- Create: `mobile/test/inventory_files_test.dart`

**Interfaces:**
- Consumes: `LocalStore`, `ApiClient.postMultipart`, `ApiClient.getBytes`, `DocumentRecord`, `UploadItem`.
- Produces:
  - `companyUploadDir(companyId)`, `companyDownloadDir(companyId)`, `clearCompanyFiles(companyId)`.
  - `LocalStore.saveUpload/uploadItems/removeUpload/clearUploads`.
  - `UploadQueue.enqueueDocument`, `enqueuePhoto`, `flush`, `discard`, `items`.
  - `AppState.uploadDocument`, `downloadDocument`, `openDocument`, `deleteDocument`, `refreshStorage`, `flushUploads`.

- [ ] **Step 1: Agregar dependencias**

Run:

```bash
cd mobile
flutter pub add file_picker open_filex
```

Expected: `pubspec.yaml` incluye `file_picker` y `open_filex`; `flutter pub get` sin errores.

- [ ] **Step 2: Escribir las pruebas que fallan**

`mobile/test/inventory_files_test.dart`:

```dart
import 'package:agenda_mobile/data/local_store.dart';
import 'package:agenda_mobile/data/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('upload queue is scoped per company and survives reload', () async {
    final store = await LocalStore.memory();
    final item = UploadItem(
      uploadId: 'u1',
      kind: 'document',
      clientId: 'c1',
      companyId: 'company-a',
      filePath: '/tmp/a.pdf',
      filename: 'a.pdf',
      size: 10,
      createdAt: '2026-11-11T10:00:00Z',
    );
    await store.saveUpload(item);

    final own = await store.uploadItems(companyId: 'company-a');
    final other = await store.uploadItems(companyId: 'company-b');
    expect(own.single.clientId, 'c1');
    expect(other, isEmpty);

    await store.removeUpload('u1');
    expect(await store.uploadItems(companyId: 'company-a'), isEmpty);
  });

  test('clearing uploads removes pending items of every company', () async {
    final store = await LocalStore.memory();
    for (final companyId in const ['company-a', 'company-b']) {
      await store.saveUpload(
        UploadItem(
          uploadId: 'u-$companyId',
          kind: 'document',
          clientId: 'c-$companyId',
          companyId: companyId,
          filePath: '/tmp/$companyId.pdf',
          filename: '$companyId.pdf',
          size: 10,
          createdAt: '2026-11-11T10:00:00Z',
        ),
      );
    }

    await store.clearUploads();

    expect(await store.uploadItems(companyId: 'company-a'), isEmpty);
    expect(await store.uploadItems(companyId: 'company-b'), isEmpty);
  });
}
```

- [ ] **Step 3: Ejecutar la prueba y verificar que falla**

Run:

```bash
cd mobile
flutter test test/inventory_files_test.dart
```

Expected: FAIL; `saveUpload` no existe.

- [ ] **Step 4: Persistir subidas en `LocalStore`**

En `local_store.dart`, agregar:

```dart
  static final _uploadStore = stringMapStoreFactory.store('uploads');

  Future<void> saveUpload(UploadItem item) {
    return _uploadStore.record(item.uploadId).put(_db, item.toJson());
  }

  Future<List<UploadItem>> uploadItems({required String companyId}) async {
    final records = await _uploadStore.find(
      _db,
      finder: Finder(sortOrders: [SortOrder('created_at')]),
    );
    return records
        .map((record) => UploadItem.fromJson(record.value))
        .where((item) => item.companyId == companyId)
        .toList();
  }

  Future<void> removeUpload(String uploadId) {
    return _uploadStore.record(uploadId).delete(_db);
  }

  Future<void> clearUploads() => _uploadStore.delete(_db);
```

- [ ] **Step 5: Crear rutas de archivos por empresa**

`mobile/lib/data/file_store.dart`:

```dart
import 'dart:io';

import 'package:path_provider/path_provider.dart';

Future<Directory> _companyDir(String kind, String companyId) async {
  final root = await getApplicationSupportDirectory();
  final directory = Directory('${root.path}/$kind/$companyId');
  if (!await directory.exists()) {
    await directory.create(recursive: true);
  }
  return directory;
}

Future<Directory> companyUploadDir(String companyId) =>
    _companyDir('uploads', companyId);

Future<Directory> companyDownloadDir(String companyId) =>
    _companyDir('downloads', companyId);

Future<void> clearCompanyFiles(String companyId) async {
  for (final kind in const ['uploads', 'downloads']) {
    final directory = await _companyDir(kind, companyId);
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
  }
}

Future<void> clearAllCompanyFiles() async {
  final root = await getApplicationSupportDirectory();
  for (final kind in const ['uploads', 'downloads']) {
    final directory = Directory('${root.path}/$kind');
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
  }
}
```

- [ ] **Step 6: Crear la cola de subidas**

`mobile/lib/data/upload_queue.dart`:

```dart
import 'dart:io';

import 'package:uuid/uuid.dart';

import 'api_client.dart';
import 'file_store.dart';
import 'local_store.dart';
import 'models.dart';

class UploadQueue {
  UploadQueue(this.store, this.api);

  final LocalStore store;
  final ApiClient api;

  Future<UploadItem> enqueueDocument({
    required String companyId,
    required List<int> bytes,
    required String filename,
    String name = '',
    String? productId,
    String? clientId,
  }) async {
    final uploadId = const Uuid().v4();
    final directory = await companyUploadDir(companyId);
    final extension = filename.contains('.')
        ? filename.substring(filename.lastIndexOf('.'))
        : '';
    final path = '${directory.path}/$uploadId$extension';
    await File(path).writeAsBytes(bytes, flush: true);
    final item = UploadItem(
      uploadId: uploadId,
      kind: 'document',
      clientId: clientId ?? const Uuid().v4(),
      companyId: companyId,
      filePath: path,
      filename: filename,
      size: bytes.length,
      createdAt: DateTime.now().toIso8601String(),
      name: name,
      productId: productId,
    );
    await store.saveUpload(item);
    return item;
  }

  Future<UploadItem> enqueuePhoto({
    required String companyId,
    required String productId,
    required List<int> bytes,
    required String filename,
  }) async {
    final uploadId = const Uuid().v4();
    final directory = await companyUploadDir(companyId);
    final extension = filename.contains('.')
        ? filename.substring(filename.lastIndexOf('.'))
        : '.jpg';
    final path = '${directory.path}/$uploadId$extension';
    await File(path).writeAsBytes(bytes, flush: true);
    final item = UploadItem(
      uploadId: uploadId,
      kind: 'asset_photo',
      clientId: uploadId,
      companyId: companyId,
      filePath: path,
      filename: filename,
      size: bytes.length,
      createdAt: DateTime.now().toIso8601String(),
      productId: productId,
    );
    await store.saveUpload(item);
    return item;
  }

  Future<List<UploadItem>> items({required String companyId}) =>
      store.uploadItems(companyId: companyId);

  Future<void> discard(String uploadId) async {
    final items = await _all();
    for (final item in items.where((item) => item.uploadId == uploadId)) {
      final file = File(item.filePath);
      if (await file.exists()) await file.delete();
    }
    await store.removeUpload(uploadId);
  }

  Future<void> flush({required String companyId}) async {
    final pending = (await items(companyId: companyId))
        .where((item) => item.status != 'failed')
        .toList();
    for (final item in pending) {
      try {
        final bytes = await File(item.filePath).readAsBytes();
        if (item.kind == 'document') {
          await api.postMultipart(
            '/api/v1/inventory/documents/',
            field: 'file',
            bytes: bytes,
            filename: item.filename,
            fields: {
              'client_id': item.clientId,
              if (item.name.isNotEmpty) 'name': item.name,
              if (item.productId != null && item.productId!.isNotEmpty)
                'product': item.productId!,
            },
          );
        } else {
          await api.postMultipart(
            '/api/v1/inventory/products/${item.productId}/photo/',
            field: 'photo',
            bytes: bytes,
            filename: item.filename,
          );
        }
        final file = File(item.filePath);
        if (await file.exists()) await file.delete();
        await store.removeUpload(item.uploadId);
      } on ApiException catch (error) {
        item.error = error.message;
        item.status = error.offline ? 'pending' : 'failed';
        await store.saveUpload(item);
        if (error.offline) break;
      }
    }
  }

  Future<List<UploadItem>> _all() async {
    final root = await getApplicationSupportDirectory();
    final directory = Directory('${root.path}/uploads');
    if (!await directory.exists()) return const [];
    final results = <UploadItem>[];
    await for (final company in directory.list()) {
      if (company is! Directory) continue;
      results.addAll(await store.uploadItems(companyId: company.path.split(Platform.pathSeparator).last));
    }
    return results;
  }
}
```

Ajustar `_all` si la ruta no coincide con el id; los elementos siempre están en `<companyId>` así que el split funciona. Alternativamente, `discard` puede recibir el `UploadItem` desde la UI:

```dart
  Future<void> discardItem(UploadItem item) async {
    final file = File(item.filePath);
    if (await file.exists()) await file.delete();
    await store.removeUpload(item.uploadId);
  }
```

Usar `discardItem` en la UI para evitar recorrer directorios. Mantener ambos métodos no es necesario; usar solo `discardItem`.

- [ ] **Step 7: Integrar en `AppState`**

En `app_state.dart`, importar:

```dart
import 'package:flutter/services.dart';
import 'package:open_filex/open_filex.dart';

import '../data/file_store.dart';
import '../data/upload_queue.dart';
```

Agregar campos:

```dart
  late UploadQueue uploadQueue;
  StorageUsage? storage;
```

En `bootstrapApp`, después de `store` y `outbox`:

```dart
      uploadQueue = UploadQueue(store, api);
```

En `refreshAll`, después de `flushOutbox()`:

```dart
      if (activeCompanyId != null) {
        await uploadQueue.flush(companyId: activeCompanyId!);
      }
```

Agregar métodos:

```dart
  Future<bool> uploadDocument({
    required List<int> bytes,
    required String filename,
    String name = '',
    String? productId,
    String? clientId,
  }) async {
    final companyId = activeCompanyId;
    if (companyId == null) return false;
    await uploadQueue.enqueueDocument(
      companyId: companyId,
      bytes: bytes,
      filename: filename,
      name: name,
      productId: productId,
      clientId: clientId,
    );
    if (!offline) {
      await uploadQueue.flush(companyId: companyId);
      await syncAll();
      await refreshStorage();
    }
    await _loadCachedData();
    return true;
  }

  Future<void> refreshStorage() async {
    try {
      final data = await api.getMap('/api/v1/inventory/documents/storage/');
      storage = StorageUsage(data);
      notifyListeners();
    } on ApiException {
      // se conserva el último uso conocido
    }
  }

  Future<File?> downloadDocument(DocumentRecord document) async {
    final companyId = activeCompanyId;
    if (companyId == null) return null;
    final directory = await companyDownloadDir(companyId);
    final extension = document.originalName.contains('.')
        ? document.originalName.substring(document.originalName.lastIndexOf('.'))
        : '';
    final file = File('${directory.path}/${document.id}$extension');
    if (await file.exists()) return file;
    try {
      final bytes = await api.getBytes(document.downloadUrl);
      await file.writeAsBytes(bytes, flush: true);
      return file;
    } on ApiException catch (error) {
      errorMessage = error.offline
          ? 'Sin conexión: este archivo aún no se descargó.'
          : error.message;
      return null;
    }
  }

  Future<void> openDocument(DocumentRecord document) async {
    final file = await downloadDocument(document);
    if (file == null) return;
    await OpenFilex.open(file.path);
  }

  Future<bool> deleteDocument(String id) async {
    _startBusy();
    try {
      await api.delete('/api/v1/inventory/documents/$id/');
      final companyId = activeCompanyId;
      if (companyId != null) {
        final directory = await companyDownloadDir(companyId);
        for (final file in directory.listSync()) {
          if (file.path.split(Platform.pathSeparator).last.startsWith(id)) {
            await file.delete();
          }
        }
      }
      await syncAll();
      await refreshStorage();
      await _loadCachedData();
      return true;
    } on ApiException catch (error) {
      errorMessage = error.message;
      return false;
    } finally {
      _stopBusy();
    }
  }

  Future<void> releaseDownloads() async {
    final companyId = activeCompanyId;
    if (companyId == null) return;
    final directory = await companyDownloadDir(companyId);
    if (await directory.exists()) {
      await directory.delete(recursive: true);
    }
    notifyListeners();
  }
```

En `logout`, antes de limpiar estado:

```dart
      await store.clearUploads();
      await clearAllCompanyFiles();
```

En `_clearLocalState`, agregar:

```dart
    pendingUploads = [];
    storage = null;
```

En `_loadCachedData`, si `documents` está vacío, llamar `refreshStorage` no dentro de la carga (evitar bucles). La pestaña Archivos llama `refreshStorage` al abrirse.

- [ ] **Step 8: Implementar la pestaña Archivos**

Reemplazar el stub de `mobile/lib/widgets/inventory_files_tab.dart` por:

```dart
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../data/models.dart';
import '../state/app_state.dart';
import 'common.dart';

class InventoryFilesTab extends StatefulWidget {
  const InventoryFilesTab({super.key, this.productId});

  final String? productId;

  @override
  State<InventoryFilesTab> createState() => _InventoryFilesTabState();
}

class _InventoryFilesTabState extends State<InventoryFilesTab> {
  bool _linkedOnly = false;
  final _search = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AppState>().refreshStorage();
    });
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _pickAndUpload() async {
    final result = await FilePicker.platform.pickFiles(
      withData: true,
      allowMultiple: false,
    );
    final file = result?.files.single;
    if (file == null) return;
    final bytes = file.bytes ??
        (file.path == null ? null : await File(file.path!).readAsBytes());
    if (bytes == null) return;
    if (bytes.length > 50 * 1024 * 1024) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('El archivo no puede superar 50 MB.')),
      );
      return;
    }
    final app = context.read<AppState>();
    final ok = await app.uploadDocument(
      bytes: bytes,
      filename: file.name,
      productId: widget.productId,
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(ok
            ? 'Archivo en cola de subida'
            : app.errorMessage ?? 'No se pudo subir el archivo.'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppState>();
    final uploads = app.pendingUploads;
    final query = _search.text.trim().toLowerCase();
    final documents = app.documents.where((document) {
      final matchesQuery = query.isEmpty ||
          document.name.toLowerCase().contains(query) ||
          document.originalName.toLowerCase().contains(query);
      final matchesLink = !_linkedOnly || document.linked;
      final matchesProduct =
          widget.productId == null || document.productId == widget.productId;
      return matchesQuery && matchesLink && matchesProduct;
    }).toList();

    return RefreshIndicator(
      onRefresh: () => context.read<AppState>().refreshAll(),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.only(bottom: 120),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: TextField(
              controller: _search,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(
                labelText: 'Buscar archivo',
                prefixIcon: Icon(Icons.search_rounded),
              ),
            ),
          ),
          if (widget.productId == null)
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
              child: Row(
                children: [
                  FilterChip(
                    label: const Text('Solo vinculados'),
                    selected: _linkedOnly,
                    onSelected: (value) => setState(() => _linkedOnly = value),
                  ),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: _pickAndUpload,
                    icon: const Icon(Icons.upload_file_outlined),
                    label: const Text('Subir'),
                  ),
                ],
              ),
            ),
          if (app.storage != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  LinearProgressIndicator(value: app.storage!.fraction),
                  const SizedBox(height: 4),
                  Text(
                    '${_bytes(app.storage!.usedBytes)} de '
                    '${_bytes(app.storage!.limitBytes)} usados',
                    style: TextStyle(color: context.palette.muted, fontSize: 12),
                  ),
                ],
              ),
            ),
          if (documents.isEmpty)
            const EmptyState(
              icon: Icons.folder_outlined,
              title: 'Sin archivos',
              message: 'Sube un PDF, Word, Excel, imagen o ZIP.',
            )
          else ...[
            const SectionLabel('Archivos'),
            for (final document in documents)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                child: Card(
                  child: ListTile(
                    leading: const Icon(Icons.description_outlined),
                    title: Text(document.name),
                    subtitle: Text(
                      '${document.sizeLabel}'
                      '${document.linked ? ' · ${document.productName}' : ' · Sin vínculo'}',
                    ),
                    onTap: () => app.openDocument(document),
                    trailing: IconButton(
                      tooltip: 'Eliminar',
                      onPressed: () async {
                        final confirmed = await showDialog<bool>(
                          context: context,
                          builder: (dialogContext) => AlertDialog(
                            title: const Text('Eliminar archivo'),
                            content: Text('¿Eliminar "${document.name}"?'),
                            actions: [
                              TextButton(
                                onPressed: () => Navigator.pop(dialogContext, false),
                                child: const Text('Volver'),
                              ),
                              FilledButton(
                                onPressed: () => Navigator.pop(dialogContext, true),
                                child: const Text('Eliminar'),
                              ),
                            ],
                          ),
                        );
                        if (confirmed == true) {
                          await app.deleteDocument(document.id);
                        }
                      },
                      icon: const Icon(Icons.delete_outline_rounded),
                    ),
                  ),
                ),
              ),
          ],
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
            child: OutlinedButton.icon(
              onPressed: app.releaseDownloads,
              icon: const Icon(Icons.cleaning_services_outlined),
              label: const Text('Liberar espacio de descargas'),
            ),
          ),
          if (uploads.isNotEmpty)
            Padding(
              padding: const EdgeInsets.all(20),
              child: Text('Subidas pendientes: ${uploads.length}'),
            ),
        ],
      ),
    );
  }

  String _bytes(int value) {
    if (value >= 1024 * 1024 * 1024) {
      return '${(value / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
    }
    if (value >= 1024 * 1024) {
      return '${(value / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    if (value >= 1024) return '${(value / 1024).toStringAsFixed(0)} KB';
    return '$value B';
  }
}
```

La lista de subidas pendientes se obtiene del estado. Agregar a `AppState`:

```dart
  List<UploadItem> pendingUploads = [];

  Future<void> loadPendingUploads() async {
    final companyId = activeCompanyId;
    if (companyId == null) {
      pendingUploads = [];
    } else {
      pendingUploads = await uploadQueue.items(companyId: companyId);
    }
    notifyListeners();
  }
```

Y llamar `loadPendingUploads()` en `_loadCachedData`; la pestaña ya lee `app.pendingUploads`.

- [ ] **Step 9: Conectar el FAB de subida**

En `inventory_screen.dart`, reemplazar `_openUpload` por:

```dart
  Future<void> _openUpload(BuildContext context) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: context.palette.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => SizedBox(
        height: MediaQuery.of(context).size.height * 0.85,
        child: const InventoryFilesTab(),
      ),
    );
  }
```

- [ ] **Step 10: Ejecutar las pruebas y verificar que pasan**

Run:

```bash
cd mobile
flutter analyze
flutter test test/inventory_files_test.dart
```

Expected: analyze sin errores; test PASS. Luego:

```bash
flutter test
```

Expected: toda la suite en verde.

- [ ] **Step 11: Commit (requiere autorización explícita de Carlos)**

```bash
git add mobile/pubspec.yaml mobile/pubspec.lock mobile/lib/data/file_store.dart \
  mobile/lib/data/local_store.dart mobile/lib/data/upload_queue.dart \
  mobile/lib/state/app_state.dart mobile/lib/widgets/inventory_files_tab.dart \
  mobile/lib/screens/inventory_screen.dart mobile/test/inventory_files_test.dart
git commit -m "feat(mobile): add offline document upload and download cache"
```

---

### Task 11: Verificación integral y documentación

**Files:**
- Modify: `docs/superpowers/specs/2026-11-11-inventario-objetos-archivos-design.md` (solo si cambió una decisión)
- Modify: `docs/superpowers/plans/2026-11-11-web-admin-operador.md` (Task 19A, ver ese plan)
- No hay código nuevo.

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: evidencia de pruebas y el estado del inventario listo para la Task 19A web.

- [ ] **Step 1: Ejecutar la suite backend completa**

Run:

```bash
cd backend
DJANGO_TESTING=true python manage.py test -v 1
```

Expected: toda la suite en verde, incluidas inventario, ventas, móvil y tenancy.

- [ ] **Step 2: Ejecutar análisis y pruebas Flutter**

Run:

```bash
cd mobile
flutter analyze
flutter test
```

Expected: 0 issues y toda la suite en verde.

- [ ] **Step 3: Validación manual Flutter**

Con el backend local y una empresa con feature `inventory`:

1. Crear un objeto sin SKU; verificar `ACT-`.
2. Subir una foto; reemplazarla; quitarla.
3. Subir un PDF vinculado al objeto y otro sin vínculo.
4. Activar modo avión, subir un archivo; verificar "pendiente"; recuperar red y comprobar que se sube una sola vez.
5. Descargar un archivo, cerrar la app, abrir sin conexión y verificar que abre desde caché.
6. "Liberar espacio" y confirmar que el archivo del servidor sigue disponible.
7. Intentar un movimiento de stock sobre el objeto; debe fallar.
8. Cambiar de empresa y verificar que no aparecen objetos ni archivos de la anterior.
9. Repetir en claro y oscuro.

- [ ] **Step 4: Validación web (Task 19A)**

Cuando se ejecute la Task 19A del plan web:

1. Abrir `/inventario`; ver objetos y archivos.
2. Descargar un archivo y comprobar el nombre y el contenido.
3. Verificar que no hay acciones de escritura.
4. Verificar que un usuario sin `inventory.read` no ve la ruta.

- [ ] **Step 5: Commit (requiere autorización explícita de Carlos)**

Si hubo ajustes de documentación:

```bash
git add docs/superpowers/specs/2026-11-11-inventario-objetos-archivos-design.md \
  docs/superpowers/plans/2026-11-11-inventario-objetos-archivos.md
git commit -m "docs(inventory): update object and file implementation notes"
```

---

## Autoevaluación del plan

- **Cobertura de la especificación:** modelo y campos (Task 1), SKU y guardas (Task 2), `Document` (Task 3), API/cuota/descarga (Task 4), foto (Task 5), sync/operaciones (Task 6), cliente Flutter (Task 7), modelos/estado (Task 8), UI de objetos (Task 9), archivos/offline (Task 10), verificación (Task 11).
- **Aislamiento:** cada tarea incluye pruebas con una empresa ajena en lista, descarga, subida y operaciones.
- **Sin placeholders:** los pasos incluyen código o comandos exactos; la única coordinación externa es la Task 19A del plan web, que se implementa allí con su propio código.
- **Consistencia de tipos:** `Product.Kind`, `Product.AssetStatus`, `Document`, `DocumentSerializer`, `UploadItem`, `StorageUsage` se definen antes de usarse en tareas posteriores.
