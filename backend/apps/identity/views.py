from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
import logging
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .authentication import revoke_user_tokens
from .client_ip import client_ip as _client_ip

User = get_user_model()
logger = logging.getLogger("agenda.security")


def _masked_email(value):
    email = str(value or "")
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}"


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"

class PasswordChangeRateThrottle(UserRateThrottle):
    scope = "password_change"

class PasswordResetRateThrottle(AnonRateThrottle):
    scope = "password_reset"

class PasswordResetConfirmRateThrottle(AnonRateThrottle):
    scope = "password_reset_confirm"

class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        request = self.context.get("request")
        logger.info(
            "login_succeeded user_id=%s email=%s ip=%s",
            self.user.pk, _masked_email(self.user.email), _client_ip(request),
        )
        data["user"] = {
            "id": str(self.user.id),
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "is_saas_admin": self.user.is_saas_admin,
            "must_change_password": self.user.must_change_password,
        }
        return data


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [LoginRateThrottle]

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

class LogoutView(APIView):
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = RefreshToken(serializer.validated_data["refresh"])
        if str(token.get("user_id")) != str(request.user.pk):
            return Response({"detail": "Token inválido."}, status=status.HTTP_400_BAD_REQUEST)
        token.blacklist()
        return Response(status=status.HTTP_204_NO_CONTENT)

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetRateThrottle]
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data["email"], is_active=True).first()
        if user:
            token = signing.dumps({"uid": str(user.pk), "epoch": int(user.jwt_valid_after.timestamp()) if user.jwt_valid_after else 0}, salt="identity.password-reset")
            reset_url = request.build_absolute_uri(reverse("password-reset-confirm"))
            send_mail("Restablece tu contraseña", f"Usa este token en {reset_url}: {token}\nEl enlace vence en una hora.", None, [user.email])
        return Response({"detail": "Si la cuenta existe, enviaremos instrucciones para restablecer la contraseña."}, status=status.HTTP_200_OK)

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=12, max_length=128)
    def validate(self, attrs):
        try:
            payload = signing.loads(attrs["token"], salt="identity.password-reset", max_age=settings.PASSWORD_RESET_TIMEOUT)
            user = User.objects.get(pk=payload["uid"], is_active=True)
        except (signing.BadSignature, signing.SignatureExpired, User.DoesNotExist, KeyError, ValueError):
            logger.warning(
                "password_reset_invalid_token ip=%s",
                _client_ip(self.context.get("request")),
            )
            raise serializers.ValidationError({"token": "El token no es válido o venció."})
        epoch = int(user.jwt_valid_after.timestamp()) if user.jwt_valid_after else 0
        if payload.get("epoch") != epoch:
            raise serializers.ValidationError({"token": "El token ya fue utilizado o invalidado."})
        validate_password(attrs["new_password"], user=user)
        attrs["_user"] = user
        return attrs

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PasswordResetConfirmRateThrottle]
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["_user"]
        user.set_password(serializer.validated_data["new_password"])
        user.jwt_valid_after = timezone.now()
        user.save(update_fields=["password", "jwt_valid_after"])
        revoke_user_tokens(user)
        return Response({"detail": "La contraseña fue actualizada. Inicia sesión nuevamente."})


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=12, max_length=128)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError(
                {"current_password": "La contraseña actual no es correcta."}
            )
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "La nueva contraseña debe ser distinta a la actual."}
            )
        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"new_password": list(error.messages)}) from error
        return attrs


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PasswordChangeRateThrottle]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        revoke_user_tokens(user)
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "must_change_password": False,
        })

# Create your views here.
