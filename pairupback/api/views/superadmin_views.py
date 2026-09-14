from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from ..models import User
from ..permissions import IsSuperAdmin
from ..helpers import error_response, success_response


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def list_admins(request):
    admins = User.objects.filter(role__in=['admin', 'superadmin']).order_by('-role', 'created_at')
    results = [
        {
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role,
            'created_at': u.created_at.isoformat() if u.created_at else None,
        }
        for u in admins
    ]
    return success_response(results)


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def search_users(request):
    email = request.GET.get('email', '').strip()
    if not email:
        return error_response('Query param "email" is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    users = User.objects.filter(email__icontains=email).exclude(role__in=['admin', 'superadmin'])[:10]
    results = [
        {
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role,
        }
        for u in users
    ]
    return success_response(results)


@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def promote_admin(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return error_response('User not found', status.HTTP_404_NOT_FOUND)

    if user.role in ('admin', 'superadmin'):
        return error_response('This user already has admin access', status.HTTP_409_CONFLICT)

    user.role = 'admin'
    user.is_staff = True
    user.save()
    return success_response({'message': 'User promoted to admin'})


@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def revoke_admin(request, user_id):
    if user_id == request.user.id:
        return error_response('You cannot revoke your own superadmin access', status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return error_response('User not found', status.HTTP_404_NOT_FOUND)

    if user.role == 'superadmin':
        return error_response('Cannot revoke another superadmin from here', status.HTTP_403_FORBIDDEN)

    if user.role != 'admin':
        return error_response('This user is not an admin', status.HTTP_422_UNPROCESSABLE_ENTITY)

    user.role = 'learner'
    user.is_staff = False
    user.save()
    return success_response({'message': 'Admin access revoked'})
