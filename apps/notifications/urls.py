from django.urls import path
from .views import NewsletterSubscribeAPIView, ContactMessageCreateAPIView

app_name = "notifications"

urlpatterns = [
    path("newsletter/", NewsletterSubscribeAPIView.as_view(), name="newsletter-subscribe"),
    path("contact/", ContactMessageCreateAPIView.as_view(), name="contact-message"),
]
