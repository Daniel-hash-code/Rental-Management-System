from decimal import Decimal

from django import forms
from django.db.models import Sum

from billing.models import RentCharge
from leases.models import Lease
from payments.services.daraja import normalize_phone_number


class TenantPaymentForm(forms.Form):

    lease = forms.ModelChoiceField(
        queryset=Lease.objects.none(),
        label="Select rental unit",
        widget=forms.Select(
            attrs={"class": "form-select"}
        ),
    )

    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("1.00"),
        label="Amount (KES)",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter amount",
                "step": "1",
                "min": "1",
            }
        ),
    )

    phone_number = forms.CharField(
        max_length=20,
        label="M-Pesa phone number",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "0712345678",
            }
        ),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)

        self.user = user

        self.fields["lease"].queryset = (
            Lease.objects
            .filter(
                tenant__user=user,
                tenant__status="active",
                status=Lease.Status.ACTIVE,
            )
            .select_related(
                "tenant",
                "unit",
                "unit__property",
            )
        )

    def clean_phone_number(self):
        phone_number = self.cleaned_data["phone_number"]

        try:
            return normalize_phone_number(phone_number)
        except ValueError as exc:
            raise forms.ValidationError(str(exc))

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if amount <= 0:
            raise forms.ValidationError(
                "Enter an amount greater than zero."
            )

        if amount != amount.to_integral_value():
            raise forms.ValidationError(
                "M-Pesa STK Push accepts whole-number amounts."
            )

        return amount

    def clean(self):
        cleaned_data = super().clean()

        lease = cleaned_data.get("lease")
        amount = cleaned_data.get("amount")

        if not lease or amount is None:
            return cleaned_data

        # Recheck ownership rather than trusting the form.
        if not Lease.objects.filter(
            pk=lease.pk,
            tenant__user=self.user,
            status=Lease.Status.ACTIVE,
        ).exists():
            raise forms.ValidationError(
                "You do not have permission to pay this lease."
            )

        # Calculate the outstanding balance for this lease.
        totals = (
            RentCharge.objects
            .filter(lease=lease)
            .exclude(status=RentCharge.Status.VOID)
            .aggregate(
                total_due=Sum("amount_due"),
                total_paid=Sum("amount_paid"),
            )
        )

        total_due = totals["total_due"] or Decimal("0.00")
        total_paid = totals["total_paid"] or Decimal("0.00")

        outstanding = total_due - total_paid

        if outstanding <= 0:
            raise forms.ValidationError(
                "This lease has no outstanding rent charges."
            )

        if amount > outstanding:
            raise forms.ValidationError(
                f"Your outstanding balance is KES {outstanding:,.2f}. "
                "The payment cannot exceed this amount."
            )

        return cleaned_data

class StyledFormMixin:

    def apply_form_styles(self):
        for field in self.fields.values():
            field.widget.attrs.update({
                "class": "form-control",
            })    