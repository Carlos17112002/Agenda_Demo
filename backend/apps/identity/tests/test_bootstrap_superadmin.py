import os
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.identity.models import User

FAST_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SUPERADMIN_ENV = {
    "AGENDA_SUPERADMIN_EMAIL": "jefe@agenda.app",
    "AGENDA_SUPERADMIN_PASSWORD": "Clave-Fuerte-2026!",
}


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class BootstrapSuperadminTests(TestCase):
    def test_creates_superadmin_when_missing(self):
        with mock.patch.dict(os.environ, SUPERADMIN_ENV):
            call_command("bootstrap_superadmin", verbosity=0)

        user = User.objects.get(email="jefe@agenda.app")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(SUPERADMIN_ENV["AGENDA_SUPERADMIN_PASSWORD"]))

    def test_does_not_overwrite_existing_user(self):
        existing = User.objects.create_user(
            email="jefe@agenda.app", username="jefe", password="Otra-Clave-2026!",
        )
        with mock.patch.dict(os.environ, SUPERADMIN_ENV):
            call_command("bootstrap_superadmin", verbosity=0)

        existing.refresh_from_db()
        self.assertTrue(existing.check_password("Otra-Clave-2026!"))
        self.assertFalse(existing.is_superuser)
        self.assertEqual(User.objects.filter(email="jefe@agenda.app").count(), 1)

    def test_does_nothing_without_environment_variables(self):
        env = {"AGENDA_SUPERADMIN_EMAIL": "", "AGENDA_SUPERADMIN_PASSWORD": ""}
        with mock.patch.dict(os.environ, env):
            call_command("bootstrap_superadmin", verbosity=0)

        self.assertEqual(User.objects.count(), 0)
