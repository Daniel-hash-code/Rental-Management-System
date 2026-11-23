
from django.contrib import admin
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):

    list_display = (
        "first_name",
        "last_name",
        "landlord",
        "phone_number",
        "email",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "landlord",
        "created_at",
    )

    search_fields = (
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "landlord__name",
    )

    autocomplete_fields = (
        "landlord",
        "user",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Tenant Information",
            {
                "fields": (
                    "landlord",
                    "user",
                    "first_name",
                    "last_name",
                    "email",
                    "phone_number",
                    "alternate_phone",
                    "status",
                )
            }
        ),
        (
            "Additional Information",
            {
                "fields": (
                    "address",
                    "emergency_contact_name",
                    "emergency_contact_phone",
                    "notes",
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
