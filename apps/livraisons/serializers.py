from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import FraisLivraison, Delivery, Livreur, DeliveryStatusHistory

class FraisLivraisonSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraisLivraison
        fields = [
            "id",
            "prix_livraison",
            "coordonnee_admin",
            "created_at",
            "updated_at",
            "is_active"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

class FraisLivraisonPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraisLivraison
        fields = [
            "prix_livraison",
            "coordonnee_admin"
        ]


class DeliveryStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryStatusHistory
        fields = [
            "id",
            "old_status",
            "new_status",
            "changed_by_name",
            "notes",
            "created_at"
        ]
        read_only_fields = fields

    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return obj.changed_by.get_full_name() or obj.changed_by.email
        return "Système"


# ─────────────────────────────────────────────────────────────────────────────
# LIVREUR SERIALIZERS
# ─────────────────────────────────────────────────────────────────────────────

class LivreurSerializer(serializers.ModelSerializer):
    """
    Serializer complet pour la gestion admin des livreurs.

    Expose toutes les informations, y compris les données personnelles
    (téléphone, email). Réservé aux endpoints admin protégés par IsPlatformAdmin.
    Calqué sur FraisLivraisonSerializer.
    """

    nom_complet = serializers.CharField(read_only=True)

    class Meta:
        model = Livreur
        fields = [
            "id",
            "nom",
            "prenom",
            "nom_complet",
            "telephone",
            "email",
            "type_vehicule",
            "zone_livraison",
            "user",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class LivreurPublicSerializer(serializers.ModelSerializer):
    """
    Serializer d'exposition minimale du livreur pour le client.

    N'expose que les informations nécessaires à l'identification visuelle
    du livreur (qui livre, pas comment le joindre directement).
    Aucune donnée PII (téléphone, email, notes) n'est exposée.
    Calqué sur FraisLivraisonPublicSerializer.
    """

    nom_complet = serializers.CharField(read_only=True)

    class Meta:
        model = Livreur
        fields = [
            "id",
            "nom",
            "prenom",
            "nom_complet",
            "type_vehicule",
        ]


# ─────────────────────────────────────────────────────────────────────────────
# DELIVERY SERIALIZERS
# ─────────────────────────────────────────────────────────────────────────────

class DeliverySerializer(serializers.ModelSerializer):
    order_reference = serializers.SerializerMethodField()
    order_status = serializers.CharField(source="order.status", read_only=True)
    client_name = serializers.SerializerMethodField()
    client_phone = serializers.CharField(source="order.phone_livraison", read_only=True)
    delivery_person_name = serializers.CharField(source="delivery_person.email", read_only=True, allow_null=True)
    order_total = serializers.DecimalField(source="order.total_final", max_digits=12, decimal_places=2, read_only=True)
    items_count = serializers.SerializerMethodField()
    
    livreur_details = serializers.SerializerMethodField()
    history = DeliveryStatusHistorySerializer(source="status_history", many=True, read_only=True)

    class Meta:
        model = Delivery
        fields = [
            "id",
            "order",
            "order_reference",
            "order_status",
            "client_name",
            "client_phone",
            "order_total",
            "items_count",
            "status",
            "delivery_address",
            "tracking_number",
            "delivery_person",
            "delivery_person_name",
            "livreur",
            "livreur_details",
            "history",
            "estimated_delivery_date",
            "actual_delivery_date",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
            "is_active"
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at", "livreur_details", "history"]

    def get_items_count(self, obj):
        return sum(item.quantity for item in obj.order.items.all())

    def get_order_reference(self, obj):
        return obj.order.numero_commande or obj.order.reference or str(obj.order.id)

    def get_client_name(self, obj):
        order = obj.order
        if order.prenom_client and order.nom_client:
            return f"{order.prenom_client} {order.nom_client}"
        if order.user:
            return order.user.get_full_name() or order.user.email
        return order.nom_client or order.prenom_client or "—"

    @extend_schema_field(LivreurPublicSerializer)
    def get_livreur_details(self, obj):
        if obj.livreur:
            return LivreurPublicSerializer(obj.livreur).data
        return None

class DeliveryPublicSerializer(serializers.ModelSerializer):
    """
    Serializer pour exposer le suivi d'une livraison au client final.
    Omet les notes internes et l'historique complet.
    """
    order_reference = serializers.SerializerMethodField()
    livreur = serializers.SerializerMethodField()

    class Meta:
        model = Delivery
        fields = [
            "id",
            "order_reference",
            "status",
            "delivery_address",
            "tracking_number",
            "livreur",
            "estimated_delivery_date",
            "actual_delivery_date",
        ]
        read_only_fields = fields

    def get_order_reference(self, obj):
        return obj.order.numero_commande or obj.order.reference or str(obj.order.id)
        
    @extend_schema_field(LivreurPublicSerializer)
    def get_livreur(self, obj):
        if obj.livreur:
            return LivreurPublicSerializer(obj.livreur).data
        return None


class ConfirmerReceptionSerializer(serializers.Serializer):
    """
    Serializer pour la confirmation de réception par le client.
    """
    notes = serializers.CharField(
        required=False, 
        allow_blank=True, 
        help_text="Commentaire optionnel du client sur la livraison."
    )


class MyDeliverySerializer(DeliverySerializer):
    """
    Serializer pour l'endpoint my-livraisons, avec les données enrichies du livreur
    directement dans le champ 'livreur'.
    """
    livreur = LivreurSerializer(read_only=True)

    class Meta(DeliverySerializer.Meta):
        pass
