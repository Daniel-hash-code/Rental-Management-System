from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from tenants.models import Tenant


User = get_user_model()


class LandlordRegistrationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                "class": "form-control", "placeholder": field.label,
            })
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)

    email = forms.EmailField()

    phone_number = forms.CharField(max_length=20)

    business_name = forms.CharField(max_length=150)

    password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
    )

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
            password_validation.validate_password(password)

        return cleaned_data


class TenantInvitationForm(forms.Form):
    
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
                ).order_by("first_name", "last_name")
            )
        self.fields["tenant"].widget.attrs["class"] = "form-select"    


class TenantInvitationAcceptanceForm(forms.Form):

    password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        strip=False,
    )

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
            password_validation.validate_password(password)

        return cleaned_data
