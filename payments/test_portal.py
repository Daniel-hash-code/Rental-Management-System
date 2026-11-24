
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import LandlordAccount
from billing.models import RentCharge
from leases.models import Lease
from payments.forms import TenantPaymentForm
from payments.models import Payment
from properties.models import Property, RentalUnit
from tenants.models import Tenant


User = get_user_model()


class PaymentPortalTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="TestPassword123!",
        )

        self.user1 = User.objects.create_user(
            username="tenant1",
            email="tenant1@example.com",
            password="TestPassword123!",
        )

        self.user2 = User.objects.create_user(
            username="tenant2",
            email="tenant2@example.com",
            password="TestPassword123!",
        )

        self.landlord = LandlordAccount.objects.create(
            name="Green Homes",
            slug="green-homes",
            created_by=self.owner,
        )

        self.property = Property.objects.create(
            landlord=self.landlord,
            name="Sunrise Apartments",
            address="Nyeri Town",
            town="Nyeri",
            county="Nyeri",
        )

        self.unit1 = RentalUnit.objects.create(
            property=self.property,
            unit_number="A101",
            rent_amount=Decimal("10000.00"),
        )

        self.unit2 = RentalUnit.objects.create(
            property=self.property,
            unit_number="A102",
            rent_amount=Decimal("12000.00"),
        )

        self.tenant1 = Tenant.objects.create(
            landlord=self.landlord,
            user=self.user1,
            first_name="John",
            last_name="Kamau",
            phone_number="0712345678",
        )

        self.tenant2 = Tenant.objects.create(
            landlord=self.landlord,
            user=self.user2,
            first_name="Mary",
            last_name="Wanjiku",
            phone_number="0723456789",
        )

        self.lease1 = Lease.objects.create(
            tenant=self.tenant1,
            unit=self.unit1,
            start_date=date(2026, 1, 1),
            monthly_rent=Decimal("10000.00"),
            security_deposit=Decimal("10000.00"),
            currency="KES",
            billing_day=1,
            status=Lease.Status.ACTIVE,
            created_by=self.owner,
        )

        self.lease2 = Lease.objects.create(
            tenant=self.tenant2,
            unit=self.unit2,
            start_date=date(2026, 1, 1),
            monthly_rent=Decimal("12000.00"),
            security_deposit=Decimal("12000.00"),
            currency="KES",
            billing_day=1,
            status=Lease.Status.ACTIVE,
            created_by=self.owner,
        )

        self.charge1 = RentCharge.objects.create(
            lease=self.lease1,
            description="January Rent",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            due_date=date(2026, 1, 5),
            amount_due=Decimal("10000.00"),
            amount_paid=Decimal("0.00"),
            currency="KES",
        )

        self.charge2 = RentCharge.objects.create(
            lease=self.lease2,
            description="January Rent",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            due_date=date(2026, 1, 5),
            amount_due=Decimal("12000.00"),
            amount_paid=Decimal("0.00"),
            currency="KES",
        )

        self.payment1 = Payment.objects.create(
            landlord=self.landlord,
            tenant=self.tenant1,
            lease=self.lease1,
            initiated_by=self.user1,
            amount=Decimal("5000.00"),
            currency="KES",
            phone_number="254712345678",
            status=Payment.Status.SUCCESSFUL,
            mpesa_receipt_number="TEST123456",
        )

        self.payment2 = Payment.objects.create(
            landlord=self.landlord,
            tenant=self.tenant2,
            lease=self.lease2,
            initiated_by=self.user2,
            amount=Decimal("6000.00"),
            currency="KES",
            phone_number="254723456789",
            status=Payment.Status.SUCCESSFUL,
            mpesa_receipt_number="TEST654321",
        )

    def test_payment_history_requires_login(self):
        response = self.client.get(
            reverse("payments:history")
        )

        self.assertEqual(response.status_code, 302)

    def test_tenant_can_view_own_payment_history(self):
        self.client.login(
            username="tenant1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("payments:history")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TEST123456")
        self.assertNotContains(response, "TEST654321")

    def test_tenant_cannot_view_another_tenants_payment_detail(self):
        self.client.login(
            username="tenant1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse(
                "payments:detail",
                kwargs={"pk": self.payment2.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_tenant_can_view_own_payment_detail(self):
        self.client.login(
            username="tenant1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse(
                "payments:detail",
                kwargs={"pk": self.payment1.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_tenant_cannot_access_another_tenants_receipt(self):
        self.client.login(
            username="tenant1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse(
                "payments:receipt",
                kwargs={"pk": self.payment2.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_tenant_can_access_own_successful_receipt(self):
        self.client.login(
            username="tenant1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse(
                "payments:receipt",
                kwargs={"pk": self.payment1.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_receipt_is_not_available_for_pending_payment(self):
        self.payment1.status = Payment.Status.PENDING
        self.payment1.save(update_fields=["status"])

        self.client.login(
            username="tenant1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse(
                "payments:receipt",
                kwargs={"pk": self.payment1.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_payment_initiation_page_requires_login(self):
        response = self.client.get(
            reverse("payments:initiate")
        )

        self.assertEqual(response.status_code, 302)

    def test_payment_form_rejects_another_tenants_lease(self):
        form = TenantPaymentForm(
            data={
                "lease": self.lease2.pk,
                "amount": "5000",
                "phone_number": "0712345678",
            },
            user=self.user1,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("lease", form.errors)

    def test_payment_form_rejects_amount_above_outstanding_balance(self):
        form = TenantPaymentForm(
            data={
                "lease": self.lease1.pk,
                "amount": "15000",
                "phone_number": "0712345678",
            },
            user=self.user1,
        )

        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_payment_form_accepts_valid_payment(self):
        form = TenantPaymentForm(
            data={
                "lease": self.lease1.pk,
                "amount": "5000",
                "phone_number": "0712345678",
            },
            user=self.user1,
        )

        self.assertTrue(form.is_valid(), form.errors)

        self.assertEqual(
            form.cleaned_data["phone_number"],
            "254712345678",
        )

    def test_payment_form_rejects_decimal_mpesa_amount(self):
        form = TenantPaymentForm(
            data={
                "lease": self.lease1.pk,
                "amount": "5000.50",
                "phone_number": "0712345678",
            },
            user=self.user1,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)
