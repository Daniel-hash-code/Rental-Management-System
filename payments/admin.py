from .models import PaymentAllocation
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

@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "payment",
        "rent_charge",
        "amount",
        "created_at",
    )

    list_filter = ("created_at",)

    search_fields = (
        "payment__mpesa_receipt_number",
        "payment__tenant__first_name",
        "payment__tenant__last_name",
        "rent_charge__description",
    )

    readonly_fields = ("created_at",)

    def has_add_permission(self, request):
        # Allocations should be created through the allocation service.
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False