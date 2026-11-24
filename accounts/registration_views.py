from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta
from accounts.forms import (
    LandlordRegistrationForm,
    TenantInvitationForm,
    TenantInvitationAcceptanceForm,
    ResendVerificationForm,
)
from accounts.models import (
    EmailVerification,
    Membership,
    TenantInvitation,
)
from accounts.services.registration import (
    create_tenant_invitation,
    generate_token,
    generate_username,
    hash_token,
    register_landlord,
    send_tenant_invitation_email,
    send_verification_email,
)
from tenants.models import Tenant


User = get_user_model()


def landlord_register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = LandlordRegistrationForm(request.POST)

        if form.is_valid():
            try:
                user, landlord, verification, raw_token = (
                    register_landlord(form.cleaned_data)
                )

                send_verification_email(user, raw_token)

                return render(
                    request,
                    "registration/verification_sent.html",
                    {"email": user.email},
                )

            except Exception:
                # Log the actual exception in production.
                form.add_error(
                    None,
                    "We could not complete registration. "
                    "Please try again.",
                )
    else:
        form = LandlordRegistrationForm()

    return render(
        request,
        "registration/landlord_register.html",
        {"form": form},
    )


def verify_email(request, token):
    token_hash = hash_token(token)

    verification = get_object_or_404(
        EmailVerification.objects.select_related("user"),
        token_hash=token_hash,
    )

    if not verification.is_valid():
        return render(
            request,
            "registration/verification_invalid.html",
        )

    if request.method == "POST":
        with transaction.atomic():
            verification = (
                EmailVerification.objects
                .select_for_update()
                .select_related("user")
                .get(pk=verification.pk)
            )

            if not verification.is_valid():
                return render(
                    request,
                    "registration/verification_invalid.html",
                )

            verification.verified_at = timezone.now()
            verification.save(update_fields=["verified_at"])

            user = verification.user
            user.is_active = True
            user.save(update_fields=["is_active"])

        return render(
            request,
            "registration/verification_success.html",
        )

    return render(
        request,
        "registration/verify_email.html",
        {"verification": verification},
    )


@require_POST
def resend_verification(request):
    if request.method == "POST":
        form = ResendVerificationForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()

            user = User.objects.filter(
                email__iexact=email,
                role=User.Role.LANDLORD,
                is_active=False,
            ).first()

            if user:
                raw_token, token_hash = generate_token()

                verification = EmailVerification.objects.filter(
                    user=user,
                ).first()

                if verification:
                    verification.token_hash = token_hash
                    verification.expires_at = (
                        timezone.now()
                        + timedelta(
                            seconds=settings.EMAIL_VERIFICATION_TIMEOUT
                        )
                    )
                    verification.verified_at = None
                    verification.save()

                else:
                    EmailVerification.objects.create(
                        user=user,
                        token_hash=token_hash,
                        expires_at=(
                            timezone.now()
                            + timedelta(
                                seconds=settings.EMAIL_VERIFICATION_TIMEOUT
                            )
                        ),
                    )

                send_verification_email(user, raw_token)

            return render(
                request,
                "registration/resend_verification_sent.html",
            )

    else:
        form = ResendVerificationForm()

    return render(
        request,
        "registration/resend_verification.html",
        {"form": form},
    )


@login_required
def invite_tenant(request, slug):
    membership = get_object_or_404(
        Membership.objects.select_related("landlord"),
        user=request.user,
        landlord__slug=slug,
        status=Membership.Status.ACTIVE,
        role__in=[
            Membership.Role.OWNER,
            Membership.Role.ADMIN,
            Membership.Role.PROPERTY_MANAGER,
        ],
    )

    landlord = membership.landlord

    if request.method == "POST":
        form = TenantInvitationForm(
            request.POST,
            landlord=landlord,
        )

        if form.is_valid():
            tenant = form.cleaned_data["tenant"]

            try:
                invitation, raw_token = create_tenant_invitation(
                    tenant=tenant,
                    invited_by=request.user,
                )

                send_tenant_invitation_email(
                    invitation,
                    raw_token,
                )

                messages.success(
                    request,
                    f"An invitation was sent to {invitation.email}.",
                )

                return redirect(
                    "landlord_dashboard",
                    slug=landlord.slug,
                )

            except ValueError as error:
                form.add_error("tenant", str(error))
            except Exception:
                form.add_error(
                    None,
                    "The invitation could not be sent. Please try again.",
                )

    else:
        form = TenantInvitationForm(landlord=landlord)

    return render(
        request,
        "registration/invite_tenant.html",
        {
            "form": form,
            "landlord": landlord,
        },
    )


def accept_tenant_invitation(request, token):
    token_hash = hash_token(token)

    invitation = get_object_or_404(
        TenantInvitation.objects.select_related("tenant"),
        token_hash=token_hash,
    )

    if not invitation.is_valid():
        if (
            invitation.status == TenantInvitation.Status.PENDING
            and invitation.expires_at <= timezone.now()
        ):
            invitation.status = TenantInvitation.Status.EXPIRED
            invitation.save(update_fields=["status"])

        return render(
            request,
            "registration/invitation_invalid.html",
        )

    # An account with this email must not be silently replaced.
    if User.objects.filter(
        email__iexact=invitation.email
    ).exists():
        return render(
            request,
            "registration/invitation_existing_account.html",
            {"email": invitation.email},
        )

    if request.method == "POST":
        form = TenantInvitationAcceptanceForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                invitation = (
                    TenantInvitation.objects
                    .select_for_update()
                    .select_related("tenant")
                    .get(pk=invitation.pk)
                )

                if not invitation.is_valid():
                    return render(
                        request,
                        "registration/invitation_invalid.html",
                    )

                if User.objects.filter(
                    email__iexact=invitation.email
                ).exists():
                    return render(
                        request,
                        "registration/invitation_existing_account.html",
                        {"email": invitation.email},
                    )

                tenant = invitation.tenant

                if tenant.user_id is not None:
                    return render(
                        request,
                        "registration/invitation_invalid.html",
                    )

                user = User.objects.create_user(
                    username=generate_username(invitation.email),
                    email=invitation.email,
                    first_name=tenant.first_name,
                    last_name=tenant.last_name,
                    phone_number=tenant.phone_number,
                    role=User.Role.TENANT,
                    password=form.cleaned_data["password"],
                    is_active=True,
                )

                tenant.user = user
                tenant.save(update_fields=["user", "updated_at"])

                invitation.status = TenantInvitation.Status.ACCEPTED
                invitation.accepted_at = timezone.now()
                invitation.save(
                    update_fields=["status", "accepted_at"]
                )

            messages.success(
                request,
                "Your tenant account has been created. You can now sign in.",
            )

            return redirect("login")

    else:
        form = TenantInvitationAcceptanceForm()

    return render(
        request,
        "registration/accept_invitation.html",
        {
            "form": form,
            "invitation": invitation,
        },
    )
