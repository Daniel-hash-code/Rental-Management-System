from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        PLATFORM_ADMIN = "platform_admin", "Platform Administrator"
        LANDLORD = "landlord", "Landlord"
        PROPERTY_MANAGER = "property_manager", "Property Manager"
        TENANT = "tenant", "Tenant"

    email = models.EmailField(unique=True)

    phone_number = models.CharField(
        max_length=20,
        blank=True
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.TENANT
    )

    def __str__(self):
        return self.username