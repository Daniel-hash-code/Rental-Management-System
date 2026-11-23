
from django.contrib import admin

from .models import RentCharge


@admin.register(RentCharge)
class RentChargeAdmin(admin.ModelAdmin):

    list_display = (
        "lease",
        "period_start",
        "period_end",
        "due_date",
        "amount_due",
        "amount_paid",
        "balance_due_display",
        "currency",
        "status",
    )

    list_filter = (
        "status",
        "currency",
        "due_date",
    )

    search_fields = (
        "lease__tenant__first_name",
        "lease__tenant__last_name",
        "lease__tenant__phone_number",
        "lease__unit__unit_number",
        "lease__unit__property__name",
    )

    autocomplete_fields = ("lease",)

    readonly_fields = (
        "amount_paid",
        "created_at",
        "updated_at",
    )

    date_hierarchy = "due_date"

    fieldsets = (
        (
            "Rent Charge",
            {
                "fields": (
                    "lease",
                    "description",
                    "period_start",
                    "period_end",
                    "due_date",
                )
            }
        ),
        (
            "Financial Details",
            {
                "fields": (
                    "amount_due",
                    "amount_paid",
                    "currency",
                    "status",
                )
            }
        ),
        (
            "Record Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            }
        ),
    )

    @admin.display(description="Balance Due")
    def balance_due_display(self, obj):
        return obj.balance_due
