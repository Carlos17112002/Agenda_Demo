# Inventario con objetos y archivos — especificación de diseño

- Fecha: 2026-11-11
- Estado: aprobado en conversación, pendiente de plan de implementación
- Clientes: `backend/`, `mobile/` y `web/` (solo lectura)
- Complementa: `docs/superpowers/specs/2026-11-11-web-admin-operador-design.md`
- Plan: `docs/superpowers/plans/2026-11-11-inventario-objetos-archivos.md`

## 1. Contexto y objetivo

El inventario actual está diseñado para insumos con stock: `Product`, `StockBalance`,
movimientos, compras, transferencias y conteos. Una barbería, un taller o un estudio
también necesitan registrar objetos físicos que no se consumen ni se valorizan por
cantidad: una máquina de corte, un secador, una silla, un equipo de sonido. Esos objetos
tienen número de serie, ubicación, responsable, estado, foto, garantía y documentos.

El objetivo es ampliar el inventario con dos conceptos separados:

1. **Objetos**: productos de tipo `asset` con datos de identificación, estado, ubicación,
   responsable, cantidad simple, compra y garantía. No participan del stock.
2. **Archivos**: una biblioteca de documentos por empresa, con vínculo opcional a un
   producto u objeto. Los archivos no son productos ni movimientos.

Flutter es el cliente de gestión. La web del operador solo lista objetos y permite
descargar archivos. Los archivos se pueden subir y descargar sin conexión desde Flutter.

## 2. Decisiones aprobadas

| Tema | Decisión |
| --- | --- |
| Plataforma | Flutter para gestión; web de solo lectura; backend como autoridad |
| Modelo de objeto | `Product.kind` con valores `stock` y `asset`; los `asset` no manejan stock |
| Archivos | Biblioteca de documentos con vínculo opcional a producto u objeto |
| Campos del objeto | Identificación, estado y ubicación, cantidad/notas/archivos, compra y garantía |
| Offline | Subida y descarga de archivos disponible sin conexión |
| Descarga | Bajo demanda al abrir; el archivo queda en caché hasta liberar espacio |
| Formatos | PDF, Word, Excel, CSV, TXT, imágenes, PowerPoint y ZIP |
| Límites | 50 MB por archivo; 5 GB por empresa; 10 MB por foto de objeto |
| Web | Solo lectura: listar objetos y descargar archivos |
| Eliminación | Productos con borrado lógico; documentos con borrado físico auditado |

## 3. Alcance

### Incluido

1. Campos de objeto en `Product` y reglas que impiden movimientos de stock sobre objetos.
2. SKU automático para objetos cuando no se informe uno.
3. Foto privada por objeto, con reemplazo y eliminación.
4. Modelo `Document` con archivo privado, metadatos, vínculo opcional a producto y
   `client_id` idempotente.
5. Endpoints autenticados de lista, alta, eliminación, descarga y uso de almacenamiento.
6. Validación de formato, tamaño y cuota por empresa.
7. Sincronización de metadatos de objetos, categorías, proveedores y documentos.
8. Operaciones móviles idempotentes para crear/editar objetos y eliminar documentos.
9. Cola persistente de subida de documentos y caché de descargas en Flutter.
10. Pantalla Flutter con pestañas Objetos, Archivos y Stock.
11. Pantalla web de solo lectura con objetos y archivos.
12. Pruebas de aislamiento entre empresas en cada capa.

### Fuera de alcance

- Extracción o vista previa del contenido de PDF, Office o ZIP.
- Edición colaborativa o control de versiones de documentos.
- Firma digital, OCR, antivirus o cuarentena de archivos.
- Carpetas, etiquetas o permisos por documento.
- Compartir archivos por enlace público.
- Depreciación contable, mantenimiento programado o historial de asignaciones.
- Gestión de objetos desde la web.
- Migración a PostgreSQL; se mantiene SQLite hasta el cambio planificado.

## 4. Modelo de datos

### 4.1 `Product.kind` y campos de objeto

Se agregan a `apps.inventory.models.Product`:

```python
class Kind(models.TextChoices):
    STOCK = "stock", "Insumo con stock"
    ASSET = "asset", "Objeto"

class AssetStatus(models.TextChoices):
    AVAILABLE = "available", "Disponible"
    ASSIGNED = "assigned", "Asignado"
    MAINTENANCE = "maintenance", "En mantenimiento"
    RETIRED = "retired", "Dado de baja"

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

Reglas:

- `kind` no cambia después de crear el producto. Un insumo con movimientos no puede
  convertirse en objeto ni al revés. La API responde `400` con
  `{"kind": "El tipo de producto no se puede cambiar."}`.
- `status`, `branch`, `assigned_worker`, `serial_number`, `internal_code`, `quantity`,
  `purchase_date`, `supplier`, `warranty_until`, `notes` y `photo` solo aplican a
  `asset`. En `stock` se guardan con sus valores por defecto y la API los ignora.
- `quantity` es una cantidad simple informativa para objetos. No genera
  `StockBalance` ni movimientos.
- `branch` y `assigned_worker` deben pertenecer a la empresa activa.
- `status = assigned` no exige `assigned_worker`; la UI lo sugiere, pero no es una
  invariante de datos. `retired` desactiva el objeto en la UI de creación de reservas
  y compras, pero no borra sus documentos.
- `cost` se reutiliza como costo de compra del objeto; `price` puede quedar en cero.
- `reorder_point` y `barcode` no se usan para objetos.
- Índices nuevos: `(company, kind, active)` y `(company, branch, kind)`.
- Los objetos usan el mismo borrado lógico (`active = False`) que los insumos.

### 4.2 `Document`

Nuevo modelo en `apps.inventory.models`:

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
```

Reglas:

- `name` es el nombre visible; por defecto es el nombre original sin extensión.
- `original_name` conserva el nombre entregado por el cliente, saneado.
- `content_type` es el MIME declarado y validado; si viene vacío se usa
  `application/octet-stream`.
- `size` se copia de `file.size` al guardar; nunca se confía en un tamaño enviado por
  el cliente.
- `product` es opcional. Si existe, debe ser de la misma empresa. Un documento puede
  quedar sin vínculo (biblioteca general).
- `client_id` permite reintentos idempotentes de subida. Es único por empresa cuando
  no es nulo.
- `uploaded_by` se toma de la sesión; no se acepta desde el cliente.
- Orden por `-created_at`; índices `(company, created_at)` y `(company, product)`.
- El borrado de un producto (`SET_NULL` no se ejecuta por ser borrado lógico) deja los
  documentos intactos. El borrado de un documento elimina el archivo físico.

### 4.3 SKU automático

- Un `asset` puede crearse sin `sku`. El backend genera `ACT-` + 8 caracteres
  hexadecimales en mayúsculas y reintenta si colisiona dentro de la empresa.
- Un `stock` sigue exigiendo `sku`; si falta, responde
  `{"sku": "El SKU es obligatorio para insumos con stock."}`.
- Un `asset` con `sku` explícito mantiene la unicidad `(company, sku)` existente.
- `internal_code` y `serial_number` son datos libres, no claves únicas.

## 5. Almacenamiento privado, cuotas y seguridad

### 5.1 Almacenamiento privado

`MEDIA_ROOT` se sirve públicamente en `DEBUG`; por eso los documentos y fotos de
objetos no pueden vivir ahí. Se define:

```python
PRIVATE_MEDIA_ROOT = Path(os.environ.get(
    "AGENDA_PRIVATE_MEDIA_ROOT", BASE_DIR / "private-media",
))
```

`apps.inventory.storage.private_storage` es un `FileSystemStorage` con
`location=PRIVATE_MEDIA_ROOT` y `base_url=None`. Las rutas se generan con UUID y el id
de la empresa:

```text
private-media/
  documents/<company_id>/<uuid>.<ext>
  assets/<company_id>/<uuid>.<ext>
```

`private-media/` se agrega a `.gitignore`. Nunca se publica una ruta estática para
estos archivos; la única salida es un endpoint autenticado.

### 5.2 Límites

| Límite | Valor |
| --- | --- |
| Tamaño máximo por documento | 50 MB (`52_428_800` bytes) |
| Tamaño máximo por foto | 10 MB (`10_485_760` bytes) |
| Cuota total por empresa | 5 GB (`5_368_709_120` bytes) |
| Formatos de documento | PDF, DOC, DOCX, XLS, XLSX, CSV, TXT, JPG, JPEG, PNG, WebP, PPT, PPTX, ZIP |
| Formatos de foto | JPEG, PNG, WebP |

La cuota incluye documentos y fotos de objetos. Se calcula con
`Sum(Document.size) + Sum(Product.photo_size)` por empresa. La comprobación y la
escritura ocurren dentro de una transacción con `select_for_update()` sobre la fila de
`Company`, para que dos subidas simultáneas no superen el límite.

Si la subida excede la cuota, responde `400`:

```json
{"detail": "La empresa alcanzó el límite de 5 GB de almacenamiento."}
```

### 5.3 Validación de archivos

Para documentos:

1. Sanear el nombre con `Path(name).name`, quitar caracteres de control y limitar a
   255 caracteres.
2. Validar extensión contra la lista permitida.
3. Validar MIME declarado contra la lista del formato.
4. Leer los primeros 8 bytes y comprobar la firma cuando el formato la tenga:
   - PDF: `%PDF-`
   - DOCX/XLSX/PPTX/ZIP: `PK\x03\x04`
   - DOC/XLS/PPT: `\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1`
   - JPEG: `\xff\xd8\xff`
   - PNG: `\x89PNG\r\n\x1a\n`
   - WebP: `RIFF` + `WEBP` en los bytes 8–11
   - CSV/TXT: sin firma; se acepta texto plano
5. Reponer el puntero al inicio antes de guardar.
6. Rechazar archivos vacíos.

Para fotos: validar tamaño, extensión/MIME y abrir con Pillow (`Image.verify()`), igual
que el logo de empresa. Se aceptan JPEG, PNG y WebP. No se impone un límite de
dimensiones distinto de los 10 MB; una imagen mayor se reescala en la UI antes de
subir.

### 5.4 Seguridad de descarga

- Toda lista, descarga, borrado y cuota parte de `company=request.tenant`.
- El endpoint de descarga obtiene el documento con `get_object()`, que ya filtra por
  empresa; un id de otra empresa responde `404`, nunca `403` con detalles.
- La respuesta usa `FileResponse(..., as_attachment=True)`, el nombre original
  saneado y `Content-Type` validado.
- Cabeceras obligatorias: `X-Content-Type-Options: nosniff` y
  `Cache-Control: private, no-store`.
- La foto de objeto se sirve inline desde un endpoint autenticado, con
  `Cache-Control: private, max-age=300`.
- No se aceptan rutas, nombres de archivo ni `company` desde el cliente.
- Cada descarga registra `document.downloaded` en auditoría con actor, documento y
  empresa. Las subidas registran `document.created`; los borrados,
  `document.deleted`.
- Los ZIP no se descomprimen en el servidor.

## 6. API

Todos los endpoints exigen `Authorization: Bearer` y `X-Tenant-Context`. Los permisos
se resuelven con el rol y los grants existentes.

### 6.1 Productos y objetos

| Método | Ruta | Permiso | Uso |
| --- | --- | --- | --- |
| GET | `/api/v1/inventory/products/` | `inventory.read` | Lista con `kind`, `branch`, `status`, `category`, `search`, `active`, `page` |
| POST | `/api/v1/inventory/products/` | `inventory.write` | Crea insumo u objeto |
| PATCH | `/api/v1/inventory/products/{id}/` | `inventory.write` | Edita campos; no permite cambiar `kind` |
| DELETE | `/api/v1/inventory/products/{id}/` | `inventory.write` | Borrado lógico (`active=false`) |
| POST | `/api/v1/inventory/products/{id}/photo/` | `inventory.write` | Sube o reemplaza foto (multipart, campo `photo`) |
| DELETE | `/api/v1/inventory/products/{id}/photo/` | `inventory.write` | Quita la foto |
| GET | `/api/v1/inventory/products/{id}/photo/` | `inventory.read` | Descarga la foto autenticada |

`ProductSerializer` agrega:

```text
kind, kind_display, status, status_display,
branch, branch_name, assigned_worker, assigned_worker_name,
serial_number, internal_code, quantity, purchase_date,
supplier, supplier_name, warranty_until, notes,
photo_url, photo_content_type, photo_size
```

`photo_url` es la ruta relativa del endpoint de foto o `""` si no hay foto. No es una
URL pública. Los filtros `kind` y `status` se validan contra los choices; un valor
inválido responde `400`.

La foto solo se acepta para `kind=asset`; para un insumo responde
`{"detail": "Solo los objetos admiten foto."}`.

### 6.2 Documentos

| Método | Ruta | Permiso | Uso |
| --- | --- | --- | --- |
| GET | `/api/v1/inventory/documents/` | `inventory.read` | Lista con `product`, `linked`, `search`, `page` |
| POST | `/api/v1/inventory/documents/` | `inventory.write` | Subida multipart (`file`, `name`, `product`, `client_id`) |
| DELETE | `/api/v1/inventory/documents/{id}/` | `inventory.write` | Borra metadatos y archivo |
| GET | `/api/v1/inventory/documents/{id}/download/` | `inventory.read` | Descarga autenticada |
| GET | `/api/v1/inventory/documents/storage/` | `inventory.read` | Uso y cuota de la empresa |

Respuesta de documento:

```json
{
  "id": "uuid",
  "company": "uuid",
  "client_id": "uuid-o-null",
  "name": "Factura máquina 1",
  "original_name": "factura.pdf",
  "content_type": "application/pdf",
  "size": 128734,
  "product": "uuid-o-null",
  "product_name": "Máquina de corte",
  "product_sku": "ACT-1A2B3C4D",
  "uploaded_by_email": "dueno@example.com",
  "download_url": "/api/v1/inventory/documents/<id>/download/",
  "created_at": "2026-11-11T15:00:00Z",
  "updated_at": "2026-11-11T15:00:00Z"
}
```

Subida:

- `name` es opcional; si falta se usa el nombre original sin extensión.
- `product` es opcional; si existe debe ser de la empresa activa.
- `client_id` es opcional. Si ya existe un documento con ese `client_id` en la empresa,
  el endpoint devuelve `200` con el documento existente en vez de crear otro. Si el
  `client_id` existe pero el contenido es distinto, igualmente devuelve el existente:
  la idempotencia protege reintentos de red, no versiones.
- Responde `201` al crear.
- Si el archivo no pasa validación, `400` con el campo `file`.
- Si se supera la cuota, `400` con `detail`.
- El parser acepta `multipart/form-data`; `application/json` responde `415`.

Uso de almacenamiento:

```json
{
  "used_bytes": 128734,
  "limit_bytes": 5368709120,
  "documents_bytes": 128734,
  "photos_bytes": 0,
  "document_count": 1,
  "asset_photo_count": 0
}
```

### 6.3 Errores

| Caso | Respuesta |
| --- | --- |
| Documento o producto de otra empresa | `404` |
| Sin permiso | `403` con mensaje genérico |
| Formato no permitido | `400` `{"file": "Formato no permitido."}` |
| Archivo mayor a 50 MB | `400` `{"file": "El archivo no puede superar 50 MB."}` |
| Cuota excedida | `400` `{"detail": "La empresa alcanzó el límite de 5 GB de almacenamiento."}` |
| Producto inactivo en un documento | `400` `{"product": "El producto está inactivo."}` |
| Cambio de `kind` | `400` `{"kind": "El tipo de producto no se puede cambiar."}` |
| Stock sobre un objeto | `400` `{"product": "Los objetos no manejan stock."}` |
| Foto sobre un insumo | `400` `{"detail": "Solo los objetos admiten foto."}` |

## 7. Reglas de stock

Los objetos no participan del ledger. Se aplica una comprobación en el punto único
`record_movement()` y en las normalizaciones de líneas:

- `record_movement`: si `product.kind != stock`, lanza
  `ValidationError({"product": "Los objetos no manejan stock."})`.
- `create_manual_movement`: valida el tipo antes de escribir y conserva el mensaje.
- `_normalize_purchase_lines`: rechaza objetos con
  `{"lines": "El objeto <sku> no maneja stock."}`.
- `_normalize_transfer_lines`: igual.
- `_normalize_stocktake_lines`: igual.
- `apps.sales.services._normalize_sale_lines`: rechaza objetos con el mismo mensaje;
  una venta no puede incluir un objeto.
- `StockBalanceViewSet` y sus reportes no cambian: los objetos no tienen saldo y no
  aparecen.

La comprobación en `record_movement` es la defensa final para cualquier llamada futura
que olvide validar antes.

## 8. Sincronización móvil y operaciones

### 8.1 Recursos de sincronización

Se agregan a `SYNC_REGISTRY` y a la lista duplicada `SYNC_RESOURCES`:

| Recurso | Modelo | Permiso | Feature | Cursor |
| --- | --- | --- | --- | --- |
| `categories` | `Category` | `inventory.read` | `inventory` | `updated_at` |
| `suppliers` | `Supplier` | `inventory.read` | `inventory` | `updated_at` |
| `documents` | `Document` | `inventory.read` | `inventory` | `updated_at` |

`products` ya existe y ahora incluye los campos de objeto. `documents` sincroniza solo
metadatos; el binario se descarga bajo demanda. Los recursos nuevos respetan
`company=request.tenant` y el aislamiento existente.

### 8.2 Operaciones

Se agregan a `OPERATION_TYPES` y `HANDLERS`:

| Tipo | Payload | Resultado |
| --- | --- | --- |
| `inventory.asset.create` | Campos de `Product` de objeto; sin `company` | `ProductSerializer` |
| `inventory.asset.update` | `{product, ...campos}` | `ProductSerializer` |
| `inventory.document.delete` | `{document}` | `{"deleted": true}` |

Reglas:

- Exigen `inventory.write` y el feature `inventory`.
- `asset.create` usa `ProductSerializer` con contexto de request; el `company` se
  asigna desde el tenant.
- `asset.update` carga el producto con `company=tenant`, rechaza `kind` distinto de
  `asset` y no permite cambiar `kind`.
- `document.delete` carga el documento con `company=tenant`, elimina el archivo físico
  y registra auditoría. Si el archivo ya no existe, igualmente elimina la fila.
- La idempotencia existente por `(company, client_id)` aplica a todas.

La subida binaria no usa `mobile/operations/`: se hace contra
`POST /api/v1/inventory/documents/` con `client_id`, que ya es idempotente. La cola
persistente de Flutter garantiza el reintento.

## 9. Experiencia Flutter

### 9.1 Navegación

La pantalla `Inventario` pasa a tener tres pestañas:

1. **Objetos**: `products` con `kind=asset`, búsqueda, filtro por estado y sucursal.
2. **Archivos**: todos los documentos, filtro vinculados/sueltos, búsqueda, uso de
   almacenamiento y acción de subir.
3. **Stock**: la vista actual de insumos, bajo mínimo, bodegas y movimientos.

La pestaña por defecto es Objetos. El FAB cambia según la pestaña: `Nuevo objeto` en
Objetos, `Subir archivo` en Archivos y `Movimiento` en Stock. Solo se muestran si el
rol tiene `inventory.write`.

### 9.2 Objetos

Lista:

- Tarjeta con foto (o icono), nombre, SKU, estado, sucursal y responsable.
- Búsqueda por nombre, SKU, serie o código interno.
- Filtros por estado y sucursal.
- Estado vacío con acción `Nuevo objeto`.

Formulario por secciones:

1. **Identificación**: nombre, categoría, foto, número de serie, código interno.
2. **Estado y ubicación**: estado, sucursal, responsable.
3. **Cantidad y notas**: cantidad (entero ≥ 1), notas.
4. **Compra y garantía**: fecha de compra, proveedor, costo, fin de garantía.

Validaciones locales: nombre obligatorio, cantidad ≥ 1, costo ≥ 0, garantía no anterior
a compra (advertencia, no bloqueo). El SKU es opcional para objetos; la UI muestra
"Se generará automáticamente".

Detalle:

- Foto, datos agrupados, documentos vinculados con acción de subir/descargar.
- Acciones editar y dar de baja (`active=false`) con confirmación.
- La foto se puede cambiar o quitar; requiere conexión.

### 9.3 Archivos

- Lista con nombre, tamaño, tipo, fecha y vínculo.
- Subir: selector de archivos (`file_picker`) con los formatos permitidos; valida
  50 MB antes de encolar. Permite elegir un objeto opcional.
- Descargar: al tocar, si está en caché se abre; si no, descarga autenticada y abre.
  Usa `open_filex`. Si no hay conexión y no está en caché, muestra
  "Sin conexión: este archivo aún no se descargó".
- Eliminar: confirmación; si no hay conexión se encola
  `inventory.document.delete` y desaparece de la lista local.
- Uso de almacenamiento: barra `usado / 5 GB`, con desglose documentos/fotos. Si está
  desactualizado, indica la fecha de última consulta.
- "Liberar espacio": elimina las descargas en caché de la empresa activa, no los
  archivos del servidor ni las subidas pendientes.

### 9.4 Subida y descarga offline

La cola de subidas es independiente del outbox JSON:

- Persistida en `LocalStore` bajo `uploads` con clave `$companyId::$uploadId`.
- Cada elemento guarda `kind` (`document` o `asset_photo`), `clientId`, `companyId`,
  `name`, `productId`, `filePath`, `filename`, `contentType`, `size`, `status`
  (`pending`, `uploading`, `failed`), `error` y `createdAt`.
- El binario se copia a `ApplicationSupport/uploads/<companyId>/<uploadId>.<ext>` al
  encolar, para sobrevivir al cierre de la app.
- Al recuperar conexión, se procesan en orden. Los documentos usan
  `postMultipart` con `client_id`; las fotos usan `product/{id}/photo`.
- Un `4xx` de validación deja el elemento `failed` con el mensaje del servidor y no se
  reintenta automáticamente. Un error de red queda `pending`.
- La UI muestra "Subidas pendientes (n)" y permite reintentar o descartar.
- Las descargas se guardan en
  `ApplicationSupport/downloads/<companyId>/<documentId>.<ext>`.
- Al cerrar sesión se eliminan descargas y subidas pendientes de todas las empresas,
  con confirmación si hay pendientes. Al cambiar de empresa no se borran, pero solo se
  muestran y procesan las de la empresa activa.
- La caché de metadatos ya está separada por empresa (`$companyId::$resource`).

### 9.5 Permisos y plan

- Sin `inventory.read`, la pantalla muestra el estado "Inventario no incluido".
- Sin `inventory.write`, se ocultan crear, editar, subir, eliminar y mover stock.
- Sin feature `inventory`, no se sincronizan recursos ni se muestran acciones.
- Un trabajador no tiene `inventory.read` por defecto y no ve la sección.

## 10. Experiencia web (solo lectura)

Ruta `/inventario`, permiso `inventory.read`, feature `inventory`. Dos pestañas:

- **Objetos**: tabla con foto, nombre, SKU, estado, sucursal, responsable y garantía.
  Búsqueda, filtro por sucursal y estado. Sin acciones de escritura.
- **Archivos**: tabla con nombre y nombre original, vínculo al objeto, tamaño, autor y
  acción de descarga. Descarga autenticada mediante blob; no se expone una URL pública.
  Filtro vinculados/sueltos y búsqueda.

No se muestran stock, compras, movimientos ni cuota en v1 web; la gestión completa
vive en Flutter. La web no sube ni elimina archivos.

## 11. Permisos y aislamiento

- `inventory.read` habilita listar/descargar; `inventory.write` habilita crear, editar,
  subir, eliminar y mover stock.
- Manager y owner ya tienen ambos permisos. El rol `inventory` los tiene. Recepción y
  trabajador no tienen `inventory.read` y no ven el inventario. Contabilidad conserva
  `inventory.read` sin escritura, así que ve las listas y descargas en web pero no la
  gestión.
- Toda consulta usa `company=tenant`; las relaciones (`category`, `branch`,
  `assigned_worker`, `supplier`, `product` de un documento) se validan contra la
  empresa activa.
- Los archivos se almacenan bajo `<company_id>` y solo se sirven tras comprobar la
  empresa del registro.
- No se acepta `company` en ningún payload.
- Las pruebas deben cubrir lista, detalle, descarga, borrado y subida con un usuario de
  otra empresa, esperando `404` o `400` según corresponda.

## 12. Pruebas

### Backend

- `Product.kind` por defecto `stock`; creación de `asset` con todos los campos; SKU
  automático y unicidad; `stock` sin SKU rechazado; cambio de `kind` rechazado.
- Movimiento manual, compra, transferencia, conteo y venta rechazan objetos.
- Foto: subida válida, reemplazo elimina el archivo anterior, formatos inválidos,
  tamaño > 10 MB, foto en insumo rechazada, descarga autenticada.
- Documento: subida válida, nombre por defecto, vínculo a producto propio, producto
  externo rechazado, formato inválido, archivo vacío, > 50 MB, cuota excedida,
  `client_id` idempotente, lista filtrada, descarga con cabeceras, borrado físico,
  descarga de otra empresa `404`.
- Cuota: suma documentos + fotos; empresa distinta no se contabiliza.
- Sincronización: `products`, `categories`, `suppliers` y `documents` filtrados por
  empresa; un usuario sin `inventory.read` no recibe los recursos.
- Operaciones: crear/editar objeto y eliminar documento; idempotencia; permisos;
  objeto de otra empresa rechazado.
- Regresión: stock, compras, transferencias, conteos y ventas existentes siguen verdes.

### Flutter

- Parseo de `ProductRecord` de objeto y `DocumentRecord`.
- Pestañas Objetos/Archivos/Stock y visibilidad por permisos.
- Formulario de objeto: validaciones y payload.
- Cola de subidas: persiste, reintenta, falla por validación, se separa por empresa.
- Descarga: usa caché, descarga una vez, abre el archivo, libera espacio.
- Eliminación offline de documento.
- `flutter analyze` y `flutter test`.

### Web

- Lista de objetos y archivos con MSW; descarga blob con cabeceras.
- Ruta y navegación visibles solo con permiso y feature.
- Estado vacío y error de red.
- `npm run test`, `npm run build` y `npm run lint`.

## 13. Criterios de aceptación

1. Un dueño crea un objeto sin SKU y el servidor asigna `ACT-XXXXXXXX`; el objeto
   aparece en Flutter y en la web.
2. El objeto guarda estado, sucursal, responsable, serie, código interno, cantidad,
   notas, compra, proveedor, costo, garantía y foto.
3. Un objeto no puede recibir movimientos, compras, transferencias, conteos ni ventas.
4. Se sube un PDF de 2 MB vinculado a un objeto; aparece en la biblioteca, se descarga
   autenticado y se elimina con su archivo físico.
5. Se rechazan formatos no permitidos, archivos > 50 MB y subidas que superen 5 GB.
6. Un documento sin vínculo aparece en la biblioteca general.
7. Flutter sube un archivo sin conexión, lo muestra como pendiente y lo envía al
   recuperar la red; el reintento no duplica el documento.
8. Flutter descarga un archivo una vez, lo abre sin conexión después y puede liberar
   espacio sin afectar el servidor.
9. La web lista objetos y archivos y descarga con sesión; no ofrece escritura.
10. Un usuario de otra empresa no puede listar, descargar, borrar ni vincular los
    objetos o archivos ajenos.
11. La caché, la cola de subidas y las descargas están separadas por empresa; al
    cerrar sesión no quedan archivos locales.
12. `flutter analyze`, `flutter test`, las pruebas backend, Vitest, build y lint pasan.

## 14. Riesgos y decisiones asumidas

- **SQLite y archivos**: los blobs viven en el sistema de archivos, no en la base. El
  backup debe incluir `private-media/`; se documenta en el plan de despliegue.
- **Cuota global**: 5 GB por empresa es un límite de producto, no una cuota física del
  disco. El servidor debe monitorear espacio libre.
- **Validación de MIME**: la firma reduce el riesgo, pero no sustituye un antivirus.
  No se ejecutan archivos; se descargan como adjunto.
- **Fotos en web**: se cargan por blob autenticado; no se cachean en disco.
- **Objetos y stock**: son tipos del mismo modelo, no tablas separadas. Esto mantiene
  categorías, proveedores y borrado lógico, a costa de campos compartidos que los
  insumos ignoran.
- **Cantidad simple**: no hay historial de cantidades ni ubicaciones múltiples por
  objeto. Si se necesita, será un submódulo posterior.
- **Sin vista previa**: abrir un archivo depende de una app externa del dispositivo.

No quedan decisiones abiertas para esta versión.
