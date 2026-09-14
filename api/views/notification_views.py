from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from ..models import Notification
from ..helpers import error_response, success_response


def serialize_notification(n):
    link = n.link or ''
    if not link:
        t = (n.notification_type or '').lower()
        role = getattr(n.user, 'role', '') if hasattr(n, 'user') and n.user else ''
        if role == 'mentor':
            if t in ['proposal']:
                link = '/mentor/my-proposals'
            elif t in ['problem']:
                link = '/mentor/explore-problems'
            elif t in ['session', 'booking']:
                link = '/mentor/sessions'
            elif t in ['payment', 'escrow']:
                link = '/mentor/earnings'
            elif t in ['review']:
                link = '/mentor/reviews'
            elif t in ['contract']:
                link = '/mentor/contracts'
            elif t in ['message', 'chat']:
                link = '/chat'
            else:
                link = '/mentor/dashboard'
        else:
            if t in ['proposal', 'problem']:
                link = '/learner/my-problems'
            elif t in ['session', 'booking']:
                link = '/learner/sessions'
            elif t in ['payment', 'escrow']:
                link = '/learner/payments'
            elif t in ['review']:
                link = '/learner/reviews'
            elif t in ['contract']:
                link = '/learner/contracts'
            elif t in ['message', 'chat']:
                link = '/chat'
            else:
                link = '/learner/dashboard'
    elif link == '/learner/problems':
        link = '/learner/my-problems'
    elif link == '/mentor/problem-requests':
        link = '/mentor/explore-problems'
    elif link.startswith('/messages'):
        link = link.replace('/messages', '/chat', 1)

    return {
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.notification_type,
        'link': link,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat() if n.created_at else None,
    }


def seed_starter_notifications(user):
    is_mentor = user.role == 'mentor'
    if is_mentor:
        Notification.objects.create(
            user=user,
            title='New Problem Matching Your Skills',
            message='A learner posted: Django REST Framework JWT authentication blocker. Budget: ₹1,200.',
            notification_type='problem',
            link='/mentor/explore-problems',
            is_read=False,
        )
        Notification.objects.create(
            user=user,
            title='Proposal Accepted! 🎉',
            message="Your proposal for 'React state synchronization bug' was accepted. Booking created in Sessions.",
            notification_type='proposal',
            link='/mentor/sessions',
            is_read=False,
        )
        Notification.objects.create(
            user=user,
            title='Payment Released to Your Balance',
            message='₹1,500 has been released from escrow for completed session with Sarah Connor.',
            notification_type='payment',
            link='/mentor/earnings',
            is_read=True,
        )
        Notification.objects.create(
            user=user,
            title='New 5★ Rating Received!',
            message="Sarah Connor left a 5-star review: 'Outstanding mentor! Fixed our backend query issue in under 30 mins.'",
            notification_type='review',
            link='/mentor/reviews',
            is_read=True,
        )
    else:
        Notification.objects.create(
            user=user,
            title='New Mentor Proposal Pitched',
            message="Alex Rivera submitted a ₹1,200 proposal on your problem: 'Django query performance issue'.",
            notification_type='proposal',
            link='/learner/my-problems',
            is_read=False,
        )
        Notification.objects.create(
            user=user,
            title='Session Confirmed',
            message='Your pairing session with Alex Rivera is confirmed. Room opens 5 minutes before scheduled time.',
            notification_type='session',
            link='/learner/sessions',
            is_read=False,
        )
        Notification.objects.create(
            user=user,
            title='Payment in Escrow',
            message='Payment of ₹1,200 is safely held in escrow and will only be released after your approval.',
            notification_type='payment',
            link='/learner/payments',
            is_read=True,
        )
        Notification.objects.create(
            user=user,
            title='Welcome to PairUp!',
            message='Explore vetted expert software engineers or post a problem request to get unstuck fast.',
            notification_type='system',
            link='/learner/explore',
            is_read=True,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return success_response([serialize_notification(n) for n in notifications])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_read(request, notification_id):
    try:
        n = Notification.objects.get(id=notification_id, user=request.user)
        n.is_read = True
        n.save()
        return success_response(serialize_notification(n))
    except Notification.DoesNotExist:
        return error_response('Notification not found', status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    Notification.objects.filter(user=request.user).update(is_read=True)
    return success_response({'message': 'All notifications marked as read'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_notifications(request):
    Notification.objects.filter(user=request.user).delete()
    return success_response({'message': 'All notifications cleared'})
