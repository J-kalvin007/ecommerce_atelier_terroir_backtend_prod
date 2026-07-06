

from allauth.account.models import EmailAddress

EmailAddress.objects.filter(
    user=request.user,
    verified=True,
).exists()




from allauth.account.models import EmailAddress

EmailAddress.objects.filter(
    user=request.user,
    verified=True,
).exists()




@receiver(email_confirmed)
def mark_user_verified(request, email_address, **kwargs):
    user = email_address.user

    user.is_verified = True

    user.save(update_fields=["is_verified"])