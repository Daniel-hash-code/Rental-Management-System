from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from billing.models import RentCharge
from payments.models import Payment, PaymentAllocation


class PaymentAllocationError(Exception):
    """Raised when a payment allocation cannot be completed."""


@transaction.atomic
def allocate_payment(payment, allocations):
    """
    Allocate a successful payment to one or more rent charges.

    Example:
        allocations = [
            {
                "rent_charge_id": 1,
                "amount": "5000.00",
            },
            {
                "rent_charge_id": 2,
                "amount": "7000.00",
            },
        ]
    """

    if not allocations:
        raise PaymentAllocationError(
            "At least one allocation is required."
        )

    # Lock the payment to prevent concurrent allocation.
    try:
        payment = Payment.objects.select_for_update().get(
            pk=payment.pk
        )
    except Payment.DoesNotExist:
        raise PaymentAllocationError("Payment does not exist.")

    if payment.status != Payment.Status.SUCCESSFUL:
        raise PaymentAllocationError(
            "Only successful payments can be allocated."
        )

    # Validate and normalize the requested allocations.
    normalized_allocations = []
    seen_charge_ids = set()

    for item in allocations:
        try:
            charge_id = int(item["rent_charge_id"])
            amount = Decimal(str(item["amount"]))
        except (
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
        ):
            raise PaymentAllocationError(
                "Each allocation must have a valid rent_charge_id "
                "and amount."
            )

        if charge_id in seen_charge_ids:
            raise PaymentAllocationError(
                "A rent charge cannot appear more than once "
                "in one allocation request."
            )

        seen_charge_ids.add(charge_id)

        if not amount.is_finite() or amount <= Decimal("0.00"):
            raise PaymentAllocationError(
                "Allocation amounts must be positive."
            )

        if amount.as_tuple().exponent < -2:
            raise PaymentAllocationError(
                "Allocation amounts cannot have more than "
                "two decimal places."
            )

        normalized_allocations.append({
            "rent_charge_id": charge_id,
            "amount": amount,
        })

    total_to_allocate = sum(
        (item["amount"] for item in normalized_allocations),
        Decimal("0.00"),
    )

    # Calculate the remaining unallocated payment amount.
    already_allocated = sum(
        PaymentAllocation.objects.filter(
            payment=payment
        ).values_list("amount", flat=True),
        Decimal("0.00"),
    )

    available_amount = payment.amount - already_allocated

    if total_to_allocate > available_amount:
        raise PaymentAllocationError(
            "The requested allocation exceeds the "
            "unallocated payment amount."
        )

    # Lock all relevant rent charges in a consistent order.
    charge_ids = sorted(seen_charge_ids)

    locked_charges = (
        RentCharge.objects
        .select_for_update()
        .filter(pk__in=charge_ids)
        .order_by("pk")
    )

    charges = {
        charge.pk: charge
        for charge in locked_charges
    }

    if len(charges) != len(charge_ids):
        raise PaymentAllocationError(
            "One or more rent charges do not exist."
        )

    created_allocations = []

    for item in normalized_allocations:
        charge = charges[item["rent_charge_id"]]
        amount = item["amount"]

        # Ensure the payment and charge belong to the same tenant.
        if charge.lease.tenant_id != payment.tenant_id:
            raise PaymentAllocationError(
                "The rent charge does not belong to this tenant."
            )

        # Ensure they also belong to the same landlord.
        if charge.lease.tenant.landlord_id != payment.landlord_id:
            raise PaymentAllocationError(
                "The rent charge does not belong to this landlord."
            )

        # Ensure currencies match.
        if charge.currency != payment.currency:
            raise PaymentAllocationError(
                "Payment and rent charge currencies must match."
            )

        if charge.status == RentCharge.Status.VOID:
            raise PaymentAllocationError(
                "A void rent charge cannot receive an allocation."
            )

        # Prevent duplicate allocations for this payment and charge.
        if PaymentAllocation.objects.filter(
            payment=payment,
            rent_charge=charge,
        ).exists():
            raise PaymentAllocationError(
                "This payment has already been allocated "
                "to this rent charge."
            )

        outstanding_balance = charge.amount_due - charge.amount_paid

        if amount > outstanding_balance:
            raise PaymentAllocationError(
                f"Allocation exceeds the outstanding balance "
                f"for rent charge {charge.pk}."
            )

        # Record the allocation.
        allocation = PaymentAllocation.objects.create(
            payment=payment,
            rent_charge=charge,
            amount=amount,
        )

        # Update the rent charge balance.
        charge.amount_paid += amount

        if charge.amount_paid >= charge.amount_due:
            charge.amount_paid = charge.amount_due
            charge.status = RentCharge.Status.PAID
        else:
            charge.status = RentCharge.Status.PARTIALLY_PAID

        charge.save(
            update_fields=[
                "amount_paid",
                "status",
                "updated_at",
            ]
        )

        created_allocations.append(allocation)

    return created_allocations