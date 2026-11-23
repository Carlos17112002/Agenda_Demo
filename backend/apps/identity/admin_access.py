def has_saas_access(user):
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_superuser or getattr(user, "is_saas_admin", False))
