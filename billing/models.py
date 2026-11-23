
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class RentCharge(models.Model):

    class Status(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIALLY_PAID = "partially_paid", "Partially Paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        VOID = "void", "Void"

    lease = models.ForeignKey(
        "leases.Lease",
        on_delete=models.PROTECT,
        related_name="rent_charges"
    )

    description = models.CharField(
        max_length=200,
        default="Monthly Rent"
    )

    period_start = models.DateField()
    period_end = models.DateField()

    due_date = models.DateField()

    amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    # Updated by the payment allocation process in a later phase.
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    currency = models.CharField(
        max_length=3,
        default="KES"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNPAID
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "period_start"]

        constraints = [
            models.UniqueConstraint(
                fields=["lease", "period_start"],
                name="unique_lease_billing_period"
            ),
            models.CheckConstraint(
                condition=Q(amount_due__gt=0),
                name="rent_charge_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(amount_paid__gte=0),
                name="rent_charge_paid_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(amount_paid__lte=models.F("amount_due")),
                name="rent_charge_paid_not_above_due"
            ),
        ]

        indexes = [
            models.Index(
                fields=["status", "due_date"],
                name="charge_status_due_idx"
            ),
            models.Index(
                fields=["lease", "due_date"],
                name="charge_lease_due_idx"
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}

        if (
            self.period_start
            and self.period_end
            and self.period_end < self.period_start
        ):
            errors["period_end"] = (
                "The billing period end cannot precede its start."
            )

        if self.lease_id and self.period_start and self.period_end:
            lease = self.lease

            if self.period_start < lease.start_date:
                errors["period_start"] = (
                    "The billing period cannot start before the lease."
                )

            if (
                lease.end_date
                and self.period_end > lease.end_date
            ):
                errors["period_end"] = (
                    "The billing period cannot end after the lease."
                )

        if (
            self.amount_due is not None
            and self.amount_paid is not None
            and self.amount_paid > self.amount_due
        ):
            errors["amount_paid"] = (
                "The amount paid cannot exceed the amount due."
            )

        if errors:
            raise ValidationError(errors)

    @property
    def balance_due(self):
        return max(
            self.amount_due - self.amount_paid,
            0
        )

    @property
    def is_overdue(self):
        return (
            self.status == self.Status.OVERDUE
            or (
                self.status in (
                    self.Status.UNPAID,
                    self.Status.PARTIALLY_PAID,
                )
                and self.due_date < timezone.localdate()
            )
        )

    def __str__(self):
        return (
            f"{self.lease.tenant} - "
            f"{self.period_start:%B %Y}"
        )
