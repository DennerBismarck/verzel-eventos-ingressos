from django.urls import path

from .views import LoginView, LogoutView, MeView, RefreshView, RegisterView

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("login", LoginView.as_view(), name="login"),
    # Troca um refresh válido por um novo access, sem pedir a senha de novo.
    # Com ROTATE_REFRESH_TOKENS, devolve também um refresh novo e invalida o
    # anterior.
    path("refresh", RefreshView.as_view(), name="token-refresh"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("me", MeView.as_view(), name="me"),
]
