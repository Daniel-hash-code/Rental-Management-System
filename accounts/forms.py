from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from tenants.models import Tenant


User = get_user_model()

class StyledFormMixin:
    """Apply consistent Bootstrap styling to form fields."""

    def apply_bootstrap_classes(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                existing = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{existing} form-control".strip()
class LandlordRegistrationForm(StyledFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)

    email = forms.EmailField()

    phone_number = forms.CharField(max_length=20)

    landlord_name = forms.CharField(max_length=150, label="Business or landlord name")

    password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False, label="Confirm password",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap_classes()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "An account with this email already exists."
            )

        return email

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirmation = cleaned_data.get("confirm_password")

        if password and confirmation and password != confirmation:
            self.add_error(
                "confirm_password",
                "The passwords do not match.",
            )

        if password:
            try:
                password_validation.validate_password(password)
            except forms.ValidationError as error:
                self.add_error("password", error)

        return cleaned_data

class TenantInvitationForm(StyledFormMixin, forms.Form):
    
    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.none(),
        empty_label="Select a tenant",
    )

    def __init__(self, *args, landlord=None, **kwargs):
        super().__init__(*args, **kwargs)

        if landlord is not None:
            self.fields["tenant"].queryset = (
                Tenant.objects.filter(
                    landlord=landlord,
                    status=Tenant.Status.ACTIVE,
                    user__isnull=True,
                )
                .exclude(email="")
                .order_by("first_name", "last_name")
            )
        self.apply_bootstrap_classes()
    def clean_tenant(self):
        tenant = self.cleaned_data["tenant"]

        if not tenant.email:
            raise forms.ValidationError(
                "This tenant does not have an email address."
            )

        if tenant.user_id:
            raise forms.ValidationError(
                "This tenant already has a login account."
            )

        return tenant


class TenantInvitationAcceptanceForm(StyledFormMixin, forms.Form):

    password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
        label="Create password",
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
        label="Confirm password",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap_classes()

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirmation = cleaned_data.get("confirm_password")

        if password and confirmation and password != confirmation:
            self.add_error(
                "confirm_password",
                "The passwords do not match.",
            )

        if password:
            try:
                password_validation.validate_password(password)
            except forms.ValidationError as error:
                self.add_error("password", error)

        return cleaned_data


class ResendVerificationForm(StyledFormMixin, forms.Form):
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap_classes()
