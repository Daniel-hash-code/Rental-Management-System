from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.shortcuts import render

from billing.models import RentCharge
from leases.models import Lease
from payments.models import Payment


@login_required
def tenant_dashboard(request):
    """
    Display all tenant profiles belonging to the logged-in user.

    A tenant cannot supply another tenant's ID to access
    their information.
    """

    tenant_profiles = (
        request.user.tenant_profiles
        .select_related("landlord")
        .all()
    )

    active_leases = (
        Lease.objects
        .filter(
            tenant__user=request.user,
            tenant__status="active",
            status=Lease.Status.ACTIVE,
        )
        .select_related(
            "tenant",
            "unit",
            "unit__property",
        )
    )

    outstanding_charges = (
        RentCharge.objects
        .filter(
            lease__tenant__user=request.user,
            lease__status=Lease.Status.ACTIVE,
        )
        .exclude(status=RentCharge.Status.VOID)
        .annotate(
            outstanding_balance=(
                F("amount_due") - F("amount_paid")
            )
        )
        .filter(outstanding_balance__gt=0)
        .select_related(
            "lease",
            "lease__tenant",
            "lease__unit",
            "lease__unit__property",
        )
        .order_by("due_date")
    )

    total_outstanding = sum(
        (
            charge.outstanding_balance
            for charge in outstanding_charges
        ),
        start=0,
    )

    recent_payments = (
        Payment.objects
        .filter(tenant__user=request.user)
        .select_related("tenant", "lease")
        .order_by("-created_at")[:10]
    )

    # Include payments initiated by other means or users,
    # provided they belong to one of this user's tenant profiles.
    from payments.models import Payment

    recent_payments = (
        Payment.objects
        .filter(tenant__user=request.user)
        .select_related("tenant", "lease")
        .order_by("-created_at")[:10]
    )

    return render(
        request,
        "tenants/dashboard.html",
        {
            "tenant_profiles": tenant_profiles,
            "active_leases": active_leases,
            "outstanding_charges": outstanding_charges,
            "total_outstanding": total_outstanding,
            "recent_payments": recent_payments,
        },
    )