SYNC_RESOURCES = {
    "branches": {"permissions": ("branches.read",), "feature": None},
    "services": {"permissions": ("catalog.read",), "feature": "catalog"},
    "workers": {"permissions": ("workforce.read",), "feature": "workforce"},
    "customers": {"permissions": ("customers.read",), "feature": "customers"},
    "bookings": {
        "permissions": ("bookings.read", "bookings.own.read"),
        "feature": "bookings",
    },
    "products": {"permissions": ("inventory.read",), "feature": "inventory"},
    "categories": {"permissions": ("inventory.read",), "feature": "inventory"},
    "suppliers": {"permissions": ("inventory.read",), "feature": "inventory"},
    "documents": {"permissions": ("inventory.read",), "feature": "inventory"},
    "warehouses": {"permissions": ("inventory.read",), "feature": "inventory"},
    "stock": {"permissions": ("inventory.read",), "feature": "inventory"},
    "movements": {"permissions": ("inventory.read",), "feature": "inventory"},
}


def available_resources(permissions, features):
    granted = set(permissions)
    return sorted(
        name for name, config in SYNC_RESOURCES.items()
        if any(permission in granted for permission in config["permissions"])
        and (config["feature"] is None or features.get(config["feature"], False))
    )
