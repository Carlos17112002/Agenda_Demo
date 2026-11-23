from rest_framework.permissions import BasePermission


class IsSaasAdmin(BasePermission):
    message = "Se requiere acceso al panel SaaS."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user and user.is_authenticated
            and (user.is_saas_admin or user.is_superuser)
        )
