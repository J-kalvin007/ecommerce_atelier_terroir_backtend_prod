from django.db import models
from django.conf import settings
from apps.core.models import BaseModel
from apps.commandes.models import Order

class FraisLivraison(BaseModel):
    """
    Table pour gerer les frais de livraison par defaut pour 1Km dynamiquement par l'admin
    """
    prix_livraison = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    coordonnee_admin = models.CharField(
        max_length=255, 
        default="6.137482, 1.212820", 
        help_text="Coordonnées GPS (latitude, longitude) de l'admin. Par défaut: Lomé."
    )

    class Meta:
        db_table = "livraisons_frais"
        verbose_name = "Frais de livraison"
        verbose_name_plural = "Frais de livraison"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["prix_livraison"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"Prix par Km: {self.prix_livraison}"


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    ASSIGNED = "assigned", "Assignée"
    IN_TRANSIT = "in_transit", "En transit"
    DELIVERED = "delivered", "Livrée"
    CANCELLED = "cancelled", "Annulée"


class Delivery(BaseModel):
    """
    Suivi d'une livraison individuelle pour une commande spécifique.
    """
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="delivery"
    )

    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True
    )

    delivery_address = models.TextField(blank=True)
    
    tracking_number = models.CharField(max_length=100, blank=True)
    
    delivery_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries_handled",
        help_text="L'utilisateur (livreur) en charge de cette livraison."
    )

    livreur = models.ForeignKey(
        "Livreur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
        verbose_name="Livreur assigné",
        help_text="Le profil livreur assigné à cette livraison."
    )

    estimated_delivery_date = models.DateTimeField(null=True, blank=True)
    
    actual_delivery_date = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_deliveries",
        help_text="L'utilisateur qui a créé cette livraison."
    )

    class Meta:
        db_table = "livraisons_delivery"
        verbose_name = "Livraison"
        verbose_name_plural = "Livraisons"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"Livraison {self.id} pour Cmd {self.order.reference}"


# ─────────────────────────────────────────────────────────────────────────────
# LIVREUR
# ─────────────────────────────────────────────────────────────────────────────

class TypeVehicule(models.TextChoices):
    """Types de véhicules disponibles pour les livreurs."""
    MOTO = "moto", "Moto"
    TRICYCLE = "tricycle", "Tricycle"
    VOITURE = "voiture", "Voiture"
    CAMIONNETTE = "camionnette", "Camionnette"
    VELO = "velo", "Vélo"
    A_PIED = "a_pied", "À pied"


class Livreur(BaseModel):
    """
    Profil d'un livreur partenaire de la plateforme.

    Distinct du champ Delivery.delivery_person (FK vers AUTH_USER_MODEL) qui
    est conservé pour compatibilité ascendante. Ce modèle est le point d'entrée
    canonique pour toute nouvelle logique de gestion des livreurs.

    La désactivation logique (is_active=False, hérité de BaseModel) est préférée
    à la suppression physique pour conserver l'historique des livraisons passées.
    """

    nom = models.CharField(
        blank=True, null=True,
        max_length=100,
        verbose_name="Nom",
        help_text="Nom de famille du livreur.",
    )

    prenom = models.CharField(
        blank=True, null=True,
        max_length=100,
        verbose_name="Prénom",
        help_text="Prénom du livreur.",
    )

    telephone = models.CharField(
        blank=True, null=True,
        max_length=30,
        verbose_name="Téléphone",
        help_text="Numéro de téléphone principal du livreur.",
        db_index=True,
    )

    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name="Email",
        help_text="Adresse email du livreur (optionnel).",
    )

    photo_profil = models.ImageField(
        upload_to="livreurs/photos/",
        blank=True,
        null=True,
        verbose_name="Photo de profil",
        help_text="Photo de profil du livreur (optionnel, formats: JPG, PNG, WEBP).",
    )

    type_vehicule = models.CharField(
        blank=True, null=True,
        max_length=20,
        choices=TypeVehicule.choices,
        verbose_name="Type de véhicule",
        help_text="Type de véhicule utilisé pour les livraisons.",
    )

    zone_livraison = models.CharField(
        null=True,
        max_length=255,
        blank=True,
        verbose_name="Zone de livraison",
        help_text="Zone géographique couverte par le livreur (texte libre).",
    )

    # Rattachement optionnel à un compte utilisateur de la plateforme.
    # related_name="profil_livreur" est distinct de "deliveries_handled"
    # qui appartient à Delivery.delivery_person (FK vers AUTH_USER_MODEL).
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profil_livreur",
        verbose_name="Compte utilisateur",
        help_text="Compte plateforme associé à ce livreur (optionnel).",
    )

    notes = models.TextField(
        null=True,
        blank=True,
        verbose_name="Notes internes",
        help_text="Informations internes sur le livreur (non visibles du client).",
    )

    class Meta:
        db_table = "livraisons_livreurs"
        verbose_name = "Livreur"
        verbose_name_plural = "Livreurs"
        ordering = ["nom", "prenom"]
        indexes = [
            models.Index(fields=["telephone"], name="livraisons_livreur_tel_idx"),
            models.Index(fields=["is_active"], name="livraisons_livreur_active_idx"),
        ]

    def __str__(self):
        return f"{self.prenom} {self.nom}"

    @property
    def nom_complet(self) -> str:
        """Retourne le nom complet du livreur (prénom + nom)."""
        return f"{self.prenom} {self.nom}"


# ─────────────────────────────────────────────────────────────────────────────
# DELIVERY STATUS HISTORY
# ─────────────────────────────────────────────────────────────────────────────

class DeliveryStatusHistory(BaseModel):
    """
    Historique des changements de statut d'une livraison.

    Permet de tracer "qui a fait quoi et quand" sur une livraison, 
    essentiel pour la résolution de litiges.
    """
    delivery = models.ForeignKey(
        Delivery,
        on_delete=models.CASCADE,
        related_name="status_history",
        verbose_name="Livraison"
    )

    old_status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        blank=True,
        null=True,
        verbose_name="Ancien statut"
    )

    new_status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        verbose_name="Nouveau statut"
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Modifié par"
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Notes / Motif"
    )

    class Meta:
        db_table = "livraisons_delivery_history"
        verbose_name = "Historique de livraison"
        verbose_name_plural = "Historiques de livraison"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["delivery", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.delivery.id} : {self.old_status} -> {self.new_status}"

