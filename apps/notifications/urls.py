from django.urls import path
from .views import (
    NewsletterSubscribeAPIView,
    ContactMessageCreateAPIView,
    NewsletterSubscriberListAPIView,
    NewsletterSubscriberDetailAPIView,
    ContactMessageListAPIView,
    ContactMessageDetailAPIView,
    CustomerReviewListAPIView,
    CustomerReviewCreateAPIView,
    AdminCustomerReviewListAPIView,
    AdminCustomerReviewDetailAPIView,
)

app_name = "notifications"

urlpatterns = [
    # Public routes
    path("newsletter/", NewsletterSubscribeAPIView.as_view(), name="newsletter-subscribe"),
    path("contact/", ContactMessageCreateAPIView.as_view(), name="contact-message"),
    path("avis-clients/", CustomerReviewListAPIView.as_view(), name="customer-reviews-list"),
    path("avis-clients/create/", CustomerReviewCreateAPIView.as_view(), name="customer-reviews-create"),

    # Admin routes
    path("admin/newsletter/", NewsletterSubscriberListAPIView.as_view(), name="admin-newsletter-list"),
    path("admin/newsletter/<uuid:pk>/", NewsletterSubscriberDetailAPIView.as_view(), name="admin-newsletter-detail"),
    path("admin/contact/", ContactMessageListAPIView.as_view(), name="admin-contact-list"),
    path("admin/contact/<uuid:pk>/", ContactMessageDetailAPIView.as_view(), name="admin-contact-detail"),
    path("admin/avis-clients/", AdminCustomerReviewListAPIView.as_view(), name="admin-avis-clients-list"),
    path("admin/avis-clients/<uuid:pk>/", AdminCustomerReviewDetailAPIView.as_view(), name="admin-avis-clients-detail"),
]
