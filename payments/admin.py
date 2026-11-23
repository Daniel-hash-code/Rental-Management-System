
from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "tenant",
        "landlord",
        "amount",
        "phone_number",
        "status",
        "mpesa_receipt_number",
        "created_at",
    )

    list_filter = (
        "status",
        "currency",
        "created_at",
    )

    search_fields = (
        "tenant__first_name",
        "tenant__last_name",
        "phone_number",
        "checkout_request_id",
        "mpesa_receipt_number",
    )

    readonly_fields = (
        "merchant_request_id",
        "checkout_request_id",
        "mpesa_receipt_number",
        "result_code",
        "result_description",
        "callback_payload",
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)
