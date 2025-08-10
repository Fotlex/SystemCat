from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Order, OrderAssignmentLog

@receiver(pre_save, sender=Order)
def update_order_timestamps(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        old_order = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return

    if old_order.status != instance.status:
        if instance.status == 'completed':
            instance.completed_at = timezone.now()
        
        
@receiver(pre_save, sender=Order)
def track_assignment_change(sender, instance, **kwargs):
    if not instance.pk:
        if instance.responsible_employee:
            pass
        return

    try:
        old_order = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return

    if old_order.responsible_employee != instance.responsible_employee and instance.responsible_employee is not None:
        OrderAssignmentLog.objects.create(
            order=instance,
            employee=instance.responsible_employee
        )



@receiver(post_save, sender=Order)
def track_initial_assignment(sender, instance, created, **kwargs):
    if created and instance.responsible_employee:
        OrderAssignmentLog.objects.create(
            order=instance,
            employee=instance.responsible_employee
        )
        
        
@receiver(pre_save, sender=Order)
def track_order_status_dates(sender, instance, **kwargs):
    if not instance.pk:
        if instance.status == 'sent_to_workshop':
            instance.work_place_at = timezone.now()
        if instance.status == 'sent_to_size':
            instance.size_at = timezone.now()
        return

    try:
        old_instance = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return


    old_status = old_instance.status
    new_status = instance.status


    if new_status == 'take_size' and old_status != 'take_size' and not instance.size_at:
        instance.size_at = timezone.now()
        
    if new_status == 'sent_to_workshop' and old_status != 'sent_to_workshop' and not instance.work_place_at:
        instance.work_place_at = timezone.now()
        
    if new_status == 'workshop_completed' and old_status != 'workshop_completed' and not instance.work_place_at_end:
        instance.work_place_at_end = timezone.now()
        
    if new_status == 'measurement_added' and old_status != 'measurement_added' and not instance.size_at_end:
        instance.size_at_end = timezone.now()
        
