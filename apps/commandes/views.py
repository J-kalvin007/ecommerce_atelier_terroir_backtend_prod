from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter, OpenApiTypes

from apps.commandes.filters import OrderFilter
from apps.commandes.models import Order, OrderStatus, Cart, CartItem
from apps.catalog.models import ProductVariant
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
)
from apps.commandes.services import OrderService
from apps.core.permissions import IsCustomer, IsPlatformAdmin


# ==================================================
# CLIENT VIEWS
# ==================================================

class CheckoutAPIView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = CheckoutSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user if request.user.is_authenticated else None

        order = OrderService.create_order(
            user=user,
            nom_client=serializer.validated_data.get("nom_client", ""),
            prenom_client=serializer.validated_data.get("prenom_client", ""),
            email_client=serializer.validated_data.get("email_client", ""),
            items=serializer.validated_data["items"],
            address_livraison=serializer.validated_data["address_livraison"],
            phone_livraison=serializer.validated_data["phone_livraison"],
            city=serializer.validated_data["city"],
            country=serializer.validated_data["country"],
            notes=serializer.validated_data.get("notes", ""),
            frais_livraison=serializer.validated_data.get("frais_livraison", 0),
            discount_amount=serializer.validated_data.get("discount_amount", 0),
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

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).select_related('user').prefetch_related(
            "items__product__product__category",
            "items__product__product__images",
            "items__product__product__variants",
        ).order_by("-created_at")


class OrderDetailAPIView(generics.RetrieveAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated, IsCustomer | IsPlatformAdmin]
    lookup_field = "reference"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).select_related('user').prefetch_related(
            "items__product__product__category",
            "items__product__product__images",
            "items__product__product__variants",
        )


class OrderHistoryAPIView(generics.ListAPIView):
    serializer_class = OrderHistorySerializer
    permission_classes = [IsAuthenticated, IsCustomer | IsPlatformAdmin]

    def get_queryset(self):
        reference = self.kwargs["reference"]
        
        # If user is admin/staff, they can view any order's history
        if self.request.user.is_staff or getattr(self.request.user, 'role', '') == 'admin':
            order = get_object_or_404(Order, reference=reference)
        else:
            order = get_object_or_404(
                Order,
                reference=reference,
                user=self.request.user,
            )
            
        return order.status_history.all().order_by("created_at")


class OrderCancelView(generics.GenericAPIView):
    """
    Gère l'annulation d'une commande par le client.
    Vérifie que la commande n'est pas déjà en cours d'expédition ou livrée.
    """
    permission_classes = [IsAuthenticated, IsCustomer | IsPlatformAdmin]

    def post(self, request, reference):
        order = get_object_or_404(
            Order,
            reference=reference,
            user=request.user,
        )

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


class AdminOrderDetailAPIView(generics.RetrieveAPIView):
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    queryset = Order.objects.all().select_related('user').prefetch_related(
        "items__product__product__category",
        "items__product__product__images",
        "items__product__product__variants",
    )
    lookup_field = "reference"


class AdminOrderStatusAPIView(generics.GenericAPIView):
    serializer_class = AdminOrderStatusSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]

    def patch(self, request, reference):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = get_object_or_404(Order, reference=reference)

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