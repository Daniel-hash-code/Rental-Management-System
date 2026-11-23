
import base64
import hashlib
from decimal import Decimal

import requests

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from payments.models import Payment

from django.db import transaction
from django.utils import timezone


class DarajaAPIError(Exception):
    """Raised when communication with Daraja fails."""


def get_base_url():
    environment = settings.DARAJA_ENVIRONMENT.lower()

    if environment == "sandbox":
        return "https://sandbox.safaricom.co.ke"

    if environment == "production":
        return "https://api.safaricom.co.ke"

    raise DarajaAPIError("Invalid Daraja environment configuration.")


def validate_daraja_configuration():
    required_settings = {
        "DARAJA_CONSUMER_KEY": settings.DARAJA_CONSUMER_KEY,
        "DARAJA_CONSUMER_SECRET": settings.DARAJA_CONSUMER_SECRET,
        "DARAJA_SHORTCODE": settings.DARAJA_SHORTCODE,
        "DARAJA_PASSKEY": settings.DARAJA_PASSKEY,
        "DARAJA_CALLBACK_URL": settings.DARAJA_CALLBACK_URL,
    }

    missing = [
        name for name, value in required_settings.items()
        if not value
    ]

    if missing:
        raise DarajaAPIError(
            "Missing Daraja configuration: " + ", ".join(missing)
        )

    callback_url = settings.DARAJA_CALLBACK_URL

    if not callback_url.startswith("https://"):
        raise DarajaAPIError(
            "Daraja callback URL must use HTTPS."
        )


def get_access_token():
    """
    Obtain and cache a Daraja OAuth access token.
    """

    validate_daraja_configuration()

    consumer_key = settings.DARAJA_CONSUMER_KEY
    consumer_secret = settings.DARAJA_CONSUMER_SECRET

    # Use a different cache entry for each application key.
    cache_identifier = hashlib.sha256(
        consumer_key.encode()
    ).hexdigest()

    cache_key = f"daraja_access_token_{cache_identifier}"

    cached_token = cache.get(cache_key)

    if cached_token:
        return cached_token

    url = f"{get_base_url()}/oauth/v1/generate"

    try:
        response = requests.get(
            url,
            params={"grant_type": "client_credentials"},
            auth=(consumer_key, consumer_secret),
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        access_token = data.get("access_token")

        if not access_token:
            raise DarajaAPIError(
                "Daraja did not return an access token."
            )

        expires_in = int(data.get("expires_in", 3600))

        # Refresh the token before its actual expiry.
        cache.set(
            cache_key,
            access_token,
            timeout=max(expires_in - 60, 60),
        )

        return access_token

    except requests.RequestException as exc:
        raise DarajaAPIError(
            "Unable to communicate with Daraja OAuth service."
        ) from exc

    except (ValueError, TypeError) as exc:
        raise DarajaAPIError(
            "Invalid response from Daraja OAuth service."
        ) from exc


def generate_stk_password():
    """
    Generate the password required by the STK Push API.
    """

    timestamp = timezone.localtime().strftime("%Y%m%d%H%M%S")

    raw_password = (
        settings.DARAJA_SHORTCODE
        + settings.DARAJA_PASSKEY
        + timestamp
    )

    encoded_password = base64.b64encode(
        raw_password.encode("utf-8")
    ).decode("utf-8")

    return encoded_password, timestamp


def normalize_phone_number(phone_number):
    """
    Convert Kenyan phone numbers into 254XXXXXXXXX format.
    """

    phone = str(phone_number).strip()

    # Remove common formatting characters.
    phone = (
        phone.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if phone.startswith("+"):
        phone = phone[1:]

    if phone.startswith("0"):
        phone = "254" + phone[1:]

    if not (
        len(phone) == 12
        and phone.startswith("254")
        and phone[3] in "17"
        and phone[3:].isdigit()
    ):
        raise ValueError("Enter a valid Kenyan M-Pesa phone number.")

    return phone


def initiate_stk_push(payment):
    """
    Send an STK Push request for an existing Payment record.

    A successful API acknowledgement only changes the payment
    to PENDING. The callback will determine the final outcome.
    """

    validate_daraja_configuration()

    if payment.pk is None:
        raise ValueError(
            "Save the payment before initiating STK Push."
        )

    if payment.status != Payment.Status.INITIATED:
        raise ValueError(
            "Only initiated payments can receive an STK Push."
        )

    if payment.currency != "KES":
        raise ValueError("M-Pesa payments must use KES.")

    amount = Decimal(payment.amount)

    if amount <= 0 or amount != amount.to_integral_value():
        raise ValueError(
            "M-Pesa STK Push requires a positive whole-number amount."
        )

    phone_number = normalize_phone_number(payment.phone_number)

    access_token = get_access_token()

    password, timestamp = generate_stk_password()

    account_reference = (
        payment.account_reference or f"RF{payment.pk}"
    )[:12]

    transaction_description = (
        payment.transaction_description or "Rent payment"
    )[:13]

    shortcode = settings.DARAJA_SHORTCODE

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": settings.DARAJA_TRANSACTION_TYPE,
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": settings.DARAJA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_description,
    }

    url = (
        f"{get_base_url()}/mpesa/stkpush/v1/processrequest"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException as exc:
        # A timeout does not prove the transaction failed.
        # Leave it INITIATED for later reconciliation.
        raise DarajaAPIError(
            "Unable to obtain a reliable STK Push response."
        ) from exc

    except ValueError as exc:
        raise DarajaAPIError(
            "Daraja returned an invalid STK Push response."
        ) from exc

    response_code = str(data.get("ResponseCode", ""))

    if response_code == "0":
        payment.status = Payment.Status.PENDING
        payment.phone_number = phone_number
        payment.account_reference = account_reference
        payment.transaction_description = transaction_description
        payment.merchant_request_id = data.get(
            "MerchantRequestID", ""
        )
        payment.checkout_request_id = data.get(
            "CheckoutRequestID"
        )

        payment.result_description = data.get(
            "ResponseDescription", ""
        )

        payment.save(
            update_fields=[
                "status",
                "phone_number",
                "account_reference",
                "transaction_description",
                "merchant_request_id",
                "checkout_request_id",
                "result_description",
                "updated_at",
            ]
        )

        return data

    payment.status = Payment.Status.FAILED
    payment.result_code = response_code
    payment.result_description = data.get(
        "ResponseDescription",
        "Daraja rejected the STK Push request.",
    )

    payment.save(
        update_fields=[
            "status",
            "result_code",
            "result_description",
            "updated_at",
        ]
    )

    raise DarajaAPIError(
        "Daraja rejected the STK Push request."
    )


def get_callback_metadata(callback):
    """
    Convert Safaricom callback metadata into a dictionary.
    """

    metadata = callback.get("CallbackMetadata", {})
    items = metadata.get("Item", [])

    return {
        item.get("Name"): item.get("Value")
        for item in items
        if isinstance(item, dict) and item.get("Name")
    }


@transaction.atomic
def process_stk_callback(payload):
    """
    Process an STK Push callback.

    Returns True when the callback is matched to a payment.
    Returns False when no matching payment exists.

    Successful payments require matching:
    - CheckoutRequestID
    - Amount
    - Phone number
    - M-Pesa receipt number

    Repeated callbacks do not process a payment twice.
    """

    stk_callback = (
        payload.get("Body", {})
        .get("stkCallback", {})
    )

    checkout_request_id = stk_callback.get(
        "CheckoutRequestID"
    )

    if not checkout_request_id:
        return False

    payment = (
        Payment.objects
        .select_for_update()
        .filter(checkout_request_id=checkout_request_id)
        .first()
    )

    if payment is None:
        return False

    # Ignore duplicate callbacks for already-finalized payments.
    if payment.status in [
        Payment.Status.SUCCESSFUL,
        Payment.Status.FAILED,
        Payment.Status.CANCELLED,
    ]:
        return True

    result_code = stk_callback.get("ResultCode")

    if result_code is None:
        return False

    result_code = str(result_code)

    # Store the callback for auditing and reconciliation.
    payment.callback_payload = payload
    payment.result_code = result_code

    if result_code != "0":

        if result_code == "1032":
            payment.status = Payment.Status.CANCELLED
        else:
            payment.status = Payment.Status.FAILED

        payment.result_description = stk_callback.get(
            "ResultDesc",
            "M-Pesa transaction was unsuccessful.",
        )

        payment.save(
            update_fields=[
                "callback_payload",
                "result_code",
                "status",
                "result_description",
                "updated_at",
            ]
        )

        return True

    # Successful callbacks must contain complete metadata.
    metadata = get_callback_metadata(stk_callback)

    amount = metadata.get("Amount")
    receipt_number = metadata.get("MpesaReceiptNumber")
    phone_number = metadata.get("PhoneNumber")

    if (
        amount is None
        or not receipt_number
        or phone_number is None
    ):
        payment.result_description = (
            "Incomplete successful callback. "
            "Payment requires reconciliation."
        )

        payment.save(
            update_fields=[
                "callback_payload",
                "result_code",
                "result_description",
                "updated_at",
            ]
        )

        return True

    try:
        callback_amount = Decimal(str(amount))

        callback_phone = normalize_phone_number(
            str(phone_number)
        )

        expected_phone = normalize_phone_number(
            payment.phone_number
        )

    except (ValueError, TypeError):
        payment.result_description = (
            "Invalid callback amount or phone number. "
            "Payment requires reconciliation."
        )

        payment.save(
            update_fields=[
                "callback_payload",
                "result_code",
                "result_description",
                "updated_at",
            ]
        )

        return True

    # Verify the callback against the stored payment.
    if callback_amount != payment.amount:
        payment.result_description = (
            "Callback amount does not match payment amount."
        )

        payment.save(
            update_fields=[
                "callback_payload",
                "result_code",
                "result_description",
                "updated_at",
            ]
        )

        return True

    if callback_phone != expected_phone:
        payment.result_description = (
            "Callback phone number does not match payment."
        )

        payment.save(
            update_fields=[
                "callback_payload",
                "result_code",
                "result_description",
                "updated_at",
            ]
        )

        return True

    # Prevent one M-Pesa receipt from confirming two payments.
    receipt_already_used = (
        Payment.objects
        .filter(mpesa_receipt_number=receipt_number)
        .exclude(pk=payment.pk)
        .exists()
    )

    if receipt_already_used:
        payment.result_description = (
            "M-Pesa receipt is already associated with another "
            "payment. Reconciliation required."
        )

        payment.save(
            update_fields=[
                "callback_payload",
                "result_code",
                "result_description",
                "updated_at",
            ]
        )

        return True

    payment.status = Payment.Status.SUCCESSFUL
    payment.mpesa_receipt_number = receipt_number
    payment.result_description = stk_callback.get(
        "ResultDesc",
        "Payment completed successfully.",
    )

    payment.save(
        update_fields=[
            "callback_payload",
            "result_code",
            "status",
            "mpesa_receipt_number",
            "result_description",
            "updated_at",
        ]
    )

    return True
