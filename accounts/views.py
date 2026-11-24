from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from accounts.models import Membership, LandlordAccount
from tenants.models import Tenant
from payments.models import Payment
from properties.models import Property, RentalUnit
from leases.models import Lease
from billing.models import RentCharge
    


@login_required
def dashboard(request):
    """
    Central dashboard selector.

    A user may have access to tenant and landlord portals.
    We show the available portals instead of assuming
    that a user can belong to only one category.
    """

    tenant_profiles = (
        Tenant.objects
        .filter(user=request.user)
        .select_related("landlord")
    )

    memberships = (
        Membership.objects
        .filter(
            user=request.user,
            status=Membership.Status.ACTIVE,
        )
        .select_related("landlord")
    )

    return render(
        request,
        "accounts/dashboard.html",
        {
            "tenant_profiles": tenant_profiles,
            "memberships": memberships,
        },
    )


@login_required
def landlord_dashboard(request, slug):
    """
    Display information for one landlord account.

    Access is granted only through an active membership.
    """

    membership = get_object_or_404(
        Membership.objects.select_related("landlord"),
        user=request.user,
        landlord__slug=slug,
        status=Membership.Status.ACTIVE,
    )

    landlord = membership.landlord

    properties = Property.objects.filter(
        landlord=landlord
    )

    units = RentalUnit.objects.filter(
        property__landlord=landlord
    )

    tenants = Tenant.objects.filter(
        landlord=landlord
    )

    active_leases = Lease.objects.filter(
        tenant__landlord=landlord,
        status=Lease.Status.ACTIVE,
    )

    outstanding_charges = (
        RentCharge.objects
        .filter(lease__tenant__landlord=landlord)
        .exclude(status=RentCharge.Status.VOID)
        .exclude(status=RentCharge.Status.PAID)
        .select_related(
            "lease",
            "lease__tenant",
            "lease__unit",
            "lease__unit__property",
        )
        .order_by("due_date")
    )

    successful_payments = Payment.objects.filter(
        landlord=landlord,
        status=Payment.Status.SUCCESSFUL,
    )

    from django.db.models import Sum

    total_collected = (
        successful_payments.aggregate(
            total=Sum("amount")
        )["total"] or 0
    )

    latest_payments = (
        Payment.objects
        .filter(landlord=landlord)
        .select_related("tenant")
        .order_by("-created_at")[:10]
    )

    return render(
        request,
        "accounts/landlord_dashboard.html",
        {
            "landlord": landlord,
            "membership": membership,
            "properties_count": properties.count(),
            "units_count": units.count(),
            "tenants_count": tenants.count(),
            "active_leases_count": active_leases.count(),
            "outstanding_charges": outstanding_charges[:10],
            "outstanding_count": outstanding_charges.count(),
            "total_collected": total_collected,
            "latest_payments": latest_payments,
        },
    )