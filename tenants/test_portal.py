
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import LandlordAccount
from properties.models import Property, RentalUnit
from tenants.models import Tenant
from leases.models import Lease
from billing.models import RentCharge
from payments.models import Payment

User = get_user_model()


class TenantPortalTests(TestCase):

    def setUp(self):
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

        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
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
            email="tenant1@example.com",
            phone_number="0712345678",
        )

        self.tenant2 = Tenant.objects.create(
            landlord=self.landlord,
            user=self.user2,
            first_name="Mary",
            last_name="Wanjiku",
            email="tenant2@example.com",
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

    def test_tenant_dashboard_requires_login(self):
        response = self.client.get(
            reverse("tenants:dashboard")
        )

        self.assertEqual(response.status_code, 302)

    def test_tenant_can_access_own_dashboard(self):
        self.client.login(
            username="tenant1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("tenants:dashboard")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John")

    def test_tenant_dashboard_does_not_show_another_tenant(self):
        self.client.login(
            username="tenant1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("tenants:dashboard")
        )

        self.assertContains(response, "John")
        self.assertNotContains(response, "Mary")

    def test_tenant_only_sees_own_outstanding_charges(self):
        self.client.login(
            username="tenant1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("tenants:dashboard")
        )

        charges = response.context["outstanding_charges"]

        self.assertEqual(charges.count(), 1)
        self.assertEqual(
            charges.first().pk,
            self.charge1.pk,
        )

    def test_tenant_only_sees_own_active_leases(self):
        self.client.login(
            username="tenant1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("tenants:dashboard")
        )

        leases = response.context["active_leases"]

        self.assertEqual(leases.count(), 1)
        self.assertEqual(
            leases.first().pk,
            self.lease1.pk,
        )
