import base64
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.audit.models import AuditEvent
from apps.identity.models import Membership
from apps.tenancy.models import Company
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class CompanyBrandingTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_root = tempfile.mkdtemp()
        cls.media_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.media_override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)

    def setUp(self):
        self.company = make_company("salon-central", "Salón Central")
        self.owner = make_user("owner-branding@example.com")
        make_membership(self.owner, self.company, Membership.Role.OWNER)
        self.client = tenant_client(self.owner, make_context(self.owner, self.company))

    def url(self):
        return "/api/v1/company/branding/"

    def test_owner_reads_default_branding(self):
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["display_name"], "Salón Central")
        self.assertEqual(response.data["primary_color"], "#E50914")
        self.assertEqual(response.data["secondary_color"], "#8B0000")
        self.assertEqual(response.data["theme_mode"], "light")
        self.assertEqual(response.data["logo_url"], "")
        self.assertTrue(response.data["booking_url"].endswith("/b/salon-central/"))
        self.assertTrue(response.data["can_manage"])

    def test_owner_updates_branding_and_booking_slug(self):
        response = self.client.patch(self.url(), {
            "display_name": "Salón Aurora",
            "primary_color": "#00A896",
            "secondary_color": "#028090",
            "theme_mode": "dark",
            "slug": "salon-aurora",
        }, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.company.refresh_from_db()
        self.assertEqual(self.company.display_name, "Salón Aurora")
        self.assertEqual(self.company.primary_color, "#00A896")
        self.assertEqual(self.company.theme_mode, "dark")
        self.assertEqual(response.data["theme_mode"], "dark")
        self.assertEqual(self.company.slug, "salon-aurora")
        self.assertTrue(response.data["booking_url"].endswith("/b/salon-aurora/"))
        self.assertTrue(AuditEvent.objects.filter(
            company=self.company, action="company.branding_updated",
        ).exists())

    def test_branding_is_tenant_scoped_and_readable_by_any_member(self):
        reception = make_user("reception-branding@example.com")
        make_membership(reception, self.company, Membership.Role.RECEPTION)
        client = tenant_client(reception, make_context(reception, self.company))

        self.assertEqual(client.get(self.url()).status_code, 200)
        denied = client.patch(self.url(), {"display_name": "Intruso"}, format="json")
        self.assertEqual(denied.status_code, 403)

        outsider = make_user("outsider-branding@example.com")
        other = make_company("otra-marca", "Otra Marca")
        make_membership(outsider, other, Membership.Role.OWNER)
        outsider_client = tenant_client(outsider, make_context(outsider, self.company))
        self.assertEqual(outsider_client.get(self.url()).status_code, 403)
        self.assertEqual(outsider_client.patch(
            self.url(), {"display_name": "Otra"}, format="json",
        ).status_code, 403)

    def test_branding_rejects_invalid_values_and_reserved_slugs(self):
        invalid_color = self.client.patch(self.url(), {"primary_color": "red"}, format="json")
        self.assertEqual(invalid_color.status_code, 400)
        self.assertEqual(
            self.client.patch(self.url(), {"theme_mode": "sepia"}, format="json").status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(self.url(), {"slug": "api"}, format="json").status_code,
            400,
        )
        make_company("ocupado", "Ocupado")
        self.assertEqual(
            self.client.patch(self.url(), {"slug": "OCUPADO"}, format="json").status_code,
            400,
        )

    def test_logo_upload_and_removal(self):
        upload = SimpleUploadedFile("logo.png", PNG_1PX, content_type="image/png")
        response = self.client.post(
            "/api/v1/company/branding/logo/", {"logo": upload}, format="multipart",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.company.refresh_from_db()
        self.assertTrue(self.company.logo)
        self.assertTrue(response.data["logo_url"].endswith(".png"))
        self.assertTrue(AuditEvent.objects.filter(
            company=self.company, action="company.branding_updated",
        ).exists())

        removed = self.client.delete("/api/v1/company/branding/logo/")
        self.assertEqual(removed.status_code, 200, removed.data)
        self.company.refresh_from_db()
        self.assertFalse(self.company.logo)
        self.assertEqual(removed.data["logo_url"], "")

    def test_logo_rejects_svg_and_oversized_files(self):
        svg = SimpleUploadedFile(
            "logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
            content_type="image/svg+xml",
        )
        self.assertEqual(self.client.post(
            "/api/v1/company/branding/logo/", {"logo": svg}, format="multipart",
        ).status_code, 400)

        oversized = SimpleUploadedFile(
            "big.png", b"a" * (2 * 1024 * 1024 + 1), content_type="image/png",
        )
        self.assertEqual(self.client.post(
            "/api/v1/company/branding/logo/", {"logo": oversized}, format="multipart",
        ).status_code, 400)

    def test_branding_propagates_to_company_lists_bootstrap_and_public_portal(self):
        self.company.display_name = "Salón Aurora"
        self.company.primary_color = "#00A896"
        self.company.theme_mode = "dark"
        self.company.save(update_fields=["display_name", "primary_color", "theme_mode", "updated_at"])

        mine = self.client.get("/api/v1/companies/mine/")
        self.assertEqual(mine.status_code, 200, mine.data)
        self.assertEqual(mine.data[0]["display_name"], "Salón Aurora")
        self.assertEqual(mine.data[0]["primary_color"], "#00A896")
        self.assertEqual(mine.data[0]["theme_mode"], "dark")
        self.assertIn("/b/salon-central/", mine.data[0]["booking_url"])

        bootstrap = self.client.get("/api/v1/mobile/bootstrap/")
        self.assertEqual(bootstrap.status_code, 200, bootstrap.data)
        self.assertEqual(bootstrap.data["company"]["display_name"], "Salón Aurora")
        self.assertEqual(bootstrap.data["company"]["primary_color"], "#00A896")
        self.assertEqual(bootstrap.data["company"]["theme_mode"], "dark")
        self.assertEqual(bootstrap.data["companies"][0]["display_name"], "Salón Aurora")

        public = self.client.get("/api/v1/public/salon-central/")
        self.assertEqual(public.status_code, 200, public.data)
        self.assertEqual(public.data["branding"]["display_name"], "Salón Aurora")
        self.assertEqual(public.data["branding"]["primary_color"], "#00A896")
        self.assertEqual(public.data["branding"]["theme_mode"], "dark")
        self.assertIn("/b/salon-central/", public.data["branding"]["booking_url"])

    def test_owner_admin_permission_can_be_denied(self):
        from apps.identity.models import PermissionGrant
        PermissionGrant.objects.create(
            membership=self.owner.memberships.get(company=self.company),
            permission="company.manage", effect="deny",
        )
        response = self.client.patch(self.url(), {"display_name": "Sin permiso"}, format="json")
        self.assertEqual(response.status_code, 403)
