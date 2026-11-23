import uuid

from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy.authentication import resolve_tenant
from apps.tenancy.models import Branch
from apps.tenancy.permissions import HasTenantContext, HasTenantPermission

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
        date_from, date_to = self.get_range()
        return Response(sales_summary(
            company=tenant, date_from=date_from, date_to=date_to, branch=branch,
        ), status=status.HTTP_200_OK)


class CashSummaryView(ReportView):
    def get(self, request):
        tenant = self.get_tenant()
        branch = self.get_branch(tenant)
        date_from, date_to = self.get_range()
        return Response(cash_summary(
            company=tenant, date_from=date_from, date_to=date_to, branch=branch,
        ), status=status.HTTP_200_OK)
