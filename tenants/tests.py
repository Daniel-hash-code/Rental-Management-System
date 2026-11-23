
from django.test import TestCase

from accounts.models import User, LandlordAccount
from tenants.models import Tenant


class TenantModelTests(TestCase):

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

    def test_create_tenant(self):
        tenant = Tenant.objects.create(
            landlord=self.landlord,
            first_name="John",
            last_name="Kamau",
            email="john@example.com",
            phone_number="0712345678"
        )

        self.assertEqual(
            tenant.first_name,
            "John"
        )

        self.assertEqual(
            tenant.landlord,
            self.landlord
        )

    def test_tenant_default_status(self):
        tenant = Tenant.objects.create(
            landlord=self.landlord,
            first_name="Mary",
            last_name="Wanjiku",
            phone_number="0723456789"
        )

        self.assertEqual(
            tenant.status,
            Tenant.Status.ACTIVE
        )
