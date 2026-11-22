from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import User
from .registration import AccountCreationError, create_account, registration_enabled
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


class CsrfView(APIView):
    """Pose le cookie CSRF ; le frontend le renvoie dans l'en-tête X-CSRFToken."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @method_decorator(ensure_csrf_cookie)
    @extend_schema(responses={204: OpenApiResponse(description="Cookie CSRF posé")})
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    """Ouvre une session (cookie HTTP-only). CSRF exigé, tentatives limitées."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=LoginSerializer,
        responses={200: UserSerializer, 400: OpenApiResponse(description="Identifiants invalides")},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Identifiants invalides."}, status=status.HTTP_400_BAD_REQUEST
            )
        login(request, user)
        return Response(UserSerializer(user).data)


class RegistrationStatusView(APIView):
    """La création de compte est-elle proposée ? (désactivée par défaut ; locale uniquement)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        responses={200: inline_serializer("RegistrationStatus", {"enabled": serializers.BooleanField(), "has_users": serializers.BooleanField()})}
    )
    def get(self, request):
        return Response({"enabled": registration_enabled(request), "has_users": User.objects.exists()})


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(APIView):
    """Crée un compte puis ouvre la session. CSRF exigé, tentatives limitées, locale uniquement."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: UserSerializer,
            400: OpenApiResponse(description="Champs invalides (identifiant pris, mot de passe trop faible…)"),
            403: OpenApiResponse(description="Création de compte désactivée ou requête non locale"),
        },
    )
    def post(self, request):
        if not registration_enabled(request):
            return Response({"detail": "La création de compte est désactivée."}, status=status.HTTP_403_FORBIDDEN)
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = create_account(
                username=data["username"], password=data["password"], email=data["email"], timezone=data["timezone"]
            )
        except AccountCreationError as exc:
            raise ValidationError(exc.errors) from exc
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LogoutView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: OpenApiResponse(description="Déconnecté")})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    """Profil de l'utilisateur connecté (seul le fuseau est modifiable)."""

    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user
