from allauth.account.signals import email_confirmed
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from apps.commandes.models import Cart

User = get_user_model()

@receiver(email_confirmed)
def mark_user_verified(request, email_address, **kwargs):
    user = email_address.user

    if not user.is_verified:
        user.is_verified = True
        user.save(update_fields=["is_verified"])


@receiver(post_save, sender=User)
def create_user_cart(sender, instance, created, **kwargs):
    """
    Crée automatiquement un panier (Cart) pour chaque nouvel utilisateur.
    """
    if created:
        Cart.objects.get_or_create(user=instance)