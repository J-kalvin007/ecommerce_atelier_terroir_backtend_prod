from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter, OpenApiTypes

from apps.commandes.filters import OrderFilter
from apps.commandes.models import Order, OrderStatus, Cart, CartItem, CartPackItem
from apps.catalog.models import ProductVariant
from apps.promotions.models import Pack
from django.utils.translation import gettext as _
from apps.commandes.serializers import (
    AdminOrderStatusSerializer,
    CheckoutSerializer,
    OrderDetailSerializer,
    OrderHistorySerializer,
    OrderListSerializer,
    CartSerializer,
    CartItemSerializer,
    AddCartItemSerializer,
    CartPackItemSerializer,
    AddCartPackSerializer,
)
from apps.commandes.services import OrderService
from apps.core.permissions import IsCustomer, IsPlatformAdmin


# ==================================================
# CLIENTS VIEWS
# ==================================================

class CheckoutAPIView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = CheckoutSerializer

    @extend_schema(
        summary="Valider une commande",
        description="Crée une nouvelle commande à partir des informations fournies.",
        request=CheckoutSerializer,
        responses={201: OrderDetailSerializer}
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user if request.user.is_authenticated else None

        order = OrderService.create_order(
            user=user,
            nom_client=serializer.validated_data.get("nom_client", ""),
            prenom_client=serializer.validated_data.get("prenom_client", ""),
            email_client=serializer.validated_data.get("email_client", ""),
            items=serializer.validated_data.get("items", []),
            packs=serializer.validated_data.get("packs", []),
            address_livraison=serializer.validated_data["address_livraison"],
            phone_livraison=serializer.validated_data["phone_livraison"],
            city=serializer.validated_data["city"],
            country=serializer.validated_data["country"],
            notes=serializer.validated_data.get("notes", ""),
            frais_livraison=serializer.validated_data.get("frais_livraison", 0),
            discount_amount=serializer.validated_data.get("discount_amount", 0),
            is_for_delivery=serializer.validated_data.get("is_for_delivery", True),
        )

        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class MyOrderListAPIView(generics.ListAPIView):
    serializer_class = OrderListSerializer
    permission_classes = [IsAuthenticated, IsCustomer | IsPlatformAdmin]
    filterset_class = OrderFilter
    filter_backends = [DjangoFilterBackend]
    ordering = ["-created_at"]

    @extend_schema(
        summary="Lister mes commandes",
        description="Renvoie la liste des commandes de l'utilisateur connecté.",
        responses={200: OrderListSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).select_related('user').prefetch_related(
            "items__product__product__category",
            "items__product__product__images",
            "items__product__product__variants",
        ).order_by("-created_at")


class OrderDetailAPIView(generics.RetrieveAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Détails d'une commande",
        description="Renvoie les détails d'une commande (via sa référence ou son ID) appartenant à l'utilisateur connecté.",
        responses={200: OrderDetailSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        """
        Resolves the order by `reference` first, then by UUID `id`.
        """
        lookup = self.kwargs.get("reference")
        qs = Order.objects.select_related('user').prefetch_related(
            "items__product__product__category",
            "items__product__product__images",
            "items__product__product__variants",
        )
        # Try matching by reference first, then fall back to UUID pk
        order = qs.filter(reference=lookup).first()
        if not order:
            from django.core.exceptions import ValidationError
            try:
                order = qs.filter(pk=lookup).first()
            except (ValueError, ValidationError):
                pass
                
        if not order:
            from rest_framework.exceptions import NotFound
            raise NotFound(_("Commande introuvable."))
            
        # Permission check
        if order.user:
            user = self.request.user
            if not user.is_authenticated:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(_("Vous devez être connecté pour voir cette commande."))

        return order


class OrderHistoryAPIView(generics.ListAPIView):
    serializer_class = OrderHistorySerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Historique d'une commande",
        description="Renvoie l'historique des changements de statut d'une commande via sa référence ou son ID.",
        responses={200: OrderHistorySerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        reference = self.kwargs["reference"]
        
        order = Order.objects.filter(reference=reference).first()
        if not order:
            from django.core.exceptions import ValidationError
            try:
                order = Order.objects.filter(pk=reference).first()
            except (ValueError, ValidationError):
                pass
                
        if not order:
            from rest_framework.exceptions import NotFound
            raise NotFound(_("Commande introuvable."))

        # Permission check
        if order.user:
            user = self.request.user
            if not user.is_authenticated:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(_("Vous devez être connecté pour voir cette commande."))
            
        return order.status_history.all().order_by("created_at")


class OrderCancelView(generics.GenericAPIView):
    """
    Gère l'annulation d'une commande par le client.
    Vérifie que la commande n'est pas déjà en cours d'expédition ou livrée.
    """
    permission_classes = [IsAuthenticated, IsCustomer | IsPlatformAdmin]

    @extend_schema(
        summary="Annuler une commande",
        description="Permet au client d'annuler une commande si elle n'est pas encore expédiée ou livrée (via sa référence ou son ID).",
        responses={
            200: OpenApiResponse(description="Commande annulée avec succès."),
            400: OpenApiResponse(description="Cette commande ne peut plus être annulée.")
        }
    )
    def post(self, request, reference):
        qs = Order.objects.filter(user=request.user)
        # Resolve by reference first, then by UUID pk (backward compat)
        order = qs.filter(reference=reference).first() or qs.filter(pk=reference).first()
        if not order:
            from rest_framework.exceptions import NotFound
            raise NotFound(_("Commande introuvable."))

        allowed_cancel_statuses = [
            OrderStatus.DRAFT,
            OrderStatus.PENDING_PAYMENT,
            OrderStatus.PAID,
            OrderStatus.CONFIRMED,
        ]

        if order.status not in allowed_cancel_statuses:
            return Response(
                {'detail': _('Cette commande ne peut plus être annulée.')},
                status=status.HTTP_400_BAD_REQUEST
            )

        OrderService.update_status(
            order=order,
            new_status=OrderStatus.CANCELLED,
            changed_by=request.user,
            comment=_("Annulation par le client"),
        )

        return Response(
            {'detail': _('Commande annulée avec succès.')},
            status=status.HTTP_200_OK
        )


# ==================================================
# ADMIN VIEWS
# ==================================================

class AdminOrderListAPIView(generics.ListAPIView):
    serializer_class = OrderListSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    queryset = Order.objects.all().select_related('user').prefetch_related(
        "items__product__product__category",
        "items__product__product__images",
        "items__product__product__variants",
    ).order_by("-created_at")
    filterset_class = OrderFilter
    filter_backends = [DjangoFilterBackend]

    @extend_schema(
        summary="Lister toutes les commandes (Admin)",
        description="Renvoie la liste de toutes les commandes pour l'administration.",
        responses={200: OrderListSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminOrderDetailAPIView(generics.RetrieveAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    @extend_schema(
        summary="Détails d'une commande (Admin)",
        description="Récupère les détails d'une commande via sa référence unique ou son ID (UUID).",
        responses={200: OrderDetailSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return Order.objects.all().select_related('user').prefetch_related(
            "items__product__product__category",
            "items__product__product__images",
            "items__product__product__variants",
        )

    def get_object(self):
        """
        Resolves the order by `reference` first, then by UUID `id`.
        """
        lookup = self.kwargs.get("reference")
        qs = self.get_queryset()
        
        order = qs.filter(reference=lookup).first()
        if not order:
            from django.core.exceptions import ValidationError
            try:
                order = qs.filter(pk=lookup).first()
            except (ValueError, ValidationError):
                pass
                
        if not order:
            from rest_framework.exceptions import NotFound
            raise NotFound(_("Commande introuvable."))
            
        return order


class AdminOrderStatusAPIView(generics.GenericAPIView):
    serializer_class = AdminOrderStatusSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    @extend_schema(
        summary="Mettre à jour le statut (Admin)",
        description="Met à jour le statut d'une commande via sa référence unique ou son ID (UUID).",
        request=AdminOrderStatusSerializer,
        responses={200: OrderDetailSerializer}
    )
    def patch(self, request, reference):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = Order.objects.filter(reference=reference).first()
        if not order:
            from django.core.exceptions import ValidationError
            try:
                order = Order.objects.filter(pk=reference).first()
            except (ValueError, ValidationError):
                pass

        if not order:
            from rest_framework.exceptions import NotFound
            raise NotFound(_("Commande introuvable."))

        OrderService.update_status(
            order=order,
            new_status=serializer.validated_data["status"],
            changed_by=request.user,
            comment=serializer.validated_data.get("comment", ""),
        )

        order.refresh_from_db()
        return Response(OrderDetailSerializer(order).data)

# ==================================================
# CART VIEWS
# ==================================================

class CartAPIView(generics.RetrieveAPIView, generics.DestroyAPIView):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Récupérer le panier",
        description="Renvoie le panier de l'utilisateur authentifié (créé automatiquement s'il n'existe pas).",
        responses={200: CartSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        cart, created = Cart.objects.get_or_create(user=self.request.user)
        return cart

    @extend_schema(
        summary="Vider le panier",
        description="Supprime tous les éléments du panier de l'utilisateur actuel.",
        responses={204: OpenApiResponse(description="Panier vidé avec succès.")}
    )
    def delete(self, request, *args, **kwargs):
        cart = self.get_object()
        cart.items.all().delete()
        cart.pack_items.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddCartItemSerializer

    @extend_schema(
        summary="Ajouter un produit au panier",
        description="Ajoute un produit au panier de l'utilisateur. Si le produit y est déjà, la quantité est mise à jour.",
        request=AddCartItemSerializer,
        responses={201: CartItemSerializer}
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        cart, _ = Cart.objects.get_or_create(user=request.user)
        product_id = serializer.validated_data["product_id"]
        quantity = serializer.validated_data["quantity"]
        
        product = get_object_or_404(ProductVariant, id=product_id)
        
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, 
            product=product,
            defaults={"quantity": quantity}
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
            
        return Response(CartItemSerializer(cart_item).data, status=status.HTTP_201_CREATED)


class CartItemDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddCartItemSerializer

    def get_queryset(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return CartItem.objects.filter(cart=cart)

    def get_object(self):
        cart_item = get_object_or_404(self.get_queryset(), product_id=self.kwargs["product_id"])
        return cart_item

    @extend_schema(
        summary="Récupérer un élément du panier",
        description="Renvoie les détails d'un élément spécifique du panier via son product_id.",
        responses={200: CartItemSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Mettre à jour la quantité",
        description="Met à jour la quantité d'un élément dans le panier.",
        request=AddCartItemSerializer,
        responses={200: CartItemSerializer}
    )
    def patch(self, request, *args, **kwargs):
        cart_item = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        if "quantity" in serializer.validated_data:
            cart_item.quantity = serializer.validated_data["quantity"]
            cart_item.save()
            
        return Response(CartItemSerializer(cart_item).data)

    @extend_schema(
        summary="Supprimer un élément",
        description="Supprime complètement un élément du panier.",
        responses={204: OpenApiResponse(description="Élément supprimé avec succès.")}
    )
    def delete(self, request, *args, **kwargs):
        cart_item = self.get_object()
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartPackItemAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddCartPackSerializer

    @extend_schema(
        summary="Ajouter un pack au panier",
        description="Ajoute un pack promotionnel au panier de l'utilisateur. Si le pack y est déjà, la quantité est mise à jour.",
        request=AddCartPackSerializer,
        responses={201: CartPackItemSerializer}
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        cart, _ = Cart.objects.get_or_create(user=request.user)
        pack_id = serializer.validated_data["pack_id"]
        quantity = serializer.validated_data["quantity"]
        
        pack = get_object_or_404(Pack, id=pack_id, is_active=True)
        
        cart_item, created = CartPackItem.objects.get_or_create(
            cart=cart, 
            pack=pack,
            defaults={"quantity": quantity}
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
            
        return Response(CartPackItemSerializer(cart_item, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CartPackItemDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddCartPackSerializer

    def get_queryset(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return CartPackItem.objects.filter(cart=cart)

    def get_object(self):
        cart_item = get_object_or_404(self.get_queryset(), pack_id=self.kwargs["pack_id"])
        return cart_item

    @extend_schema(
        summary="Récupérer un pack du panier",
        description="Renvoie les détails d'un pack spécifique du panier via son pack_id.",
        responses={200: CartPackItemSerializer}
    )
    def get(self, request, *args, **kwargs):
        cart_item = self.get_object()
        return Response(CartPackItemSerializer(cart_item, context={'request': request}).data)

    @extend_schema(
        summary="Mettre à jour la quantité d'un pack",
        description="Met à jour la quantité d'un pack dans le panier.",
        request=AddCartPackSerializer,
        responses={200: CartPackItemSerializer}
    )
    def patch(self, request, *args, **kwargs):
        cart_item = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        if "quantity" in serializer.validated_data:
            cart_item.quantity = serializer.validated_data["quantity"]
            cart_item.save()
            
        return Response(CartPackItemSerializer(cart_item, context={'request': request}).data)

    @extend_schema(
        summary="Supprimer un pack",
        description="Supprime complètement un pack du panier.",
        responses={204: OpenApiResponse(description="Pack supprimé avec succès.")}
    )
    def delete(self, request, *args, **kwargs):
        cart_item = self.get_object()
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)