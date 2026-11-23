from django.test import TestCase

from apps.identity.models import Membership
from apps.tenancy.models import Branch
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)
from apps.workforce.models import BlockedSlot, Break, TimeOff, WorkerProfile, WorkingHours


class WorkforceApiTests(TestCase):
    def setUp(self):
        self.company = make_company("empresa-a", "Empresa A")
        self.other_company = make_company("empresa-b", "Empresa B")
        self.owner = make_user("owner@example.com")
        make_membership(self.owner, self.company, Membership.Role.OWNER)
        self.staff_user = make_user("staff@example.com")
        self.staff_membership = make_membership(self.staff_user, self.company, Membership.Role.WORKER)
        self.outsider = make_user("outsider@example.com")
        make_membership(self.outsider, self.other_company, Membership.Role.OWNER)
        self.client = tenant_client(self.owner, make_context(self.owner, self.company))
        self.branch = Branch.objects.create(company=self.company, name="Centro", code="CENTRO")
        self.foreign_branch = Branch.objects.create(company=self.other_company, name="Otra", code="OTRA")

    def _create_worker(self, client=None, **overrides):
        payload = {"first_name": "Carla", "last_name": "Rojas", "job_title": "Estilista",
                   "branches": [str(self.branch.id)], **overrides}
        return (client or self.client).post("/api/v1/workers/", payload, format="json")

    def _worker(self, **overrides):
        response = self._create_worker(**overrides)
        self.assertEqual(response.status_code, 201, response.data)
        return WorkerProfile.objects.get(pk=response.data["id"])

    def test_worker_creation_is_scoped_to_company_and_branch(self):
        worker = self._worker()
        self.assertEqual(worker.company, self.company)
        self.assertEqual(list(worker.branches.all()), [self.branch])
        response = self._create_worker(branches=[str(self.foreign_branch.id)])
        self.assertEqual(response.status_code, 400)

    def test_worker_membership_must_belong_to_same_company(self):
        response = self._create_worker(membership=str(self.staff_membership.id))
        self.assertEqual(response.status_code, 201, response.data)
        foreign_membership = Membership.objects.filter(company=self.other_company).first()
        response = self._create_worker(membership=str(foreign_membership.id))
        self.assertEqual(response.status_code, 400)

    def test_worker_role_cannot_manage_workers(self):
        staff_client = tenant_client(self.staff_user, make_context(self.staff_user, self.company))
        self.assertEqual(self._create_worker(client=staff_client).status_code, 403)

    def test_working_hours_validation_and_overlap(self):
        worker = self._worker()
        payload = {"worker": str(worker.id), "branch": str(self.branch.id), "weekday": 0,
                   "start_time": "09:00", "end_time": "13:00"}
        response = self.client.post("/api/v1/working-hours/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        overlap = {**payload, "start_time": "12:00", "end_time": "15:00"}
        self.assertEqual(self.client.post("/api/v1/working-hours/", overlap, format="json").status_code, 400)
        invalid = {**payload, "start_time": "18:00", "end_time": "10:00"}
        self.assertEqual(self.client.post("/api/v1/working-hours/", invalid, format="json").status_code, 400)

    def test_working_hours_cannot_use_foreign_worker_or_branch(self):
        worker = self._worker()
        response = self.client.post("/api/v1/working-hours/", {
            "worker": str(worker.id), "branch": str(self.foreign_branch.id), "weekday": 1,
            "start_time": "09:00", "end_time": "10:00",
        }, format="json")
        # The branch-scoped permission check rejects before payload validation.
        self.assertIn(response.status_code, {400, 403})
        foreign_worker = WorkerProfile.objects.create(company=self.other_company, first_name="Ajeno")
        response = self.client.post("/api/v1/working-hours/", {
            "worker": str(foreign_worker.id), "branch": str(self.branch.id), "weekday": 1,
            "start_time": "09:00", "end_time": "10:00",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_working_hours_list_is_tenant_scoped(self):
        worker = self._worker()
        WorkingHours.objects.create(company=self.company, worker=worker, branch=self.branch,
                                    weekday=0, start_time="09:00", end_time="13:00")
        other_worker = WorkerProfile.objects.create(company=self.other_company, first_name="Otro")
        WorkingHours.objects.create(company=self.other_company, worker=other_worker,
                                    branch=self.foreign_branch, weekday=0,
                                    start_time="09:00", end_time="13:00")
        response = self.client.get("/api/v1/working-hours/", {"worker": str(worker.id)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_time_off_requires_valid_range_and_ownership(self):
        worker = self._worker()
        base = {"worker": str(worker.id), "starts_at": "2026-12-01T09:00:00Z",
                "ends_at": "2026-12-01T12:00:00Z", "reason": "Médico"}
        self.assertEqual(self.client.post("/api/v1/time-off/", base, format="json").status_code, 201)
        invalid = {**base, "ends_at": "2026-12-01T08:00:00Z"}
        self.assertEqual(self.client.post("/api/v1/time-off/", invalid, format="json").status_code, 400)
        foreign_worker = WorkerProfile.objects.create(company=self.other_company, first_name="Ajeno")
        response = self.client.post("/api/v1/time-off/", {
            "worker": str(foreign_worker.id), "starts_at": "2026-12-02T09:00:00Z",
            "ends_at": "2026-12-02T10:00:00Z",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_destroy_deactivates_worker(self):
        worker = self._worker()
        response = self.client.delete(f"/api/v1/workers/{worker.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(WorkerProfile.objects.get(pk=worker.pk).active)

    def test_break_validates_overlap_and_tenant(self):
        worker = self._worker()
        payload = {"worker": str(worker.id), "branch": str(self.branch.id), "weekday": 0,
                   "start_time": "09:30", "end_time": "10:00", "label": "Café"}
        response = self.client.post("/api/v1/breaks/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        overlap = {**payload, "start_time": "09:45", "end_time": "10:15"}
        self.assertEqual(self.client.post("/api/v1/breaks/", overlap, format="json").status_code, 400)
        invalid = {**payload, "start_time": "11:00", "end_time": "10:30"}
        self.assertEqual(self.client.post("/api/v1/breaks/", invalid, format="json").status_code, 400)
        foreign_worker = WorkerProfile.objects.create(company=self.other_company, first_name="Ajeno")
        response = self.client.post("/api/v1/breaks/", {
            "worker": str(foreign_worker.id), "branch": str(self.branch.id), "weekday": 1,
            "start_time": "09:30", "end_time": "10:00",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/v1/breaks/", {
            "worker": str(worker.id), "branch": str(self.foreign_branch.id), "weekday": 1,
            "start_time": "09:30", "end_time": "10:00",
        }, format="json")
        self.assertIn(response.status_code, {400, 403})

    def test_blocked_slot_validates_range_and_tenant(self):
        worker = self._worker()
        payload = {"worker": str(worker.id), "branch": str(self.branch.id),
                   "starts_at": "2026-12-03T09:00:00Z", "ends_at": "2026-12-03T10:00:00Z",
                   "reason": "Reunión"}
        response = self.client.post("/api/v1/blocked-slots/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        invalid = {**payload, "ends_at": "2026-12-03T08:30:00Z"}
        self.assertEqual(self.client.post("/api/v1/blocked-slots/", invalid, format="json").status_code, 400)
        foreign_worker = WorkerProfile.objects.create(company=self.other_company, first_name="Ajeno")
        response = self.client.post("/api/v1/blocked-slots/", {
            "worker": str(foreign_worker.id), "starts_at": "2026-12-04T09:00:00Z",
            "ends_at": "2026-12-04T10:00:00Z",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(BlockedSlot.objects.count(), 1)
