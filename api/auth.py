import time
import jwt
from django.conf import settings
from rest_framework import authentication, exceptions
from .models import User


def generate_jwt(user, ttl_hours=None):
    if ttl_hours is None:
        ttl_hours = settings.JWT_TTL_HOURS
    now = int(time.time())
    payload = {
        'sub': user.id,
        'role': user.role,
        'name': user.name,
        'iat': now,
        'exp': now + (ttl_hours * 3600),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm='HS256')


def decode_jwt(token):
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=['HS256'], options={'verify_sub': False})
    except jwt.ExpiredSignatureError:
        raise exceptions.AuthenticationFailed('Token has expired')
    except jwt.InvalidTokenError:
        raise exceptions.AuthenticationFailed('Invalid or expired token')



class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None

        token = parts[1]
        payload = decode_jwt(token)

        user_id = payload.get('sub')
        if not user_id:
            raise exceptions.AuthenticationFailed('Invalid token payload')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User not found')

        if not user.is_active:
            raise exceptions.AuthenticationFailed('User is inactive')

        return (user, payload)
