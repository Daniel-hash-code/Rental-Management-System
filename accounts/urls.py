from django.urls import path
from accounts.views import ( dashboard, landlord_dashboard,)

app_name = "accounts"

urlpatterns = [
    path( "", dashboard, name="dashboard", ),
    path( "landlord/<slug:slug>/", landlord_dashboard, name="landlord_dashboard", ),
]