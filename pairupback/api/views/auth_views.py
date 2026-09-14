from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from django.db import IntegrityError
from ..models import User, MentorProfile, PlatformSetting
from ..auth import generate_jwt
from ..helpers import error_response, success_response
from ..notifications import create_notification


def is_role_switching_allowed():
    setting = PlatformSetting.objects.filter(setting_key='allow_role_switching').first()
    if not setting:
        return True
    val = str(setting.setting_value).strip().lower()
    return val not in ('false', '0', 'off', 'disabled')


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    data = request.data or {}
    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))
    role = str(data.get('role', 'learner')).strip().lower()

    if not name or not email or not password:
        return error_response('Name, email, and password are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    if role not in ('learner', 'mentor'):
        return error_response('Role must be either "learner" or "mentor"', status.HTTP_422_UNPROCESSABLE_ENTITY)

    if len(password) < 6:
        return error_response('Password must be at least 6 characters', status.HTTP_422_UNPROCESSABLE_ENTITY)

    if User.objects.filter(email=email).exists():
        return error_response('An account with this email already exists', status.HTTP_409_CONFLICT)

    try:
        user = User.objects.create_user(
            email=email,
            name=name,
            password=password,
            role=role
        )

        if role == 'mentor':
            MentorProfile.objects.create(
                user=user,
                approval_status='pending',
                title='',
                bio='',
                skills='',
                hourly_rate=0.0
            )
            create_notification(
                user=user,
                title='Welcome to PairUp! 🚀',
                message='Welcome to PairUp! Complete your mentor profile and submit for verification to start receiving session requests.',
                notification_type='system',
                link='/mentor/profile'
            )
        else:
            create_notification(
                user=user,
                title='Welcome to PairUp! 🚀',
                message='Welcome to PairUp! Explore verified expert mentors or post a problem request to get live 1:1 help.',
                notification_type='system',
                link='/learner/explore'
            )

        token = generate_jwt(user)
        return success_response({
            'token': token,
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role,
            }
        }, status_code=status.HTTP_201_CREATED)

    except IntegrityError:
        return error_response('An account with this email already exists', status.HTTP_409_CONFLICT)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    data = request.data or {}
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))

    if not email or not password:
        return error_response('Email and password are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return error_response('This email is not registered. Please check your email or sign up.', status.HTTP_404_NOT_FOUND)

    if not user.check_password(password):
        return error_response('Incorrect password. Please try again.', status.HTTP_401_UNAUTHORIZED)

    if not user.is_active:
        return error_response('This account has been deactivated', status.HTTP_403_FORBIDDEN)

    token = generate_jwt(user)
    return success_response({
        'token': token,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'allow_role_switching': is_role_switching_allowed(),
        }
    })


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    if request.method == 'GET':
        return success_response({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'allow_role_switching': is_role_switching_allowed(),
            'created_at': user.created_at.isoformat() if user.created_at else None,
        })

    # PUT
    data = request.data or {}
    name = str(data.get('name', '')).strip()
    password = str(data.get('password', '')).strip()

    if name:
        user.name = name
    if password:
        if len(password) < 6:
            return error_response('Password must be at least 6 characters', status.HTTP_422_UNPROCESSABLE_ENTITY)
        user.set_password(password)

    user.save()
    return success_response({
        'message': 'Account updated',
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'allow_role_switching': is_role_switching_allowed(),
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def switch_role(request):
    user = request.user
    if user.role in ('admin', 'superadmin'):
        return error_response('Administrators cannot switch account roles via this endpoint', status.HTTP_403_FORBIDDEN)

    if not is_role_switching_allowed():
        return error_response(
            'Role switching between mentor and learner has been disabled by platform administrator.',
            status.HTTP_403_FORBIDDEN
        )

    data = request.data or {}
    target_role = str(data.get('role', '')).strip().lower()

    if not target_role:
        target_role = 'mentor' if user.role == 'learner' else 'learner'

    if target_role not in ('learner', 'mentor'):
        return error_response('Role must be either "learner" or "mentor"', status.HTTP_422_UNPROCESSABLE_ENTITY)

    if user.role == target_role:
        return error_response(f'You are already in {target_role} mode', status.HTTP_400_BAD_REQUEST)

    user.role = target_role
    user.save()

    if target_role == 'mentor':
        profile, created = MentorProfile.objects.get_or_create(user=user)
        if profile.approval_status != 'approved':
            profile.approval_status = 'approved'
            profile.save()

    token = generate_jwt(user)
    return success_response({
        'message': f'Switched role to {target_role}',
        'token': token,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'allow_role_switching': is_role_switching_allowed(),
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def platform_config(request):
    """
    Returns public platform feature flags and configuration.
    """
    return success_response({
        'allow_role_switching': is_role_switching_allowed(),
    })
