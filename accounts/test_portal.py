from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import LandlordAccount, Membership


User = get_user_model()


class AccountPortalTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="landlord1",
            email="landlord1@example.com",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="landlord2",
            email="landlord2@example.com",
            password="TestPassword123!",
        )

        self.landlord = LandlordAccount.objects.create(
            name="Green Homes",
            slug="green-homes",
            created_by=self.user,
        )

        self.other_landlord = LandlordAccount.objects.create(
            name="Blue Homes",
            slug="blue-homes",
            created_by=self.other_user,
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(
            reverse("dashboard")
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_authenticated_user_can_access_dashboard(self):
        self.client.login(
            username="landlord1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("dashboard")
        )

        self.assertEqual(response.status_code, 200)

    def test_active_member_can_access_landlord_dashboard(self):
        Membership.objects.create(
            user=self.user,
            landlord=self.landlord,
            role=Membership.Role.OWNER,
            status=Membership.Status.ACTIVE,
        )

        self.client.login(
            username="landlord1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse(
                "landlord_dashboard",
                kwargs={"slug": "green-homes"},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_user_without_membership_cannot_access_landlord_dashboard(self):
        self.client.login(
            username="landlord2",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse(
                "landlord_dashboard",
                kwargs={"slug": "green-homes"},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_suspended_member_cannot_access_landlord_dashboard(self):
        Membership.objects.create(
            user=self.user,
            landlord=self.landlord,
            role=Membership.Role.OWNER,
            status=Membership.Status.SUSPENDED,
        )

        self.client.login(
            username="landlord1",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse(
                "landlord_dashboard",
                kwargs={"slug": "green-homes"},
            )
        )

        self.assertEqual(response.status_code, 404)
