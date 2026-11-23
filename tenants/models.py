from django.db import models

# Create your models here.

from django.conf import settings
from django.db import models


class Tenant(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    # Every tenant profile belongs to a landlord account.
    landlord = models.ForeignKey(
        "accounts.LandlordAccount",
        on_delete=models.PROTECT,
        related_name="tenants"
    )

    # A tenant may optionally have a RentFlow login account.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_profiles"
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    email = models.EmailField(blank=True)

    phone_number = models.CharField(max_length=20)
    alternate_phone = models.CharField(
        max_length=20,
        blank=True
    )

    address = models.TextField(blank=True)

    emergency_contact_name = models.CharField(
        max_length=150,
        blank=True
    )

    emergency_contact_phone = models.CharField(
        max_length=20,
        blank=True
    )

    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        indexes = [
            models.Index(
                fields=["landlord", "status"],
                name="tenant_landlord_status_idx"
            ),
            models.Index(
                fields=["phone_number"],
                name="tenant_phone_idx"
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
