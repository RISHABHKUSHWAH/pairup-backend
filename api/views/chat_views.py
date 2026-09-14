from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Q, Max
from ..models import User, Message
from ..helpers import error_response, success_response, check_leak_guard
from ..notifications import notify_chat_message


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def messages_endpoint(request):
    if request.method == 'POST':
        return send_message(request)
    return list_messages(request)


def send_message(request):
    user = request.user
    data = request.data or {}
    try:
        receiver_id = int(data.get('receiver_id', 0))
    except (ValueError, TypeError):
        receiver_id = 0

    body = str(data.get('body', '')).strip()
    booking_id = data.get('booking_id')
    if booking_id is not None:
        try:
            booking_id = int(booking_id)
        except (ValueError, TypeError):
            booking_id = None

    if receiver_id <= 0 or not body:
        return error_response('receiver_id and body are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    if not User.objects.filter(id=receiver_id).exists():
        return error_response('Receiver not found', status.HTTP_404_NOT_FOUND)

    if check_leak_guard(body):
        return error_response(
            'For your safety, sharing phone numbers, emails, or external links in chat is not allowed.',
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    msg = Message.objects.create(
        sender=user,
        receiver_id=receiver_id,
        booking_id=booking_id,
        body=body
    )
    notify_chat_message(msg)
    return success_response({'id': msg.id}, status_code=status.HTTP_201_CREATED)


def list_messages(request):

    user = request.user
    try:
        other_id = int(request.GET.get('with', 0))
    except (ValueError, TypeError):
        other_id = 0

    if other_id <= 0:
        return error_response('Query param "with" (the other user id) is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    messages = Message.objects.filter(
        (Q(sender=user) & Q(receiver_id=other_id)) |
        (Q(sender_id=other_id) & Q(receiver=user))
    ).order_by('created_at')

    results = [
        {
            'id': m.id,
            'sender_id': m.sender_id,
            'receiver_id': m.receiver_id,
            'booking_id': m.booking_id,
            'body': m.body,
            'created_at': m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]
    return success_response(results)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversations(request):
    user = request.user
    # Find all users that the current user has sent to or received from
    all_msgs = Message.objects.filter(Q(sender=user) | Q(receiver=user))
    partner_ids = set()
    for m in all_msgs.values_list('sender_id', 'receiver_id'):
        partner_ids.add(m[0] if m[1] == user.id else m[1])
    partner_ids.discard(user.id)

    convos = []
    for pid in partner_ids:
        try:
            partner = User.objects.get(id=pid)
        except User.DoesNotExist:
            continue

        last_msg = Message.objects.filter(
            (Q(sender=user) & Q(receiver=partner)) |
            (Q(sender=partner) & Q(receiver=user))
        ).order_by('-created_at').first()

        if not last_msg:
            continue

        convos.append({
            'other_id': partner.id,
            'other_name': partner.name,
            'other_role': partner.role,
            'user_id': partner.id,
            'name': partner.name,
            'role': partner.role,
            'avatar': partner.name[:2].upper() if partner.name else 'U',
            'last_message': last_msg.body,
            'last_message_mine': last_msg.sender_id == user.id,
            'last_message_at': last_msg.created_at.isoformat() if last_msg.created_at else None,
            'last_time': last_msg.created_at.strftime('%I:%M %p') if last_msg.created_at else '',
        })

    convos.sort(key=lambda x: x['last_message_at'] or '', reverse=True)
    return success_response(convos)
