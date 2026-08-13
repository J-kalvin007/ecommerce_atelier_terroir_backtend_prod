from rest_framework import serializers
from .models import NewsletterSubscriber, ContactMessage, CustomerReview

class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ['id', 'email', 'is_active', 'created_at']
        read_only_fields = ['id', 'is_active', 'created_at']

class AdminNewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ['id', 'email', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'subject', 'message', 'is_read', 'created_at']
        read_only_fields = ['id', 'is_read', 'created_at']

class AdminContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['id', 'name', 'email', 'subject', 'message', 'is_read', 'created_at']
        read_only_fields = ['id', 'created_at']

class CustomerReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerReview
        fields = [
            'id', 'last_name', 'first_name', 'city', 'profile_image', 
            'rating', 'message', 'is_approved', 'created_at'
        ]
        read_only_fields = ['id', 'is_approved', 'created_at']

class AdminCustomerReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerReview
        fields = [
            'id', 'last_name', 'first_name', 'city', 'profile_image', 
            'rating', 'message', 'is_approved', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
