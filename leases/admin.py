
from django.contrib import admin
from .models import Lease


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):

    list_display = (
        "tenant",
        "unit",
        "start_date",
        "end_date",
        "monthly_rent",
        "currency",
        "status",
        "billing_day",
    )

    list_filter = (
        "status",
        "currency",
        "start_date",
        "created_at",
    )

    search_fields = (
        "tenant__first_name",
        "tenant__last_name",
        "tenant__phone_number",
        "unit__unit_number",
        "unit__property__name",
    )

    autocomplete_fields = (
        "tenant",
        "unit",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    date_hierarchy = "start_date"

    fieldsets = (
        (
            "Lease Parties",
            {
                "fields": (
                    "tenant",
                    "unit",
                    "created_by",
                )
            }
        ),
        (
            "Lease Period",
            {
                "fields": (
                    "start_date",
                    "end_date",
                    "status",
                )
            }
        ),
        (
            "Financial Agreement",
            {
                "fields": (
                    "monthly_rent",
                    "security_deposit",
                    "currency",
                    "billing_day",
                )
            }
        ),
        (
            "Agreement Terms",
            {
                "fields": (
                    "terms_and_conditions",
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
