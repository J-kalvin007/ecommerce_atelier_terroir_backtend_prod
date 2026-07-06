import uuid
from django.db import models
from django.utils import timezone


class BaseModel(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    # deleted_at = models.DateTimeField(
    #     null=True,
    #     blank=True
    # )

    is_active = models.BooleanField(
        default=True,
        db_index=True
    )

    class Meta:
        abstract = True

    # def soft_delete(self):
    #     self.deleted_at = timezone.now()
    #     self.is_active = False
    #     self.save(update_fields=["deleted_at", "is_active"])

    # @property
    # def is_deleted(self):
    #     return self.deleted_at is not None