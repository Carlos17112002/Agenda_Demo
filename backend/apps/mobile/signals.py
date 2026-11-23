from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.inventory.models import InventoryMovement

from .push import push_low_stock_event


@receiver(post_save, sender=InventoryMovement, dispatch_uid="mobile_low_stock_push")
def notify_low_stock(sender, instance, created, **kwargs):
    if created:
        push_low_stock_event(instance)
