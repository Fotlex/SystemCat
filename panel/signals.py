from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from .models import StartOrder


@receiver(post_save, sender=StartOrder)
def mailing_post_save(sender, instance: StartOrder, created, **kwargs):
    from .tasks import send_first_message

    if created:
        transaction.on_commit(lambda: send_first_message.apply_async(args=[instance.id]))
