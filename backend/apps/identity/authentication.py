from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from django.utils import timezone

class RevocableJWTAuthentication(JWTAuthentication):
    """Reject access tokens issued before the user's password/security epoch."""
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        issued_at = validated_token.get("iat")
        if issued_at and user.jwt_valid_after and int(user.jwt_valid_after.timestamp()) > int(issued_at):
            raise AuthenticationFailed("Las credenciales de esta sesión ya no son válidas.")
        return user

def revoke_user_tokens(user):
    """Blacklist outstanding refresh tokens and advance the access-token epoch."""
    user.jwt_valid_after = timezone.now()
    user.save(update_fields=["jwt_valid_after"])
    token_ids = OutstandingToken.objects.filter(user=user).exclude(
        id__in=BlacklistedToken.objects.values_list("token_id", flat=True)
    ).values_list("id", flat=True)
    for token in OutstandingToken.objects.filter(id__in=token_ids).iterator():
        BlacklistedToken.objects.get_or_create(token=token)
