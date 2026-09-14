import re
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import status
from ..models import ContactMessage
from ..helpers import error_response, success_response


@api_view(['POST'])
@permission_classes([AllowAny])
def submit_contact(request):
    data = request.data or {}
    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip()
    subject = str(data.get('subject', '')).strip()
    message = str(data.get('message', '')).strip()

    if not name or not email or not message:
        return error_response('name, email, and message are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return error_response('Invalid email address', status.HTTP_422_UNPROCESSABLE_ENTITY)

    ContactMessage.objects.create(
        name=name,
        email=email,
        subject=subject,
        message=message
    )
    return success_response({"message": "Thanks — we'll get back to you soon."}, status_code=status.HTTP_201_CREATED)
