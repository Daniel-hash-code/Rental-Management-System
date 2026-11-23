
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User, LandlordAccount
from properties.models import Property, RentalUnit
from tenants.models import Tenant
from leases.models import Lease


class LeaseModelTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="landlord1",
            email="landlord1@example.com",
            password="TestPassword123!"
        )

        self.landlord = LandlordAccount.objects.create(
            name="Green Homes",
            slug="green-homes",
            created_by=self.user
        )

        self.property = Property.objects.create(
            landlord=self.landlord,
            name="Green Apartments",
            property_type=Property.PropertyType.APARTMENT,
            address="Nyeri Town",
            town="Nyeri",
            county="Nyeri"
        )

        self.unit = RentalUnit.objects.create(
            property=self.property,
            unit_number="A101",
            rent_amount=Decimal("12000.00"),
            currency="KES",
            bedrooms=2,
            bathrooms=1
        )

        self.tenant = Tenant.objects.create(
            landlord=self.landlord,
            first_name="John",
            last_name="Kamau",
            phone_number="0712345678"
        )

    def create_lease(
        self,
        start_date=date(2027, 1, 1),
        end_date=date(2027, 12, 31),
        status=Lease.Status.DRAFT
    ):

        return Lease.objects.create(
            tenant=self.tenant,
            unit=self.unit,
            start_date=start_date,
            end_date=end_date,
            monthly_rent=Decimal("12000.00"),
            security_deposit=Decimal("12000.00"),
            currency="KES",
            billing_day=1,
            status=status,
            created_by=self.user
        )

    def test_create_lease(self):

        lease = self.create_lease()

        self.assertEqual(
            lease.monthly_rent,
            Decimal("12000.00")
        )

        self.assertEqual(
            lease.status,
            Lease.Status.DRAFT
        )

    def test_end_date_cannot_precede_start_date(self):

        lease = Lease(
            tenant=self.tenant,
            unit=self.unit,
            start_date=date(2027, 12, 31),
            end_date=date(2027, 1, 1),
            monthly_rent=Decimal("12000.00")
        )

        with self.assertRaises(ValidationError):
            lease.full_clean()

    def test_tenant_and_unit_must_share_landlord(self):

        another_user = User.objects.create_user(
            username="landlord2",
            email="landlord2@example.com",
            password="TestPassword123!"
        )

        another_landlord = LandlordAccount.objects.create(
            name="Blue Homes",
            slug="blue-homes",
            created_by=another_user
        )

        another_property = Property.objects.create(
            landlord=another_landlord,
            name="Blue Apartments",
            property_type=Property.PropertyType.APARTMENT,
            address="Karatina",
            town="Karatina",
            county="Nyeri"
        )

        another_unit = RentalUnit.objects.create(
            property=another_property,
            unit_number="B101",
            rent_amount=Decimal("15000.00")
        )

        lease = Lease(
            tenant=self.tenant,
            unit=another_unit,
            start_date=date(2027, 1, 1),
            monthly_rent=Decimal("15000.00")
        )

        with self.assertRaises(ValidationError):
            lease.full_clean()

    def test_overlapping_active_leases_are_rejected(self):

        self.create_lease(
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            status=Lease.Status.ACTIVE
        )

        overlapping_lease = Lease(
            tenant=self.tenant,
            unit=self.unit,
            start_date=date(2027, 6, 1),
            end_date=date(2028, 5, 31),
            monthly_rent=Decimal("12000.00"),
            status=Lease.Status.ACTIVE
        )

        with self.assertRaises(ValidationError):
            overlapping_lease.full_clean()

    def test_non_overlapping_active_leases_are_allowed(self):

        self.create_lease(
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            status=Lease.Status.ACTIVE
        )

        next_lease = Lease(
            tenant=self.tenant,
            unit=self.unit,
            start_date=date(2028, 1, 1),
            end_date=date(2028, 12, 31),
            monthly_rent=Decimal("13000.00"),
            status=Lease.Status.ACTIVE
        )

        next_lease.full_clean()

        self.assertEqual(
            next_lease.status,
            Lease.Status.ACTIVE
        )

    def test_monthly_rent_must_be_positive(self):

        lease = Lease(
            tenant=self.tenant,
            unit=self.unit,
            start_date=date(2027, 1, 1),
            monthly_rent=Decimal("0.00")
        )

        with self.assertRaises(ValidationError):
            lease.full_clean()
