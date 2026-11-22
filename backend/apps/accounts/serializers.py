from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


def _check_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise serializers.ValidationError("Fuseau horaire inconnu.") from None
    return value


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    timezone = serializers.CharField(required=False, default="UTC", max_length=64)

    def validate_username(self, value):
        value = value.strip()
        try:
            UnicodeUsernameValidator()(value)
        except DjangoValidationError:
            raise serializers.ValidationError(
                "Lettres, chiffres et @ . + - _ uniquement (pas d'espaces)."
            ) from None
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Cet identifiant est déjà utilisé.")
        return value

    def validate_timezone(self, value):
        return _check_timezone(value)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Les mots de passe ne correspondent pas."})
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "timezone"]
        read_only_fields = ["id", "username", "email"]

    def validate_timezone(self, value):
        return _check_timezone(value)
