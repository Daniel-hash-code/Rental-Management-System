from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, LandlordAccount, Membership


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "role",
        "is_staff",
        "is_active",
    )

    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
    )

    fieldsets = UserAdmin.fieldsets + (
        ("RentFlow Information", {
            "fields": ("phone_number", "role"),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("RentFlow Information", {
            "fields": ("email", "phone_number", "role"),
        }),
    )


@admin.register(LandlordAccount)
class LandlordAccountAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "slug",
        "created_by",
        "created_at",
    )

    search_fields = (
        "name",
        "slug",
        "created_by__username",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "landlord",
        "role",
        "status",
        "joined_at",
    )

    list_filter = (
        "role",
        "status",
    )

    search_fields = (
        "user__username",
        "user__email",
        "landlord__name",
    )

    autocomplete_fields = (
        "user",
        "landlord",
    )

    readonly_fields = ("joined_at",)
