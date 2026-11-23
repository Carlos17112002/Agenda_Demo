from django.test import TestCase

from apps.tenancy.models import Company

from .utils import BookingScenarioMixin, local_dt


class PublicBookingPageTests(BookingScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()
        self.company.display_name = "Estudio Aurora"
        self.company.primary_color = "#00A896"
        self.company.secondary_color = "#028090"
        self.company.save()
        self.path = f"/b/{self.company.slug}/"

    def test_page_renders_branding_and_public_endpoints(self):
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"].split(";")[0], "text/html")
        self.assertContains(response, "Estudio Aurora")
        self.assertContains(response, "--brand:#00A896")
        self.assertContains(response, 'data-theme="light"')
        self.assertContains(response, f'data-company-url="/api/v1/public/{self.company.slug}/"')
        self.assertContains(response, f'data-bookings-url="/api/v1/public/{self.company.slug}/bookings/"')
        self.assertContains(response, 'id="booking-app"')
        self.assertContains(response, "Corte")

    def test_page_hides_unavailable_companies(self):
        self.assertEqual(self.client.get("/b/no-existe/").status_code, 404)
        self.company.status = Company.Status.SUSPENDED
        self.company.save(update_fields=["status"])
        self.assertEqual(self.client.get(self.path).status_code, 404)

    def test_page_escapes_tenant_supplied_names(self):
        self.company.display_name = "<script>alert('marca')</script>"
        self.company.save(update_fields=["display_name"])

        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>alert('marca')</script>")
        self.assertContains(response, "&lt;script&gt;alert(&#x27;marca&#x27;)&lt;/script&gt;")

    def test_reservation_deep_link_exposes_public_code(self):
        booking = self.client.post(
            f"/api/v1/public/{self.company.slug}/bookings/",
            {
                "branch": str(self.branch.id), "service": str(self.service.id),
                "worker": str(self.worker.id),
                "start_at": local_dt(self.day, 10).isoformat(),
                "first_name": "María", "last_name": "López",
                "email": "maria-page@example.com", "phone": "+56911111111",
            },
            format="json",
        )
        self.assertEqual(booking.status_code, 201, booking.data)

        response = self.client.get(f"{self.path}reserva/{booking.data['public_code']}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-initial-code="{booking.data["public_code"]}"')
        self.assertContains(
            response,
            f'data-detail-base="/api/v1/public/{self.company.slug}/bookings/CODE/"',
        )

    def test_page_uses_default_identity_when_no_branding_is_set(self):
        bare = Company.objects.create(name="Sin Marca", slug="sin-marca")
        response = self.client.get(f"/b/{bare.slug}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sin Marca")
        self.assertContains(response, "--brand:#E50914")
        self.assertContains(response, "--brand-dark:#8B0000")
        self.assertContains(response, 'data-theme="light"')

    def test_page_follows_company_theme_mode(self):
        self.company.theme_mode = Company.ThemeMode.DARK
        self.company.save(update_fields=["theme_mode"])
        response = self.client.get(self.path)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-theme="dark"')
