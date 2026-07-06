from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .forms import UserAdminChangeForm
from .forms import UserAdminCreationForm
from .models import User


if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
    admin.autodiscover()
    admin.site.login = secure_admin_login(admin.site.login)


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):

    form = UserAdminChangeForm
    add_form = UserAdminCreationForm

    list_display = (
        "profile_preview",
        "email",
        "name",
        "role_badge",
        "is_verified",
        "is_active",
        "is_staff",
        "date_joined",
    )

    list_filter = (
        "role",
        "is_verified",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    )

    search_fields = (
        "email",
        "name",
        "phone_number",
    )

    ordering = ("-date_joined",)

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "last_login",
        "date_joined",
        "profile_preview_large",
    )

    fieldsets = (
        (
            _("Account"),
            {
                "fields": (
                    "id",
                    "email",
                    "password",
                )
            },
        ),
        (
            _("Profile"),
            {
                "fields": (
                    "profile_preview_large",
                    "profile_image",
                    "name",
                    "phone_number",
                )
            },
        ),
        (
            _("Roles & Permissions"),
            {
                "fields": (
                    "role",
                    "is_verified",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            _("Audit"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "last_login",
                    "date_joined",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            _("Create User"),
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "name",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


    actions = [
        "verify_users",
        "unverify_users",
    ]

    def profile_preview(self, obj):
        if obj.profile_image:
            return format_html(
                '<img src="{}" width="40" height="40" '
                'style="border-radius:50%;object-fit:cover;" />',
                obj.profile_image.url
            )
        return "—"

    profile_preview.short_description = "Avatar"

    def profile_preview_large(self, obj):
        if obj.profile_image:
            return format_html(
                '<img src="{}" width="150" '
                'style="border-radius:10px;" />',
                obj.profile_image.url
            )
        return "No image"

    profile_preview_large.short_description = "Profile Image"


    @admin.action(description="Mark selected users as verified")
    def verify_users(self, request, queryset):
        queryset.update(is_verified=True)


    @admin.action(description="Mark selected users as unverified")
    def unverify_users(self, request, queryset):
        queryset.update(is_verified=False)


    def role_badge(self, obj):
        colors = {
            "platform_admin": "#dc3545",
            "customer": "#198754",
        }

        return format_html(
            '<span style="padding:4px 8px;border-radius:5px;'
            'background:{};color:white;">{}</span>',
            colors.get(obj.role, "#6c757d"),
            obj.get_role_display(),
        )

    role_badge.short_description = "Role"

from django.apps import apps

# Hide unused third-party apps from admin to clean up the dashboard
apps_to_hide = [
    "django_celery_beat",
    "sites",
    "mfa",
    "authtoken",
    "socialaccount",
    "account",
]

for app_label in apps_to_hide:
    try:
        app_config = apps.get_app_config(app_label)
        for model in app_config.get_models():
            try:
                admin.site.unregister(model)
            except admin.sites.NotRegistered:
                pass
    except LookupError:
        pass
