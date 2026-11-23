
from django.contrib import admin

from .models import Property, RentalUnit


class RentalUnitInline(admin.TabularInline):

    model = RentalUnit

    extra = 1

    fields = (
        "unit_number",
        "rent_amount",
        "currency",
        "bedrooms",
        "bathrooms",
        "status",
    )


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "landlord",
        "property_type",
        "town",
        "county",
        "created_at",
    )

    list_filter = (
        "property_type",
        "county",
        "town",
    )

    search_fields = (
        "name",
        "landlord__name",
        "address",
        "town",
        "county",
    )

    autocomplete_fields = ("landlord",)

    inlines = [RentalUnitInline]

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(RentalUnit)
class RentalUnitAdmin(admin.ModelAdmin):

    list_display = (
        "unit_number",
        "property",
        "rent_amount",
        "currency",
        "bedrooms",
        "status",
    )

    list_filter = (
        "status",
        "bedrooms",
        "currency",
    )

    search_fields = (
        "unit_number",
        "property__name",
        "property__landlord__name",
    )

    autocomplete_fields = ("property",)

    readonly_fields = (
        "created_at",
        "updated_at",
    )
