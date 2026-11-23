from datetime import timedelta
from uuid import uuid4
from django.test import TestCase, RequestFactory
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient
from apps.identity.models import Membership, PermissionGrant, User
from apps.tenancy.middleware import TenantContextMiddleware
from apps.tenancy.mixins import TenantQuerysetMixin
from apps.tenancy.models import Branch, Company, TenantContext
from apps.tenancy.permissions import HasTenantContext, HasTenantPermission

class TenantIsolationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", email="ana@example.com", password="Correct-horse-123")
        self.other = User.objects.create_user(username="bob", email="bob@example.com", password="Correct-horse-123")
        self.company_a = Company.objects.create(name="A", slug="empresa-a")
        self.company_b = Company.objects.create(name="B", slug="empresa-b")
        self.membership = Membership.objects.create(user=self.user, company=self.company_a, role=Membership.Role.OWNER)
        self.branch_a = Branch.objects.create(company=self.company_a, name="Centro", code="CENTRO")
        self.branch_b = Branch.objects.create(company=self.company_b, name="Centro", code="CENTRO")
        self.context = TenantContext.objects.create(user=self.user, company=self.company_a,
            expires_at=timezone.now() + timedelta(hours=1))
        self.client = APIClient()
        response = self.client.post("/api/v1/auth/token/", {"email": "ana@example.com", "password": "Correct-horse-123"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_user_only_lists_companies_with_active_membership(self):
        Membership.objects.create(user=self.user, company=self.company_b, active=False)
        response = self.client.get("/api/v1/companies/mine/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [str(self.company_a.id)])

    def test_context_creation_rejects_other_users_company(self):
        response = self.client.post("/api/v1/tenant-contexts/", {"company": str(self.company_b.id)}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_context_cannot_be_reused_by_another_user(self):
        request = RequestFactory().get("/private/", HTTP_X_TENANT_CONTEXT=str(self.context.id))
        request.user = self.other
        response = TenantContextMiddleware(lambda req: req.tenant)(request)
        self.assertIsNone(response)

    def test_context_expires_and_membership_revocation_takes_effect_immediately(self):
        request = RequestFactory().get("/private/", HTTP_X_TENANT_CONTEXT=str(self.context.id))
        request.user = self.user
        self.assertEqual(TenantContextMiddleware(lambda req: req.tenant)(request), self.company_a)
        self.membership.active = False
        self.membership.save(update_fields=["active"])
        self.assertIsNone(TenantContextMiddleware(lambda req: req.tenant)(request))
        self.membership.active = True
        self.membership.save(update_fields=["active"])
        self.context.expires_at = timezone.now() - timedelta(seconds=1)
        self.context.save(update_fields=["expires_at"])
        self.assertIsNone(TenantContextMiddleware(lambda req: req.tenant)(request))

    def test_suspended_company_cannot_be_selected(self):
        self.company_a.status = Company.Status.SUSPENDED
        self.company_a.save(update_fields=["status"])
        request = RequestFactory().get("/private/", HTTP_X_TENANT_CONTEXT=str(self.context.id))
        request.user = self.user
        self.assertIsNone(TenantContextMiddleware(lambda req: req.tenant)(request))

    def test_server_owned_tenant_field_is_not_writable(self):
        from apps.tenancy.serializers import BranchSerializer
        serializer = BranchSerializer(data={"name": "otra", "code": "X", "company": str(self.company_b.id)})
        self.assertFalse(serializer.is_valid())
        self.assertIn("company", serializer.errors)

    def test_queryset_mixin_filters_to_current_company(self):
        class BranchSerializer(serializers.ModelSerializer):
            class Meta:
                model = Branch
                fields = ["id", "company", "name", "code"]
        class BaseView:
            request = type("Request", (), {"tenant": self.company_a})()
            def get_queryset(inner_self):
                return Branch.objects.all()
        class ScopedView(TenantQuerysetMixin, BaseView):
            pass
        self.assertEqual(list(ScopedView().get_queryset()), [self.branch_a])

    def test_queryset_mixin_fails_closed_without_tenant(self):
        class BaseView:
            request = type("Request", (), {"tenant": None})()
            def get_queryset(inner_self):
                return Branch.objects.all()
        class ScopedView(TenantQuerysetMixin, BaseView):
            pass
        with self.assertRaises(PermissionDenied):
            ScopedView().get_queryset()

    def test_explicit_deny_overrides_role_and_allow(self):
        grant = PermissionGrant.objects.create(membership=self.membership, permission="inventory.write", effect="deny")
        request = RequestFactory().get("/")
        request.user, request.tenant = self.user, self.company_a
        view = type("View", (), {"required_tenant_permission": "inventory.write", "kwargs": {}})()
        self.assertFalse(HasTenantPermission().has_permission(request, view))
        grant.effect = "allow"
        grant.save(update_fields=["effect"])
        self.assertTrue(HasTenantPermission().has_permission(request, view))

    def test_global_deny_applies_when_payload_selects_a_branch(self):
        PermissionGrant.objects.create(
            membership=self.membership, permission="sales.write", effect="deny",
        )
        request = type("Request", (), {
            "user": self.user, "tenant": self.company_a,
            "data": {"branch": str(self.branch_a.id)},
        })()
        view = type("View", (), {"required_tenant_permission": "sales.write", "kwargs": {}})()
        self.assertFalse(HasTenantPermission().has_permission(request, view))

    def test_context_endpoint_only_returns_active_user_context(self):
        response = self.client.get("/api/v1/tenant-contexts/current/", HTTP_X_TENANT_CONTEXT=str(self.context.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["company"]), str(self.company_a.id))
        response = self.client.get("/api/v1/tenant-contexts/current/", HTTP_X_TENANT_CONTEXT=str(uuid4()))
        self.assertEqual(response.status_code, 404)

    def test_branch_api_filters_and_creates_only_in_current_company(self):
        headers = {"HTTP_X_TENANT_CONTEXT": str(self.context.id)}
        response = self.client.get("/api/v1/branches/", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["results"]], [str(self.branch_a.id)])
        response = self.client.post("/api/v1/branches/", {"name": "Nueva", "code": "NUEVA",
            "company": str(self.company_b.id)}, format="json", **headers)
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/v1/branches/", {"name": "Nueva", "code": "NUEVA"}, format="json", **headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(response.data["company"]), str(self.company_a.id))

    def test_permission_grant_api_requires_admin_and_scopes_memberships(self):
        headers = {"HTTP_X_TENANT_CONTEXT": str(self.context.id)}
        response = self.client.get("/api/v1/permission-grants/", **headers)
        self.assertEqual(response.status_code, 200)
        self.client.post("/api/v1/tenant-contexts/", {"company": str(self.company_b.id)}, format="json")
        response = self.client.post("/api/v1/permission-grants/", {"membership": str(self.membership.id),
            "permission": "inventory.write", "effect": "allow", "branch": str(self.branch_b.id)}, format="json", **headers)
        self.assertEqual(response.status_code, 400)

    def test_unselected_tenant_is_rejected_for_business_endpoints(self):
        response = self.client.get("/api/v1/branches/")
        self.assertEqual(response.status_code, 403)

    def test_company_registration_atomically_creates_owner_and_membership(self):
        response = APIClient().post("/api/v1/auth/register-company/", {
            "company_name": "Nuevo negocio", "slug": "nuevo-negocio", "email": "owner@example.com",
            "password": "Strong-Horse-Battery-483!", "first_name": "Dueña"
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        company = Company.objects.get(pk=response.data["company_id"])
        membership = Membership.objects.get(company=company)
        self.assertEqual(membership.role, Membership.Role.OWNER)
        self.assertEqual(membership.user.email, "owner@example.com")
        self.assertTrue(membership.user.check_password("Strong-Horse-Battery-483!"))

    def test_company_registration_rejects_duplicate_email_and_short_password(self):
        client = APIClient()
        payload = {"company_name": "Otro", "slug": "otro-negocio", "email": "ana@example.com",
            "password": "Weak", "first_name": ""}
        response = client.post("/api/v1/auth/register-company/", payload, format="json")
        self.assertEqual(response.status_code, 400)
