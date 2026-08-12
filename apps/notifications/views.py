from rest_framework import generics, status
from rest_framework.response import Response
from django.core.mail import send_mail
from django.conf import settings
from .models import NewsletterSubscriber, ContactMessage, CustomerReview
from .serializers import (
    NewsletterSubscriberSerializer, 
    ContactMessageSerializer, 
    CustomerReviewSerializer
)
from apps.core.permissions import IsPlatformAdmin
from drf_spectacular.utils import extend_schema, extend_schema_view

@extend_schema_view(
    post=extend_schema(
        summary="S'inscrire à la newsletter",
        description=(
            "Permet à un visiteur ou utilisateur de s'inscrire à la newsletter. "
            "Envoie un email de bienvenue à l'adresse fournie."
        )
    )
)
class NewsletterSubscribeAPIView(generics.CreateAPIView):
    queryset = NewsletterSubscriber.objects.all()
    serializer_class = NewsletterSubscriberSerializer
    permission_classes = [] # Accessible to public

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Save the subscriber
            self.perform_create(serializer)
            
            # Send welcome email
            email = serializer.validated_data.get('email')
            try:
                send_mail(
                    subject="Bienvenue à la Newsletter - L'Atelier du Terroir",
                    message="Merci de vous être inscrit à notre newsletter ! Vous recevrez bientôt nos actualités et offres exclusives.",
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@dealandconsulting.com'),
                    recipient_list=[email],
                    fail_silently=True,
                )
            except Exception as e:
                # Log email failure but don't fail the request
                print(f"Failed to send newsletter email to {email}: {e}")
                
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema_view(
    post=extend_schema(
        summary="Envoyer un message de contact",
        description=(
            "Permet à un visiteur ou utilisateur d'envoyer un message via le formulaire de contact. "
            "Envoie une notification par email à l'administrateur et un accusé de réception à l'utilisateur."
        )
    )
)
class ContactMessageCreateAPIView(generics.CreateAPIView):
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [] # Accessible to public

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Save the message
            message_obj = serializer.save()
            
            # 1. Send email to admin/support
            try:
                send_mail(
                    subject=f"Nouveau message de contact : {message_obj.subject}",
                    message=f"Nouveau message de {message_obj.name} ({message_obj.email}):\n\n{message_obj.message}",
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@dealandconsulting.com'),
                    recipient_list=['agrobusiness@dealandconsulting.com'], # Replace with admin email
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Failed to send contact notification to admin: {e}")
                
            # 2. Send acknowledgment to user
            try:
                send_mail(
                    subject="Nous avons bien reçu votre message - L'Atelier du Terroir",
                    message=f"Bonjour {message_obj.name},\n\nNous avons bien reçu votre message et notre équipe vous répondra dans les plus brefs délais.\n\nCordialement,\nL'Atelier du Terroir",
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@dealandconsulting.com'),
                    recipient_list=[message_obj.email],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Failed to send contact acknowledgment to {message_obj.email}: {e}")

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    get=extend_schema(
        summary="Lister les abonnés à la newsletter",
        description=(
            "Retourne la liste de tous les abonnés à la newsletter. "
            "Accès réservé aux administrateurs de la plateforme."
        )
    )
)
class NewsletterSubscriberListAPIView(generics.ListAPIView):
    queryset = NewsletterSubscriber.objects.all()
    serializer_class = NewsletterSubscriberSerializer
    permission_classes = [IsPlatformAdmin]


@extend_schema_view(
    get=extend_schema(
        summary="Détails d'un abonné à la newsletter",
        description="Retourne les détails d'un abonné spécifique par son ID. Accès réservé aux administrateurs."
    ),
    delete=extend_schema(
        summary="Supprimer un abonné à la newsletter",
        description="Supprime un abonné spécifique par son ID. Accès réservé aux administrateurs."
    )
)
class NewsletterSubscriberDetailAPIView(generics.RetrieveDestroyAPIView):
    queryset = NewsletterSubscriber.objects.all()
    serializer_class = NewsletterSubscriberSerializer
    permission_classes = [IsPlatformAdmin]


@extend_schema_view(
    get=extend_schema(
        summary="Lister les messages de contact",
        description=(
            "Retourne la liste de tous les messages de contact reçus. "
            "Accès réservé aux administrateurs de la plateforme."
        )
    )
)
class ContactMessageListAPIView(generics.ListAPIView):
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [IsPlatformAdmin]


@extend_schema_view(
    get=extend_schema(
        summary="Détails d'un message de contact",
        description="Retourne les détails d'un message de contact spécifique. Accès réservé aux administrateurs."
    ),
    put=extend_schema(
        summary="Mettre à jour un message de contact",
        description="Met à jour un message de contact spécifique (ex: marquer comme lu). Accès réservé aux administrateurs."
    ),
    patch=extend_schema(
        summary="Mettre à jour partiellement un message de contact",
        description="Met à jour partiellement un message de contact spécifique. Accès réservé aux administrateurs."
    ),
    delete=extend_schema(
        summary="Supprimer un message de contact",
        description="Supprime un message de contact spécifique. Accès réservé aux administrateurs."
    )
)
class ContactMessageDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [IsPlatformAdmin]


@extend_schema_view(
    get=extend_schema(
        summary="Lister les avis clients approuvés",
        description=(
            "Retourne la liste des avis clients qui ont été approuvés par l'administration. "
            "Accès public."
        )
    ),
    post=extend_schema(
        summary="Soumettre un avis client",
        description=(
            "Permet à un utilisateur de soumettre un nouvel avis. "
            "L'avis devra être approuvé par un administrateur avant d'être visible."
        )
    )
)
class CustomerReviewListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = CustomerReviewSerializer
    permission_classes = [] # Accessible to public

    def get_queryset(self):
        return CustomerReview.objects.filter(is_approved=True)


@extend_schema_view(
    get=extend_schema(
        summary="Lister tous les avis clients (Admin)",
        description=(
            "Retourne la liste complète de tous les avis clients, approuvés ou non. "
            "Accès réservé aux administrateurs de la plateforme."
        )
    )
)
class AdminCustomerReviewListAPIView(generics.ListAPIView):
    queryset = CustomerReview.objects.all()
    serializer_class = CustomerReviewSerializer
    permission_classes = [IsPlatformAdmin]


@extend_schema_view(
    get=extend_schema(
        summary="Détails d'un avis client (Admin)",
        description="Retourne les détails d'un avis client spécifique. Accès réservé aux administrateurs."
    ),
    put=extend_schema(
        summary="Mettre à jour un avis client (Admin)",
        description="Met à jour un avis client spécifique (ex: approuver l'avis). Accès réservé aux administrateurs."
    ),
    patch=extend_schema(
        summary="Mettre à jour partiellement un avis client (Admin)",
        description="Met à jour partiellement un avis client spécifique. Accès réservé aux administrateurs."
    ),
    delete=extend_schema(
        summary="Supprimer un avis client (Admin)",
        description="Supprime un avis client spécifique. Accès réservé aux administrateurs."
    )
)
class AdminCustomerReviewDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CustomerReview.objects.all()
    serializer_class = CustomerReviewSerializer
    permission_classes = [IsPlatformAdmin]
