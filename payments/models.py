
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Payment(models.Model):

    class Status(models.TextChoices):
        INITIATED = "INITIATED", "Initiated"
        PENDING = "PENDING", "Pending"
        SUCCESSFUL = "SUCCESSFUL", "Successful"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    # Ownership and relationships
    landlord = models.ForeignKey(
        "accounts.LandlordAccount",
        on_delete=models.PROTECT,
        related_name="payments"
    )

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.PROTECT,
        related_name="payments"
    )

    lease = models.ForeignKey(
        "leases.Lease",
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True
    )

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_payments"
    )

    # Payment information
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    currency = models.CharField(
        max_length=3,
        default="KES"
    )

    phone_number = models.CharField(
        max_length=20
    )

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.INITIATED
    )

    # Daraja transaction identifiers
    merchant_request_id = models.CharField(
        max_length=100,
        blank=True
    )

    checkout_request_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )

    mpesa_receipt_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True
    )

    # Transaction response information
    result_code = models.CharField(
        max_length=20,
        blank=True
    )

    result_description = models.TextField(
        blank=True
    )

    account_reference = models.CharField(
        max_length=100,
        blank=True
    )

    transaction_description = models.CharField(
        max_length=255,
        blank=True
    )

    # Store the callback for audit and reconciliation.
    callback_payload = models.JSONField(
        default=dict,
        blank=True
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_amount_positive"
            )
        ]

        indexes = [
            models.Index(
                fields=["landlord", "status", "created_at"],
                name="payment_land_status_idx"
            ),
            models.Index(
                fields=["tenant", "created_at"],
                name="payment_tenant_date_idx"
            ),
        ]

    def clean(self):
        super().clean()

        if self.tenant_id and self.landlord_id:
            if self.tenant.landlord_id != self.landlord_id:
                raise ValidationError(
                    "The tenant does not belong to this landlord account."
                )

        if self.lease_id:
            if self.lease.landlord_id != self.landlord_id:
                raise ValidationError(
                    "The lease does not belong to this landlord account."
                )

            if self.lease.tenant_id != self.tenant_id:
                raise ValidationError(
                    "The lease does not belong to this tenant."
                )

    def __str__(self):
        return (
            f"Payment {self.pk} - "
            f"KES {self.amount} - {self.status}"
        )
