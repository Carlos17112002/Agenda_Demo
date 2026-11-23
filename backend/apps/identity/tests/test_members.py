from django.test import TestCase

from apps.identity.models import Membership, PermissionGrant, User
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)
from apps.workforce.models import WorkerProfile

PASSWORD = "Correct-Horse-Battery-983!"


class MembershipModelTests(TestCase):
    def test_membership_can_point_to_a_default_branch(self):
        company = make_company("members-model", "Modelo")
        user = User.objects.create_user(
            username="model@example.com", email="model@example.com", password=PASSWORD,
        )
        branch = Branch.objects.create(company=company, name="Centro", code="CEN")

        membership = Membership.objects.create(
            company=company, user=user, default_branch=branch,
        )

        membership.refresh_from_db()
        self.assertEqual(membership.default_branch, branch)

    def test_new_users_do_not_require_password_change(self):
        user = User.objects.create_user(
            username="flag@example.com", email="flag@example.com", password=PASSWORD,
        )
        self.assertFalse(user.must_change_password)


class MembersApiTests(TestCase):
    def setUp(self):
        self.company = make_company("members-api", "Miembros API")
        self.owner = make_user("owner-members@example.com")
        self.owner_membership = make_membership(self.owner, self.company, Membership.Role.OWNER)
        self.client = tenant_client(self.owner, make_context(self.owner, self.company))
        self.branch = Branch.objects.create(company=self.company, name="Centro", code="CEN")
        self.other_company = make_company("members-foreign", "Ajena")
        self.foreign_branch = Branch.objects.create(
            company=self.other_company, name="Ajena", code="AJN",
        )

    def _admin_client(self):
        user = make_user("admin-members@example.com")
        make_membership(user, self.company, Membership.Role.ADMIN)
        return tenant_client(user, make_context(user, self.company))

    def _create_member(self, **overrides):
        payload = {
            "email": "nuevo@example.com",
            "first_name": "Nueva",
            "last_name": "Persona",
            "role": "reception",
            "default_branch": str(self.branch.id),
        }
        payload.update(overrides)
        return self.client.post("/api/v1/members/", payload, format="json")

    def test_lists_only_members_of_the_active_company(self):
        foreign_user = make_user("foreign@example.com")
        make_membership(foreign_user, self.other_company)

        response = self.client.get("/api/v1/members/")

        self.assertEqual(response.status_code, 200)
        emails = [row["email"] for row in response.data["results"]]
        self.assertEqual(emails, [self.owner.email])

    def test_owner_updates_role_and_default_branch(self):
        target = make_user("target@example.com")
        membership = make_membership(target, self.company, Membership.Role.RECEPTION)
        other_branch = Branch.objects.create(company=self.company, name="Norte", code="NOR")

        response = self.client.patch(
            f"/api/v1/members/{membership.id}/",
            {"role": "manager", "default_branch": str(other_branch.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        membership.refresh_from_db()
        self.assertEqual(membership.role, Membership.Role.MANAGER)
        self.assertEqual(membership.default_branch, other_branch)

    def test_foreign_branch_is_rejected_on_update(self):
        target = make_user("target-foreign@example.com")
        membership = make_membership(target, self.company, Membership.Role.RECEPTION)

        response = self.client.patch(
            f"/api/v1/members/{membership.id}/",
            {"default_branch": str(self.foreign_branch.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("default_branch", response.data)

    def test_admin_cannot_modify_an_owner(self):
        response = self._admin_client().patch(
            f"/api/v1/members/{self.owner_membership.id}/",
            {"first_name": "Hack"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_deactivation_is_soft_and_keeps_the_user_active(self):
        target = make_user("soft@example.com")
        membership = make_membership(target, self.company, Membership.Role.RECEPTION)

        response = self.client.delete(f"/api/v1/members/{membership.id}/")

        self.assertEqual(response.status_code, 204)
        membership.refresh_from_db()
        target.refresh_from_db()
        self.assertFalse(membership.active)
        self.assertTrue(target.is_active)

    def test_owner_cannot_deactivate_self_when_another_owner_exists(self):
        second = make_user("owner-two@example.com")
        make_membership(second, self.company, Membership.Role.OWNER)

        response = self.client.delete(f"/api/v1/members/{self.owner_membership.id}/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("active", response.data)

    def test_last_owner_cannot_be_deactivated(self):
        response = self.client.delete(f"/api/v1/members/{self.owner_membership.id}/")

        self.assertEqual(response.status_code, 400)
        self.assertIn("active", response.data)
        self.owner_membership.refresh_from_db()
        self.assertTrue(self.owner_membership.active)

    def test_last_owner_cannot_be_demoted(self):
        response = self.client.patch(
            f"/api/v1/members/{self.owner_membership.id}/",
            {"role": "admin"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.data)
        self.owner_membership.refresh_from_db()
        self.assertEqual(self.owner_membership.role, Membership.Role.OWNER)

    def test_permission_grants_can_be_filtered_by_membership(self):
        target = make_user("target-grants@example.com")
        target_membership = make_membership(target, self.company, Membership.Role.RECEPTION)
        PermissionGrant.objects.create(
            membership=target_membership, permission="bookings.write", effect="deny",
        )
        PermissionGrant.objects.create(
            membership=self.owner_membership, permission="bookings.read", effect="allow",
        )

        response = self.client.get(
            "/api/v1/permission-grants/", {"membership": str(target_membership.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["permission"], "bookings.write")

    def test_grants_reject_memberships_from_another_tenant(self):
        make_membership(self.owner, self.other_company, Membership.Role.OWNER)
        foreign_user = make_user("foreign-grant@example.com")
        foreign_membership = make_membership(foreign_user, self.other_company)

        response = self.client.post("/api/v1/permission-grants/", {
            "membership": str(foreign_membership.id),
            "permission": "bookings.read",
            "effect": "allow",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("membership", response.data)

    def test_grants_reject_unknown_permissions(self):
        target = make_user("unknown-perm@example.com")
        membership = make_membership(target, self.company, Membership.Role.RECEPTION)

        response = self.client.post("/api/v1/permission-grants/", {
            "membership": str(membership.id),
            "permission": "nope.nope",
            "effect": "allow",
        }, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("permission", response.data)

    def test_owner_creates_member_with_branch_and_temporary_password(self):
        response = self._create_member(email="creada@example.com")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["temporary_password"])
        user = User.objects.get(email="creada@example.com")
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.check_password(response.data["temporary_password"]))
        self.assertEqual(response.data["member"]["default_branch"]["id"], str(self.branch.id))

    def test_duplicate_email_is_rejected(self):
        self._create_member(email="repetida@example.com")

        response = self._create_member(email="repetida@example.com")

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_foreign_branch_is_rejected_on_create(self):
        response = self._create_member(default_branch=str(self.foreign_branch.id))

        self.assertEqual(response.status_code, 400)
        self.assertIn("default_branch", response.data)

    def test_admin_cannot_assign_owner_role(self):
        response = self._admin_client().post(
            "/api/v1/members/",
            {"email": "owner2@example.com", "role": "owner"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.data)

    def test_worker_profile_is_created_with_the_default_branch(self):
        response = self._create_member(
            email="worker-new@example.com", role="worker", create_worker_profile=True,
            first_name="Wanda",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNotNone(response.data["worker_profile"])
        worker = WorkerProfile.objects.get(membership__user__email="worker-new@example.com")
        self.assertEqual(worker.company, self.company)
        self.assertEqual(list(worker.branches.all()), [self.branch])

    def test_worker_profile_requires_worker_role(self):
        response = self._create_member(
            email="reception-worker@example.com", role="reception", create_worker_profile=True,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("create_worker_profile", response.data)
