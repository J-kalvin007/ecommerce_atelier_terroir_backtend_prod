import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

class NewsletterSubscriber(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("Email address"), unique=True)
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("Newsletter Subscriber")
        verbose_name_plural = _("Newsletter Subscribers")
        ordering = ["-created_at"]
        
    def __str__(self):
        return self.email

class ContactMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("Name"), max_length=150)
    email = models.EmailField(_("Email address"))
    subject = models.CharField(_("Subject"), max_length=255)
    message = models.TextField(_("Message"))
    is_read = models.BooleanField(_("Read"), default=False)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("Contact Message")
        verbose_name_plural = _("Contact Messages")
        ordering = ["-created_at"]
        
    def __str__(self):
        return f"{self.subject} - {self.email}"

class CustomerReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    last_name = models.CharField(_("Last Name"), max_length=150)
    first_name = models.CharField(_("First Name"), max_length=150)
    city = models.CharField(_("City"), max_length=150)
    profile_image = models.ImageField(_("Profile Image"), upload_to="reviews/profiles/", null=True, blank=True)
    rating = models.PositiveSmallIntegerField(_("Rating"), choices=[(i, i) for i in range(1, 6)])
    message = models.TextField(_("Message"))
    is_approved = models.BooleanField(_("Approved"), default=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("Customer Review")
        verbose_name_plural = _("Customer Reviews")
        ordering = ["-created_at"]
        
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.rating} stars"
