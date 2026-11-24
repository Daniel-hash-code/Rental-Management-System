import hashlib
import secrets

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.crypto import get_random_string

from accounts.models import (
    EmailVerification,
    LandlordAccount,
    Membership,
    TenantInvitation,
)
from tenants.models import Tenant


User = get_user_model()

class RegistrationError(Exception):
    pass
class ExistingAccountError(RegistrationError):
    pass

def generate_token():
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    return raw_token, token_hash


def hash_token(raw_token):
    return hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()


def generate_username(email):
    base = slugify(email.split("@")[0])[:120] or "user"
    username = base
    counter = 1

    while User.objects.filter(username=username).exists():
        counter += 1
        username = f"{base[:135]}-{counter}"

    return username


def generate_unique_slug(name):
    base = slugify(name)[:150] or "landlord"
    slug = base
    counter = 1

    while LandlordAccount.objects.filter(slug=slug).exists():
        counter += 1
        slug = f"{base[:160]}-{counter}"

    return slug


@transaction.atomic
def register_landlord(cleaned_data):
    raw_token, token_hash = generate_token()

    user = User.objects.create_user(
        username=generate_username(cleaned_data["email"]),
        email=cleaned_data["email"],
        first_name=cleaned_data["first_name"],
        last_name=cleaned_data["last_name"],
        phone_number=cleaned_data["phone_number"],
        role=User.Role.LANDLORD,
        is_active=False,
    )

    user.set_password(cleaned_data["password"])
    user.save(update_fields=["password"])

    landlord = LandlordAccount.objects.create(
        name=cleaned_data["landlord_name"],
        slug=generate_unique_slug(cleaned_data["landlord_name"]),
        created_by=user,
    )

    Membership.objects.create(
        user=user,
        landlord=landlord,
        role=Membership.Role.OWNER,
        status=Membership.Status.ACTIVE,
    )

    verification = EmailVerification.objects.create(
        user=user,
        token_hash=token_hash,
        expires_at=(
            timezone.now()
            + timedelta(
                seconds=settings.EMAIL_VERIFICATION_TIMEOUT
            )
        ),
    )

    return user, landlord, verification, raw_token


def send_verification_email(user, raw_token):
    verification_url = (
        f"{settings.SITE_URL}"
        f"/accounts/verify-email/{raw_token}/"
    )

    send_mail(
        subject="Verify your RentFlow account",
        message=(
            f"Hello {user.first_name},\n\n"
            "Thank you for registering with RentFlow.\n"
            "Verify your email using this link:\n\n"
            f"{verification_url}\n\n"
            "This link expires in 24 hours.\n"
            "If you did not create this account, ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


@transaction.atomic
def create_tenant_invitation(tenant, invited_by):
    if not tenant.email:
        raise ValueError(
            "This tenant does not have an email address."
        )

    if tenant.user_id is not None:
        raise ValueError(
            "This tenant already has a RentFlow login account."
        )

    if User.objects.filter(email__iexact=tenant.email).exists():
        raise ValueError(
            "An account already uses this email address. "
            "Use the account-linking process instead."
        )

    # Revoke any previous outstanding invitations.
    TenantInvitation.objects.filter(
        tenant=tenant,
        status=TenantInvitation.Status.PENDING,
    ).update(status=TenantInvitation.Status.REVOKED)

    raw_token, token_hash = generate_token()

    invitation = TenantInvitation.objects.create(
        tenant=tenant,
        invited_by=invited_by,
        email=tenant.email.strip().lower(),
        token_hash=token_hash,
        expires_at=(
            timezone.now()
            + timedelta(
                seconds=settings.TENANT_INVITATION_TIMEOUT
            )
        ),
    )

    return invitation, raw_token


def send_tenant_invitation_email(invitation, raw_token):
    invitation_url = (
        f"{settings.SITE_URL}"
        f"/accounts/accept-invitation/{raw_token}/"
    )

    tenant = invitation.tenant

    send_mail(
        subject="Your RentFlow tenant portal invitation",
        message=(
            f"Hello {tenant.first_name},\n\n"
            "Your landlord has invited you to join RentFlow.\n"
            "Use this secure link to create your tenant portal account:\n\n"
            f"{invitation_url}\n\n"
            "This invitation expires in 48 hours.\n"
            "If you were not expecting this invitation, ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=False,
    )
