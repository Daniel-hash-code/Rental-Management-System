
from django.db import models
from accounts.models import LandlordAccount


class Property(models.Model):

    class PropertyType(models.TextChoices):
        APARTMENT = "apartment", "Apartment"
        RESIDENTIAL = "residential", "Residential House"
        COMMERCIAL = "commercial", "Commercial"
        MIXED = "mixed", "Mixed Use"
        OTHER = "other", "Other"

    landlord = models.ForeignKey(
        LandlordAccount,
        on_delete=models.PROTECT,
        related_name="properties"
    )

    name = models.CharField(max_length=150)

    property_type = models.CharField(
        max_length=20,
        choices=PropertyType.choices,
        default=PropertyType.APARTMENT
    )

    address = models.CharField(max_length=255)

    town = models.CharField(max_length=100)

    county = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Properties"

    def __str__(self):
        return f"{self.name} - {self.landlord.name}"


class RentalUnit(models.Model):

    class Status(models.TextChoices):
        VACANT = "vacant", "Vacant"
        OCCUPIED = "occupied", "Occupied"
        MAINTENANCE = "maintenance", "Under Maintenance"
        INACTIVE = "inactive", "Inactive"

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="units"
    )

    unit_number = models.CharField(max_length=50)

    rent_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    currency = models.CharField(
        max_length=3,
        default="KES"
    )

    bedrooms = models.PositiveSmallIntegerField(default=1)

    bathrooms = models.PositiveSmallIntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.VACANT
    )

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["property", "unit_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["property", "unit_number"],
                name="unique_unit_number_per_property"
            )
        ]

    def __str__(self):
        return f"{self.property.name} - Unit {self.unit_number}"
