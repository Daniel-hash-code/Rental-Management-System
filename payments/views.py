import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.contrib import messages
from django.shortcuts import ( get_object_or_404, redirect, render,)
from payments.forms import TenantPaymentForm
from payments.models import Payment

from payments.services.daraja import ( process_stk_callback, initiate_stk_push, DarajaAPIError,)

# Daraja Callback
@csrf_exempt
@require_POST
def stk_callback(request):
    """
    Public endpoint receiving Safaricom STK Push callbacks.
    """

    try:
        payload = json.loads(request.body)

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid JSON payload."},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": "Invalid callback structure."},
            status=400,
        )

    try:
        process_stk_callback(payload)

    except Exception:
        # Do not expose internal errors to the callback sender.
        # Production logging and alerting should capture details.
        return JsonResponse(
            {"ResultCode": 1, "ResultDesc": "Processing error"},
            status=500,
        )

    # Acknowledge the callback without revealing payment details.
    return JsonResponse(
        {
            "ResultCode": 0,
            "ResultDesc": "Callback received successfully.",
        },
        status=200,
    )

# Tenant Payment Initiation
@login_required
def initiate_payment(request):

    if request.method == "POST":

        form = TenantPaymentForm(
            request.POST,
            user=request.user,
        )

        if form.is_valid():

            lease = form.cleaned_data["lease"]
            amount = form.cleaned_data["amount"]
            phone_number = form.cleaned_data["phone_number"]

            payment = Payment.objects.create(
                landlord=lease.tenant.landlord,
                tenant=lease.tenant,
                lease=lease,
                initiated_by=request.user,
                amount=amount,
                currency=lease.currency,
                phone_number=phone_number,
                status=Payment.Status.INITIATED,
                account_reference=f"RF{lease.pk}",
                transaction_description="Rent payment",
            )

            try:

                initiate_stk_push(payment)

                messages.success(
                    request,
                    "Your M-Pesa payment request has been sent. "
                    "Check your phone and enter your M-Pesa PIN.",
                )

            except DarajaAPIError:

                payment.refresh_from_db()

                messages.warning(
                    request,
                    "We could not confirm the STK Push request. "
                    "Check your payment history before attempting "
                    "another payment.",
                )

            except ValueError as exc:

                messages.error(request, str(exc))

            return redirect(
                "payments:history"
            )

    else:

        form = TenantPaymentForm(
            user=request.user,
        )

    return render(
        request,
        "payments/payment_form.html",
        {"form": form},
    )

# Payment history
@login_required
def payment_history(request):

    payments = (
        Payment.objects
        .filter(tenant__user=request.user)
        .select_related(
            "tenant",
            "lease",
            "lease__unit",
            "lease__unit__property",
        )
        .order_by("-created_at")
    )

    return render(
        request,
        "payments/payment_history.html",
        {"payments": payments},
    )

# Payment details
@login_required
def payment_detail(request, pk):

    payment = get_object_or_404(
        Payment.objects.select_related(
            "tenant",
            "lease",
            "lease__unit",
            "lease__unit__property",
        ),
        pk=pk,
        tenant__user=request.user,
    )

    return render(
        request,
        "payments/payment_detail.html",
        {
            "payment": payment,
        },
    )

# Successful Payment Receipt
@login_required
def payment_receipt(request, pk):

    payment = get_object_or_404(
        Payment.objects.select_related(
            "tenant",
            "lease",
            "lease__unit",
            "lease__unit__property",
        ),
        pk=pk,
        tenant__user=request.user,
        status=Payment.Status.SUCCESSFUL,
    )

    return render(
        request,
        "payments/payment_detail.html",
        {
            "payment": payment,
            "is_receipt": True,
        },
    )