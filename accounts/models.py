from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.utils import timezone


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



class LandlordAccount(models.Model):

    name = models.CharField(max_length=150)

    slug = models.SlugField(
        max_length=180,
        unique=True
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_landlord_accounts"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Landlord Account"
        verbose_name_plural = "Landlord Accounts"
        ordering = ["name"]


class Membership(models.Model):

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Administrator"
        PROPERTY_MANAGER = "property_manager", "Property Manager"
        ACCOUNTANT = "accountant", "Accountant"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INVITED = "invited", "Invited"
        SUSPENDED = "suspended", "Suspended"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    landlord = models.ForeignKey(
        LandlordAccount,
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.PROPERTY_MANAGER
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "landlord"],
                name="unique_user_landlord_membership"
            )
        ]

        ordering = ["landlord", "user"]

    def __str__(self):
        return f"{self.user.username} - {self.landlord.name} ({self.role})"


class EmailVerification(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verification",
    )

    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return (
            self.verified_at is None
            and self.expires_at > timezone.now()
        )

    def __str__(self):
        return f"Email verification: {self.user.email}"


class TenantInvitation(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="invitations",
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_tenant_invitations",
    )

    email = models.EmailField()
    token_hash = models.CharField(max_length=64, unique=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return (
            self.status == self.Status.PENDING
            and self.expires_at > timezone.now()
            and self.accepted_at is None
        )

    def __str__(self):
        return f"Invitation for {self.email}"
