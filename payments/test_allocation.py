from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import LandlordAccount
from billing.models import RentCharge
from leases.models import Lease
from payments.models import Payment, PaymentAllocation
from payments.services.allocation import (
    PaymentAllocationError,
    allocate_payment,
)
from properties.models import Property, RentalUnit
from tenants.models import Tenant


User = get_user_model()


class PaymentAllocationTests(TestCase):

    def setUp(self):
        # Create a platform user.
        self.user = User.objects.create_user(
            username="allocationowner",
            email="allocation@example.com",
            password="test-password",
        )

        # Create landlord account.
        self.landlord = LandlordAccount.objects.create(
            name="Allocation Test Landlord",
            slug="allocation-test-landlord",
            created_by=self.user,
        )

        # Create property.
        self.property = Property.objects.create(
            landlord=self.landlord,
            name="Sunrise Apartments",
            address="Nyeri Town",
            town="Nyeri",
            county="Nyeri",
        )

        # Create rental unit.
        self.unit = RentalUnit.objects.create(
            property=self.property,
            unit_number="A101",
            rent_amount=Decimal("10000.00"),
            bedrooms=2,
            bathrooms=1,
            status=RentalUnit.Status.OCCUPIED,
        )

        # Create tenant.
        self.tenant = Tenant.objects.create(
            landlord=self.landlord,
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone_number="0712345678",
        )

        # Create active lease.
        self.lease = Lease.objects.create(
            tenant=self.tenant,
            unit=self.unit,
            start_date=date(2026, 1, 1),
            monthly_rent=Decimal("10000.00"),
            security_deposit=Decimal("10000.00"),
            currency="KES",
            billing_day=1,
            status=Lease.Status.ACTIVE,
            created_by=self.user,
        )

        # Create January rent charge.
        self.charge = RentCharge.objects.create(
            lease=self.lease,
            description="January 2026 Rent",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            due_date=date(2026, 1, 5),
            amount_due=Decimal("10000.00"),
            amount_paid=Decimal("0.00"),
            currency="KES",
        )

        # Create a successful M-Pesa payment.
        self.payment = Payment.objects.create(
            landlord=self.landlord,
            tenant=self.tenant,
            lease=self.lease,
            amount=Decimal("12000.00"),
            currency="KES",
            phone_number="0712345678",
            status=Payment.Status.SUCCESSFUL,
            mpesa_receipt_number="ALLOC12345",
        )

    def create_charge(
        self,
        description,
        period_start,
        period_end,
        due_date,
        amount_due,
        unit=None,
        tenant=None,
        landlord=None,
    ):
        """Helper for creating additional rent charges."""

        landlord = landlord or self.landlord
        tenant = tenant or self.tenant
        unit = unit or self.unit

        lease = Lease.objects.create(
            tenant=tenant,
            unit=unit,
            start_date=period_start,
            monthly_rent=Decimal(str(amount_due)),
            security_deposit=Decimal("0.00"),
            currency="KES",
            billing_day=1,
            status=Lease.Status.ACTIVE,
            created_by=self.user,
        )

        return RentCharge.objects.create(
            lease=lease,
            description=description,
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            amount_due=Decimal(str(amount_due)),
            amount_paid=Decimal("0.00"),
            currency="KES",
        )

    def test_successful_full_payment_allocation(self):

        result = allocate_payment(
            self.payment,
            [
                {
                    "rent_charge_id": self.charge.pk,
                    "amount": "10000.00",
                }
            ],
        )

        self.assertEqual(len(result), 1)

        self.charge.refresh_from_db()

        self.assertEqual(
            self.charge.amount_paid,
            Decimal("10000.00"),
        )

        self.assertEqual(
            self.charge.status,
            RentCharge.Status.PAID,
        )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            1,
        )

    def test_partial_payment_allocation(self):

        result = allocate_payment(
            self.payment,
            [
                {
                    "rent_charge_id": self.charge.pk,
                    "amount": "4000.00",
                }
            ],
        )

        self.assertEqual(len(result), 1)

        self.charge.refresh_from_db()

        self.assertEqual(
            self.charge.amount_paid,
            Decimal("4000.00"),
        )

        self.assertEqual(
            self.charge.status,
            RentCharge.Status.PARTIALLY_PAID,
        )

        self.assertEqual(
            self.charge.balance_due,
            Decimal("6000.00"),
        )

    def test_one_payment_can_settle_multiple_charges(self):

        second_charge = self.create_charge(
            description="February 2026 Rent",
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            due_date=date(2026, 2, 5),
            amount_due="10000.00",
        )

        result = allocate_payment(
            self.payment,
            [
                {
                    "rent_charge_id": self.charge.pk,
                    "amount": "7000.00",
                },
                {
                    "rent_charge_id": second_charge.pk,
                    "amount": "5000.00",
                },
            ],
        )

        self.assertEqual(len(result), 2)

        self.charge.refresh_from_db()
        second_charge.refresh_from_db()

        self.assertEqual(
            self.charge.amount_paid,
            Decimal("7000.00"),
        )

        self.assertEqual(
            second_charge.amount_paid,
            Decimal("5000.00"),
        )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            2,
        )

    def test_allocation_cannot_exceed_payment_amount(self):

        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [
                    {
                        "rent_charge_id": self.charge.pk,
                        "amount": "13000.00",
                    }
                ],
            )

        self.charge.refresh_from_db()

        self.assertEqual(
            self.charge.amount_paid,
            Decimal("0.00"),
        )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            0,
        )

    def test_allocation_cannot_exceed_charge_balance(self):

        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [
                    {
                        "rent_charge_id": self.charge.pk,
                        "amount": "11000.00",
                    }
                ],
            )

        self.charge.refresh_from_db()

        self.assertEqual(
            self.charge.amount_paid,
            Decimal("0.00"),
        )

    def test_duplicate_charge_in_same_request_is_rejected(self):

        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [
                    {
                        "rent_charge_id": self.charge.pk,
                        "amount": "3000.00",
                    },
                    {
                        "rent_charge_id": self.charge.pk,
                        "amount": "2000.00",
                    },
                ],
            )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            0,
        )

    def test_same_payment_cannot_be_allocated_twice_to_same_charge(self):

        allocate_payment(
            self.payment,
            [
                {
                    "rent_charge_id": self.charge.pk,
                    "amount": "3000.00",
                }
            ],
        )

        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [
                    {
                        "rent_charge_id": self.charge.pk,
                        "amount": "2000.00",
                    }
                ],
            )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            1,
        )

    def test_unsuccessful_payment_cannot_be_allocated(self):

        self.payment.status = Payment.Status.PENDING
        self.payment.save(update_fields=["status"])

        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [
                    {
                        "rent_charge_id": self.charge.pk,
                        "amount": "5000.00",
                    }
                ],
            )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            0,
        )

    def test_payment_cannot_be_allocated_to_another_tenant(self):

        another_tenant = Tenant.objects.create(
            landlord=self.landlord,
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone_number="0722345678",
        )

        another_charge = self.create_charge(
            description="Jane's Rent",
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            due_date=date(2026, 3, 5),
            amount_due="10000.00",
            tenant=another_tenant,
        )

        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [
                    {
                        "rent_charge_id": another_charge.pk,
                        "amount": "5000.00",
                    }
                ],
            )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            0,
        )

    def test_payment_cannot_be_allocated_to_another_landlord(self):

        another_landlord = LandlordAccount.objects.create(
            name="Another Landlord",
            slug="another-landlord",
            created_by=self.user,
        )

        another_property = Property.objects.create(
            landlord=another_landlord,
            name="Another Property",
            address="Nairobi",
            town="Nairobi",
            county="Nairobi",
        )

        another_unit = RentalUnit.objects.create(
            property=another_property,
            unit_number="B101",
            rent_amount=Decimal("10000.00"),
        )

        another_tenant = Tenant.objects.create(
            landlord=another_landlord,
            first_name="Peter",
            last_name="Kamau",
            phone_number="0732345678",
        )

        another_charge = self.create_charge(
            description="Another Landlord Rent",
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            due_date=date(2026, 4, 5),
            amount_due="10000.00",
            tenant=another_tenant,
            unit=another_unit,
            landlord=another_landlord,
        )

        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [
                    {
                        "rent_charge_id": another_charge.pk,
                        "amount": "5000.00",
                    }
                ],
            )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            0,
        )

    def test_void_rent_charge_cannot_receive_payment(self):

        self.charge.status = RentCharge.Status.VOID
        self.charge.save(update_fields=["status"])

        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [
                    {
                        "rent_charge_id": self.charge.pk,
                        "amount": "5000.00",
                    }
                ],
            )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            0,
        )

    def test_currency_mismatch_is_rejected(self):

        self.charge.currency = "USD"
        self.charge.save(update_fields=["currency"])

        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [
                    {
                        "rent_charge_id": self.charge.pk,
                        "amount": "5000.00",
                    }
                ],
            )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            0,
        )

    def test_failed_batch_rolls_back_previous_allocations(self):

        second_charge = self.create_charge(
            description="February 2026 Rent",
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            due_date=date(2026, 2, 5),
            amount_due="10000.00",
        )

        # The first allocation is valid.
        # The second allocation exceeds the charge balance.
        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [
                    {
                        "rent_charge_id": self.charge.pk,
                        "amount": "5000.00",
                    },
                    {
                        "rent_charge_id": second_charge.pk,
                        "amount": "15000.00",
                    },
                ],
            )

        self.charge.refresh_from_db()
        second_charge.refresh_from_db()

        # Both charges should remain unchanged.
        self.assertEqual(
            self.charge.amount_paid,
            Decimal("0.00"),
        )

        self.assertEqual(
            second_charge.amount_paid,
            Decimal("0.00"),
        )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            0,
        )

    def test_allocated_amount_cannot_have_more_than_two_decimal_places(self):

        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [
                    {
                        "rent_charge_id": self.charge.pk,
                        "amount": "1000.001",
                    }
                ],
            )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            0,
        )

    def test_empty_allocation_request_is_rejected(self):

        with self.assertRaises(PaymentAllocationError):
            allocate_payment(
                self.payment,
                [],
            )

        self.assertEqual(
            PaymentAllocation.objects.count(),
            0,
        )