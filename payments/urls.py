
from django.urls import path

from payments.views import stk_callback


app_name = "payments"

urlpatterns = [
    path(
        "callback/", stk_callback, name="stk_callback",
    ),
]
