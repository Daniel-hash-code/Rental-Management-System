
import calendar

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from leases.models import Lease
from billing.models import RentCharge


CENT = Decimal("0.01")


def add_months(year, month, offset):
    """
    Return the year and month after adding offset months.
    """

    month_index = (year * 12) + (month - 1) + offset

    new_year = month_index // 12
    new_month = (month_index % 12) + 1

    return new_year, new_month


def calculate_prorated_rent(
    monthly_rent,
    occupied_days,
    days_in_month
):
    """
    Calculate rent for part of a calendar month.
    """

    amount = (
        monthly_rent
        * Decimal(occupied_days)
        / Decimal(days_in_month)
    )

    return amount.quantize(
        CENT,
        rounding=ROUND_HALF_UP
    )


def get_billing_periods(lease, through_date):
    """
    Generate calendar-month billing periods that intersect
    the lease and begin on or before through_date.

    Lease end dates are inclusive.
    """

    year = lease.start_date.year
    month = lease.start_date.month

    while True:

        month_start = date(year, month, 1)

        if month_start > through_date:
            break

        last_day = calendar.monthrange(year, month)[1]

        month_end = date(year, month, last_day)

        period_start = max(
            lease.start_date,
            month_start
        )

        period_end = month_end

        if lease.end_date:
            period_end = min(
                period_end,
                lease.end_date
            )

        if period_start <= period_end:

            days_in_month = last_day

            occupied_days = (
                period_end - period_start
            ).days + 1

            if occupied_days == days_in_month:
                amount = lease.monthly_rent
            else:
                amount = calculate_prorated_rent(
                    lease.monthly_rent,
                    occupied_days,
                    days_in_month
                )

            configured_due_date = date(
                year,
                month,
                lease.billing_day
            )

            # The first charge cannot be due before
            # the tenant's lease start date.
            due_date = max(
                configured_due_date,
                period_start
            )

            yield {
                "period_start": period_start,
                "period_end": period_end,
                "due_date": due_date,
                "amount_due": amount,
            }

        year, month = add_months(year, month, 1)


@transaction.atomic
def generate_monthly_charges(lease, through_date=None):
    """
    Generate rent charges for an active lease.

    Existing charges are not duplicated.
    Returns the list of newly created charges.
    """

    if through_date is None:
        through_date = timezone.localdate()

    if not isinstance(through_date, date):
        raise ValueError("through_date must be a date.")

    # Lock the lease row to reduce the risk of two
    # concurrent billing requests generating duplicates.
    locked_lease = (
        Lease.objects
        .select_for_update()
        .select_related("tenant", "unit")
        .get(pk=lease.pk)
    )

    if locked_lease.status != Lease.Status.ACTIVE:
        raise ValueError(
            "Rent charges can only be generated for active leases."
        )

    if locked_lease.start_date > through_date:
        return []

    if (
        locked_lease.end_date
        and locked_lease.end_date < locked_lease.start_date
    ):
        raise ValueError("The lease dates are invalid.")

    created_charges = []

    for period in get_billing_periods(
        locked_lease,
        through_date
    ):

        initial_status = (
            RentCharge.Status.OVERDUE
            if period["due_date"] < through_date
            else RentCharge.Status.UNPAID
        )

        charge, created = RentCharge.objects.get_or_create(
            lease=locked_lease,
            period_start=period["period_start"],
            defaults={
                "description": "Monthly Rent",
                "period_end": period["period_end"],
                "due_date": period["due_date"],
                "amount_due": period["amount_due"],
                "amount_paid": Decimal("0.00"),
                "currency": locked_lease.currency,
                "status": initial_status,
            }
        )

        if created:
            created_charges.append(charge)

    return created_charges


def refresh_charge_status(charge, as_of=None):
    """
    Recalculate a charge's status after a payment allocation
    or when checking whether it has become overdue.
    """

    if as_of is None:
        as_of = timezone.localdate()

    if charge.status == RentCharge.Status.VOID:
        return charge

    if charge.amount_paid >= charge.amount_due:
        new_status = RentCharge.Status.PAID

    elif charge.amount_paid > 0:
        new_status = RentCharge.Status.PARTIALLY_PAID

    elif charge.due_date < as_of:
        new_status = RentCharge.Status.OVERDUE

    else:
        new_status = RentCharge.Status.UNPAID

    if charge.status != new_status:
        charge.status = new_status

        charge.save(
            update_fields=["status", "updated_at"]
        )

    return charge
