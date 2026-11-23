from django.urls import reverse
from unittest.mock import patch

from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.core.cache import cache

from accounts.models import LandlordAccount
from tenants.models import Tenant
from payments.models import Payment
from payments.services.daraja import (
    DarajaAPIError,
    generate_stk_password,
    get_access_token,
    initiate_stk_push,
    normalize_phone_number,
    process_stk_callback,
)


User = get_user_model()


@override_settings(
    DARAJA_ENVIRONMENT="sandbox",
    DARAJA_CONSUMER_KEY="test-consumer-key",
    DARAJA_CONSUMER_SECRET="test-consumer-secret",
    DARAJA_SHORTCODE="174379",
    DARAJA_PASSKEY="test-passkey",
    DARAJA_CALLBACK_URL="https://example.com/api/payments/callback/",
    DARAJA_TRANSACTION_TYPE="CustomerPayBillOnline",
)
class DarajaServiceTests(TestCase):

    def setUp(self):
        cache.clear()

        self.user = User.objects.create_user(
            username="testowner",
            email="owner@example.com",
            password="test-password",
        )

        self.landlord = LandlordAccount.objects.create(
            name="Test Landlord",
            slug="test-landlord",
            created_by=self.user,
        )

        self.tenant = Tenant.objects.create(
            landlord=self.landlord,
            first_name="John",
            last_name="Doe",
            phone_number="0712345678",
            email="john@example.com",
        )

        self.payment = Payment.objects.create(
            landlord=self.landlord,
            tenant=self.tenant,
            amount=Decimal("12000.00"),
            currency="KES",
            phone_number="0712345678",
        )

    def test_phone_number_normalization(self):
        self.assertEqual(
            normalize_phone_number("0712345678"),
            "254712345678",
        )

        self.assertEqual(
            normalize_phone_number("+254712345678"),
            "254712345678",
        )

        self.assertEqual(
            normalize_phone_number("254712345678"),
            "254712345678",
        )

    def test_invalid_phone_number(self):
        with self.assertRaises(ValueError):
            normalize_phone_number("12345")

    def test_stk_password_generation(self):
        password, timestamp = generate_stk_password()

        self.assertTrue(password)
        self.assertEqual(len(timestamp), 14)

    @patch("payments.services.daraja.requests.get")
    def test_get_access_token(self, mock_get):

        response = Mock()

        response.json.return_value = {
            "access_token": "test-access-token",
            "expires_in": "3599",
        }

        response.raise_for_status.return_value = None

        mock_get.return_value = response

        token = get_access_token()

        self.assertEqual(token, "test-access-token")
        mock_get.assert_called_once()

        # A second call should use the cached token.
        second_token = get_access_token()

        self.assertEqual(second_token, "test-access-token")
        mock_get.assert_called_once()

    @patch("payments.services.daraja.requests.post")
    @patch("payments.services.daraja.get_access_token")
    def test_successful_stk_initiation(
        self,
        mock_token,
        mock_post,
    ):

        mock_token.return_value = "test-access-token"

        response = Mock()

        response.json.return_value = {
            "ResponseCode": "0",
            "MerchantRequestID": "merchant-123",
            "CheckoutRequestID": "checkout-123",
            "ResponseDescription": "Success. Request accepted.",
        }

        response.raise_for_status.return_value = None

        mock_post.return_value = response

        result = initiate_stk_push(self.payment)

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            Payment.Status.PENDING,
        )

        self.assertEqual(
            self.payment.checkout_request_id,
            "checkout-123",
        )

        self.assertEqual(
            self.payment.merchant_request_id,
            "merchant-123",
        )

        self.assertEqual(
            result["ResponseCode"],
            "0",
        )

        request_payload = mock_post.call_args.kwargs["json"]

        self.assertEqual(
            request_payload["PhoneNumber"],
            "254712345678",
        )

        self.assertEqual(
            request_payload["Amount"],
            12000,
        )

        self.assertEqual(
            request_payload["TransactionType"],
            "CustomerPayBillOnline",
        )

    @patch("payments.services.daraja.requests.post")
    @patch("payments.services.daraja.get_access_token")
    def test_rejected_stk_request(
        self,
        mock_token,
        mock_post,
    ):

        mock_token.return_value = "test-access-token"

        response = Mock()

        response.json.return_value = {
            "ResponseCode": "1",
            "ResponseDescription": "Request rejected",
        }

        response.raise_for_status.return_value = None

        mock_post.return_value = response

        with self.assertRaises(DarajaAPIError):
            initiate_stk_push(self.payment)

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            Payment.Status.FAILED,
        )

    def test_successful_callback(self):

        self.payment.status = Payment.Status.PENDING
        self.payment.checkout_request_id = "checkout-123"
        self.payment.save()

        callback = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "checkout-123",
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 12000},
                            {
                                "Name": "MpesaReceiptNumber",
                                "Value": "QAB1234567",
                            },
                            {
                                "Name": "PhoneNumber",
                                "Value": 254712345678,
                            },
                        ]
                    },
                }
            }
        }

        result = process_stk_callback(callback)

        self.payment.refresh_from_db()

        self.assertTrue(result)

        self.assertEqual(
            self.payment.status,
            Payment.Status.SUCCESSFUL,
        )

        self.assertEqual(
            self.payment.mpesa_receipt_number,
            "QAB1234567",
        )

    def test_duplicate_callback_is_idempotent(self):

        self.payment.status = Payment.Status.PENDING
        self.payment.checkout_request_id = "checkout-123"
        self.payment.save()

        callback = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "checkout-123",
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 12000},
                            {
                                "Name": "MpesaReceiptNumber",
                                "Value": "QAB1234567",
                            },
                            {
                                "Name": "PhoneNumber",
                                "Value": 254712345678,
                            },
                        ]
                    },
                }
            }
        }

        process_stk_callback(callback)
        process_stk_callback(callback)

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            Payment.Status.SUCCESSFUL,
        )

        self.assertEqual(
            self.payment.mpesa_receipt_number,
            "QAB1234567",
        )

    def test_callback_with_wrong_amount_does_not_confirm_payment(self):

        self.payment.status = Payment.Status.PENDING
        self.payment.checkout_request_id = "checkout-123"
        self.payment.save()

        callback = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "checkout-123",
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 5000},
                            {
                                "Name": "MpesaReceiptNumber",
                                "Value": "QAB1234567",
                            },
                            {
                                "Name": "PhoneNumber",
                                "Value": 254712345678,
                            },
                        ]
                    },
                }
            }
        }

        process_stk_callback(callback)

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            Payment.Status.PENDING,
        )

        self.assertIsNone(
            self.payment.mpesa_receipt_number
        )

    def test_cancelled_callback(self):

        self.payment.status = Payment.Status.PENDING
        self.payment.checkout_request_id = "checkout-123"
        self.payment.save()

        callback = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "checkout-123",
                    "ResultCode": 1032,
                    "ResultDesc": "Request cancelled by user.",
                }
            }
        }

        process_stk_callback(callback)

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            Payment.Status.CANCELLED,
        )

    def test_callback_for_unknown_payment(self):

        callback = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "unknown-checkout",
                    "ResultCode": 0,
                }
            }
        }

        result = process_stk_callback(callback)

        self.assertFalse(result)


@override_settings(
    DARAJA_ENVIRONMENT="sandbox",
    DARAJA_CONSUMER_KEY="",
    DARAJA_CONSUMER_SECRET="",
    DARAJA_SHORTCODE="174379",
    DARAJA_PASSKEY="test-passkey",
    DARAJA_CALLBACK_URL="https://example.com/callback/",
)
class DarajaConfigurationTests(TestCase):

    def test_missing_credentials_are_rejected(self):

        with self.assertRaises(DarajaAPIError):
            get_access_token()


class DarajaCallbackViewTests(TestCase):

    def test_invalid_json_is_rejected(self):
        response = self.client.post(
            reverse("payments:stk_callback"),
            data="{invalid-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @patch("payments.views.process_stk_callback")
    def test_valid_callback_is_acknowledged(self, mock_process):

        mock_process.return_value = True

        payload = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "checkout-123",
                    "ResultCode": 0,
                }
            }
        }

        response = self.client.post(
            reverse("payments:stk_callback"),
            data=payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.json()["ResultCode"],
            0,
        )

        mock_process.assert_called_once()
