"""
Services métier du module users.

Note : la vérification d'email est câblée en production via le signal
``mark_user_verified`` de ``ecommerce_backend.users.signals`` (branché sur
``allauth.account.signals.email_confirmed``). Ce module n'expose que des
helpers réutilisables, sans effet de bord à l'import.

L'ancien contenu de ce fichier exécutait du code au niveau module en
référençant des noms inexistants (`request`, `receiver`, `email_confirmed`) :
tout import réel levait NameError. Il est ici réécrit sous une forme sûre.
"""

from allauth.account.models import EmailAddress


def is_email_verified(user) -> bool:
    """Indique si l'utilisateur possède au moins une adresse email vérifiée."""
    return EmailAddress.objects.filter(user=user, verified=True).exists()


def mark_user_verified(user) -> None:
    """
    Marque un utilisateur comme vérifié.

    Idempotent : ne réécrit pas si le drapeau est déjà positionné, afin de ne
    pas déclencher inutilement les signaux post_save de l'utilisateur.
    """
    if not user.is_verified:
        user.is_verified = True
        user.save(update_fields=["is_verified"])
