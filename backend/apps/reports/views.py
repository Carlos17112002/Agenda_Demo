import uuid

from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.authentication import resolve_tenant
from apps.tenancy.models import Branch
from apps.tenancy.permissions import HasTenantContext, HasTenantPermission
from apps.workforce.models import WorkerProfile

from .exports import build_excel, build_pdf, export_filename
from .services import cash_summary, parse_report_date, sales_summary


class ReportView(APIView):
    permission_classes = [IsAuthenticated, HasTenantContext, HasTenantPermission]
    required_tenant_permission = "reports.read"

    def get_tenant(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            tenant = resolve_tenant(self.request, self.request.user)
        if tenant is None:
            raise PermissionDenied("Selecciona una empresa.")
        return tenant

    def get_branch(self, tenant):
        value = self.request.query_params.get("branch")
        if not value:
            return None
        try:
            branch_id = uuid.UUID(value)
        except ValueError as error:
            raise ValidationError({"branch": "Sucursal inválida."}) from error
        branch = Branch.objects.filter(pk=branch_id, company=tenant).first()
        if branch is None:
            raise ValidationError({"branch": "La sucursal no pertenece a la empresa activa."})
        return branch

    def get_worker(self, tenant):
        value = self.request.query_params.get("worker")
        if not value:
            return None
        try:
            worker_id = uuid.UUID(value)
        except ValueError as error:
            raise ValidationError({"worker": "Trabajador inválido."}) from error
        worker = (
            WorkerProfile.objects.filter(pk=worker_id, company=tenant)
            .select_related("membership")
            .first()
        )
        if worker is None:
            raise ValidationError({"worker": "El trabajador no pertenece a la empresa activa."})
        return worker

    def get_range(self):
        params = self.request.query_params
        date_from = parse_report_date(params.get("date_from"), "date_from")
        date_to = parse_report_date(params.get("date_to"), "date_to")
        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_to": "La fecha final no puede ser anterior a la inicial."})
        return date_from, date_to


class SalesSummaryView(ReportView):
    def get(self, request):
        tenant = self.get_tenant()
        branch = self.get_branch(tenant)
        worker = self.get_worker(tenant)
        date_from, date_to = self.get_range()
        return Response(sales_summary(
            company=tenant, date_from=date_from, date_to=date_to, branch=branch, worker=worker,
        ), status=status.HTTP_200_OK)


class ReportExportView(ReportView):
    def get(self, request):
        fmt = (request.query_params.get("fmt") or "pdf").lower()
        if fmt not in {"pdf", "excel"}:
            raise ValidationError({"fmt": "Usa pdf o excel."})

        tenant = self.get_tenant()
        branch = self.get_branch(tenant)
        worker = self.get_worker(tenant)
        date_from, date_to = self.get_range()

        sales = sales_summary(
            company=tenant, date_from=date_from, date_to=date_to, branch=branch, worker=worker,
        )
        cash = cash_summary(
            company=tenant, date_from=date_from, date_to=date_to, branch=branch,
        )

        if fmt == "pdf":
            content = build_pdf(company=tenant, sales=sales, cash=cash, branch=branch, worker=worker)
            content_type = "application/pdf"
            extension = "pdf"
        else:
            content = build_excel(company=tenant, sales=sales, cash=cash)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            extension = "xlsx"

        response = HttpResponse(content, content_type=content_type)
        filename = export_filename(tenant, sales, extension)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class CashSummaryView(ReportView):
    def get(self, request):
        tenant = self.get_tenant()
        branch = self.get_branch(tenant)
        date_from, date_to = self.get_range()
        return Response(cash_summary(
            company=tenant, date_from=date_from, date_to=date_to, branch=branch,
        ), status=status.HTTP_200_OK)
