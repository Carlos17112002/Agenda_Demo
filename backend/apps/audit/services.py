from .models import AuditEvent


def record_event(*, company, actor, action, instance, metadata=None):
    return AuditEvent.objects.create(
        company=company,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        entity_type=instance._meta.label,
        entity_id=str(instance.pk),
        metadata=metadata or {},
    )
