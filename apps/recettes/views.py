"""
Vues DRF pour le module recettes.

- RecetteViewSet : consultation publique (lecture seule), filtrable par
  produit ou par pack pour reproduire l'affichage "recette associée à ce
  produit" du site public (à la manière d'une page recette e-commerce).
- AdminRecetteViewSet : CRUD complet réservé aux administrateurs de la
  plateforme.
"""
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.core.permissions import IsPlatformAdmin

from .filters import RecetteFilter
from .models import Recette
from .serializers import AdminRecetteSerializer, RecetteSerializer
from .services import RecetteService


# =====================================================
# PUBLIC RECETTE
# =====================================================

@extend_schema_view(
    list=extend_schema(
        summary="Lister les recettes",
        description=(
            "Retourne les recettes de cuisine actives. Filtrable par produit "
            "(`?product=<id>` ou `?product_slug=<slug>`) ou par pack "
            "(`?pack=<id>` ou `?pack_slug=<slug>`) afin de récupérer les "
            "recettes associées à un produit ou à un pack de produits particulier. "
            "Filtrable également par le slug propre de la recette (`?slug=<slug>`)."
        ),
    ),
    retrieve=extend_schema(
        summary="Détails d'une recette",
        description="Retourne le détail complet d'une recette de cuisine active.",
    ),
)
class RecetteViewSet(ReadOnlyModelViewSet):
    """
    GET /api/v1/recettes/
    GET /api/v1/recettes/{id}/

    Endpoint public en lecture seule.
    """
    permission_classes = [AllowAny]

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_class = RecetteFilter

    search_fields = [
        "nom",
        "slug",
        "description",
        "ingredients",
    ]

    ordering_fields = [
        "created_at",
        "nom",
    ]

    serializer_class = RecetteSerializer

    def get_queryset(self):
        return RecetteService.get_active_recettes()


# =====================================================
# ADMIN RECETTE
# =====================================================

@extend_schema_view(
    list=extend_schema(
        summary="Lister les recettes (Admin)",
        description="Retourne la liste complète de toutes les recettes de cuisine. Accès réservé aux administrateurs de la plateforme.",
    ),
    retrieve=extend_schema(
        summary="Détails d'une recette (Admin)",
        description="Retourne les détails d'une recette spécifique par son ID.",
    ),
    create=extend_schema(
        summary="Créer une recette (Admin)",
        description="Crée une nouvelle recette. Si une vidéo est fournie, elle est automatiquement compressée côté serveur.",
    ),
    update=extend_schema(
        summary="Mettre à jour une recette (Admin)",
        description="Met à jour l'intégralité d'une recette.",
    ),
    partial_update=extend_schema(
        summary="Mettre à jour partiellement une recette (Admin)",
        description="Met à jour partiellement les champs d'une recette.",
    ),
    destroy=extend_schema(
        summary="Supprimer une recette (Admin)",
        description="Supprime définitivement une recette ainsi que ses fichiers médias associés.",
    ),
)
class AdminRecetteViewSet(ModelViewSet):
    """
    CRUD admin complet pour les recettes de cuisine.
    /api/v1/recettes/admin/recettes/
    """
    permission_classes = [
        IsPlatformAdmin
    ]

    serializer_class = AdminRecetteSerializer

    queryset = (
        Recette.objects
        .all()
        .select_related("product", "pack")
        .order_by("-created_at")
    )
