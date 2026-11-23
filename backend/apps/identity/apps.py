from django.apps import AppConfig

class IdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.identity"

    def ready(self):
        from django.contrib import admin

        from . import signals  # noqa: F401  (registra el logging de accesos fallidos)

        admin.site.site_header = "AGENDA · Administración"
        admin.site.site_title = "AGENDA"
        admin.site.index_title = "Administración interna"
