"""
URL configuration for rentflow project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from accounts.views import dashboard, landlord_dashboard
from django.views.generic import RedirectView
from rentflow.views import home
from accounts import registration_views

urlpatterns = [
    path("", home, name="home"),
    path('admin/', admin.site.urls),
    path('api/payments/', include('payments.urls')),
    path("accounts/login/", auth_views.LoginView.as_view(),
        name="login",
    ),
    path(
        "accounts/logout/", auth_views.LogoutView.as_view(),
        name="logout",
    ),

     # Main dashboards
     path("dashboard/", dashboard, name="dashboard"),
     # Landlord dashboard
     path("dashboard/landlord/<slug:slug>/", landlord_dashboard,
         name="landlord_dashboard",
     ),

    # Tenant portal
    path("tenant/", include("tenants.urls")),

    # Public landlord registration
    path(
        "accounts/register/",
        registration_views.landlord_register,
        name="landlord_register",
    ),

    # Email verification
    path(
        "accounts/verify-email/<str:token>/",
        registration_views.verify_email,
        name="verify_email",
    ),

    path(
        "accounts/resend-verification/",
        registration_views.resend_verification,
        name="resend_verification",
    ),

    # Tenant invitation
    path(
        "dashboard/landlord/<slug:slug>/invite-tenant/",
        registration_views.invite_tenant,
        name="invite_tenant",
    ),

    path(
        "accounts/accept-invitation/<str:token>/",
        registration_views.accept_tenant_invitation,
        name="accept_tenant_invitation",
    ),
]
