import re
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from .models import PlatformSetting, AuditLog


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        # Format DRF validation/permission/auth errors as {"error": "..."} to match PHP Response::error
        if isinstance(response.data, dict):
            if 'error' in response.data:
                err_msg = response.data['error']
            elif 'detail' in response.data:
                err_msg = str(response.data['detail'])
            else:
                first_key = next(iter(response.data))
                val = response.data[first_key]
                if isinstance(val, list) and val:
                    err_msg = f"{first_key}: {val[0]}"
                else:
                    err_msg = f"{first_key}: {val}"
        elif isinstance(response.data, list) and response.data:
            err_msg = str(response.data[0])
        else:
            err_msg = str(response.data)

        response.data = {'error': err_msg}
    return response


def error_response(message, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': message}, status=status_code)


def success_response(data=None, status_code=status.HTTP_200_OK):
    if data is None:
        data = {}
    return Response(data, status=status_code)


def check_leak_guard(text):
    r"""
    Returns True if text contains phone numbers, email addresses, or URLs.
    Matching PHP: /(\+?\d[\d\-\s]{7,}\d)|([\w.+-]+@[\w-]+\.[a-z]{2,})|(https?:\/\/)/i
    """
    pattern = r'(\+?\d[\d\-\s]{7,}\d)|([\w.+-]+@[\w-]+\.[a-z]{2,})|(https?://)'
    return bool(re.search(pattern, text, re.IGNORECASE))


def get_commission_percent():
    try:
        setting = PlatformSetting.objects.get(setting_key='commission_percent')
        return float(setting.setting_value)
    except (PlatformSetting.DoesNotExist, ValueError):
        return 10.0


def log_audit(actor, action, target_type=None, target_id=None, details=None):
    AuditLog.objects.create(
        actor=actor,
        actor_name=actor.name,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details
    )
