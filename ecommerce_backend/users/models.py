

from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone  # Ajout de l'import manquant pour timezone.now()
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from allauth.account.models import EmailAddress

from .managers import UserManager


class User(AbstractUser):

    class UserRole(models.TextChoices):
        PLATFORM_ADMIN = "platform_admin", _("Platform Admin")
        CUSTOMER = "customer", _("Customer")

    username = None

    first_name = None
    
    last_name = None

    email = models.EmailField(
        unique=True
    )

    name = models.CharField(
        max_length=255,
        blank=True
    )

    role = models.CharField(
        max_length=30,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER
    )

    phone_number = models.CharField(
        max_length=30,
        blank=True
    )

    profile_image = models.ImageField(
        upload_to="users/profiles/",
        blank=True,
        null=True
    )

    is_verified = models.BooleanField(
        default=False
        # Retrait de null=True, blank=True : inutile pour un booléen avec un default=False
    )

    # Correction de l'indentation
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # is_active est déjà présent dans AbstractUser, mais on peut le garder pour être explicite
    is_active = models.BooleanField(
        default=True
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    class Meta:
        # abstract = True  <-- SUPPRIMÉ : Un modèle utilisateur personnalisé doit être concret pour être créé dans la base de données !
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save()

    @property
    def is_deleted(self):
        # CORRIGÉ : La méthode était vide/inachevée
        return self.deleted_at is not None

    @property
    def email_verified(self):
        return EmailAddress.objects.filter(
            user=self,
            verified=True,
        ).exists()

    def get_absolute_url(self):
        return reverse(
            "users:detail",
            kwargs={"pk": self.pk}
        )