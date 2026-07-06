from rest_framework import generics, status
from rest_framework.response import Response
from django.core.mail import send_mail
from django.conf import settings
from .models import NewsletterSubscriber, ContactMessage
from .serializers import NewsletterSubscriberSerializer, ContactMessageSerializer

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
