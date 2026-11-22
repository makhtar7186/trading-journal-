from django.urls import path

from .views import CsrfView, LoginView, LogoutView, MeView, RegisterView, RegistrationStatusView

urlpatterns = [
    path("csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("registration/", RegistrationStatusView.as_view(), name="auth-registration"),
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
]
