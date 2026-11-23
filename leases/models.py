
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Lease(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        TERMINATED = "terminated", "Terminated"

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.PROTECT,
        related_name="leases"
    )

    unit = models.ForeignKey(
        "properties.RentalUnit",
        on_delete=models.PROTECT,
        related_name="leases"
    )

    start_date = models.DateField()
    end_date = models.DateField(
        null=True,
        blank=True
    )

    monthly_rent = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    security_deposit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    currency = models.CharField(
        max_length=3,
        default="KES"
    )

    billing_day = models.PositiveSmallIntegerField(
        default=1,
        help_text="Day of the month when rent is due (1-28)."
    )

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.DRAFT
    )

    terms_and_conditions = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_leases"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

        indexes = [
            models.Index(
                fields=["unit", "status"],
                name="lease_unit_status_idx"
            ),
            models.Index(
                fields=["tenant", "status"],
                name="lease_tenant_status_idx"
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(monthly_rent__gt=0),
                name="lease_monthly_rent_positive"
            ),
            models.CheckConstraint(
                condition=Q(security_deposit__gte=0),
                name="lease_deposit_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(billing_day__gte=1)
                & Q(billing_day__lte=28),
                name="lease_billing_day_valid"
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}

        # Ensure that the tenant and rental unit
        # belong to the same landlord account.
        if self.tenant_id and self.unit_id:

            tenant_landlord_id = self.tenant.landlord_id

            unit_landlord_id = (
                self.unit.property.landlord_id
            )

            if tenant_landlord_id != unit_landlord_id:
                errors["tenant"] = (
                    "This tenant and rental unit "
                    "belong to different landlord accounts."
                )

        # The end date must not precede the start date.
        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            errors["end_date"] = (
                "The lease end date cannot be "
                "earlier than the start date."
            )

        # Only one active lease can occupy a unit
        # during a given period.
        if (
            self.unit_id
            and self.start_date
            and self.status == self.Status.ACTIVE
        ):
            overlapping_leases = Lease.objects.filter(
                unit_id=self.unit_id,
                status=self.Status.ACTIVE,
                start_date__lte=(
                    self.end_date
                    if self.end_date
                    else "9999-12-31"
                ),
            ).filter(
                Q(end_date__isnull=True)
                | Q(end_date__gte=self.start_date)
            )

            if self.pk:
                overlapping_leases = (
                    overlapping_leases.exclude(pk=self.pk)
                )

            if overlapping_leases.exists():
                errors["unit"] = (
                    "This unit already has an active "
                    "lease covering the selected period."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.tenant} - "
            f"{self.unit} ({self.start_date})"
        )
