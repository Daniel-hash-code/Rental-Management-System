
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User, LandlordAccount
from properties.models import Property, RentalUnit
from tenants.models import Tenant
from leases.models import Lease

from billing.models import RentCharge
from billing.services.rent_generation import (
    calculate_prorated_rent,
    generate_monthly_charges,
    refresh_charge_status,
)


class BillingTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="billinglandlord",
            email="billing@example.com",
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
            currency="KES"
        )

        self.tenant = Tenant.objects.create(
            landlord=self.landlord,
            first_name="John",
            last_name="Kamau",
            phone_number="0712345678"
        )

        self.lease = Lease.objects.create(
            tenant=self.tenant,
            unit=self.unit,
            start_date=date(2027, 1, 15),
            end_date=date(2027, 3, 15),
            monthly_rent=Decimal("12000.00"),
            security_deposit=Decimal("12000.00"),
            currency="KES",
            billing_day=1,
            status=Lease.Status.ACTIVE,
            created_by=self.user
        )

    def test_prorated_rent_calculation(self):

        amount = calculate_prorated_rent(
            Decimal("12000.00"),
            17,
            31
        )

        self.assertEqual(
            amount,
            Decimal("6580.65")
        )

    def test_generate_three_monthly_charges(self):

        charges = generate_monthly_charges(
            self.lease,
            through_date=date(2027, 3, 20)
        )

        self.assertEqual(len(charges), 3)

        self.assertEqual(
            charges[0].amount_due,
            Decimal("6580.65")
        )

        self.assertEqual(
            charges[1].amount_due,
            Decimal("12000.00")
        )

        self.assertEqual(
            charges[2].amount_due,
            Decimal("5806.45")
        )

    def test_first_charge_due_date(self):

        charges = generate_monthly_charges(
            self.lease,
            through_date=date(2027, 1, 20)
        )

        self.assertEqual(
            charges[0].due_date,
            date(2027, 1, 15)
        )

    def test_duplicate_charges_are_not_generated(self):

        first_run = generate_monthly_charges(
            self.lease,
            through_date=date(2027, 3, 20)
        )

        second_run = generate_monthly_charges(
            self.lease,
            through_date=date(2027, 3, 20)
        )

        self.assertEqual(len(first_run), 3)
        self.assertEqual(len(second_run), 0)

        self.assertEqual(
            RentCharge.objects.filter(
                lease=self.lease
            ).count(),
            3
        )

    def test_inactive_lease_cannot_generate_charges(self):

        self.lease.status = Lease.Status.DRAFT
        self.lease.save()

        with self.assertRaises(ValueError):
            generate_monthly_charges(
                self.lease,
                through_date=date(2027, 3, 20)
            )

    def test_partial_payment_updates_status(self):

        charge = generate_monthly_charges(
            self.lease,
            through_date=date(2027, 1, 20)
        )[0]

        charge.amount_paid = Decimal("2000.00")
        charge.save()

        refresh_charge_status(
            charge,
            as_of=date(2027, 1, 20)
        )

        charge.refresh_from_db()

        self.assertEqual(
            charge.status,
            RentCharge.Status.PARTIALLY_PAID
        )

        self.assertEqual(
            charge.balance_due,
            Decimal("4580.65")
        )

    def test_full_payment_updates_status(self):

        charge = generate_monthly_charges(
            self.lease,
            through_date=date(2027, 1, 20)
        )[0]

        charge.amount_paid = charge.amount_due
        charge.save()

        refresh_charge_status(
            charge,
            as_of=date(2027, 1, 20)
        )

        charge.refresh_from_db()

        self.assertEqual(
            charge.status,
            RentCharge.Status.PAID
        )

        self.assertEqual(
            charge.balance_due,
            Decimal("0.00")
        )

    def test_overdue_charge_status(self):

        charge = generate_monthly_charges(
            self.lease,
            through_date=date(2027, 1, 20)
        )[0]

        refresh_charge_status(
            charge,
            as_of=date(2027, 1, 20)
        )

        charge.refresh_from_db()

        self.assertEqual(
            charge.status,
            RentCharge.Status.OVERDUE
        )

    def test_charge_cannot_be_paid_above_amount_due(self):

        charge = generate_monthly_charges(
            self.lease,
            through_date=date(2027, 1, 20)
        )[0]

        charge.amount_paid = (
            charge.amount_due + Decimal("100.00")
        )

        with self.assertRaises(ValidationError):
            charge.full_clean()
