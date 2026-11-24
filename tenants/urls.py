from django.urls import path
from tenants.views import tenant_dashboard

app_name = "tenants"

urlpatterns = [
    path( "dashboard/", tenant_dashboard, name="dashboard", ),
]