
from django.urls import path

from payments.views import (stk_callback, initiate_payment, payment_history, payment_detail, payment_receipt,)


app_name = "payments"

urlpatterns = [
    path(
        "callback/", stk_callback, name="stk_callback",
    ),
    path(
        "initiate/", initiate_payment, name="initiate",
    ),
    path(
        "history/", payment_history, name="history",
    ),
    path(
        "<int:pk>/", payment_detail, name="detail",
    ),
    path(
        "<int:pk>/receipt/", payment_receipt, name="receipt",
    ),
]
