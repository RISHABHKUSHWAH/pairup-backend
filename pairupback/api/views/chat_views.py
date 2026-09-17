import os
import re
import mimetypes
from pathlib import Path
from datetime import datetime
from django.conf import settings
from django.http import FileResponse
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from django.db.models import Q, Max
from django.utils import timezone
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

    contract_id = data.get('contract_id')
    if contract_id is not None:
        try:
            contract_id = int(contract_id)
        except (ValueError, TypeError):
            contract_id = None

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
        contract_id=contract_id,
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

    try:
        contract_id = int(request.GET.get('contract_id', 0))
    except (ValueError, TypeError):
        contract_id = 0

    if other_id <= 0:
        return error_response('Query param "with" (the other user id) is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Filter messages visible to current user
    filters = (
        (Q(sender=user) & Q(receiver_id=other_id) & Q(deleted_by_sender=False)) |
        (Q(sender_id=other_id) & Q(receiver=user) & Q(deleted_by_receiver=False))
    )

    if contract_id > 0:
        filters = filters & Q(contract_id=contract_id)
    else:
        filters = filters & Q(contract_id__isnull=True)

    messages = Message.objects.filter(filters).order_by('created_at')

    results = [
        {
            'id': m.id,
            'sender_id': m.sender_id,
            'receiver_id': m.receiver_id,
            'booking_id': m.booking_id,
            'contract_id': m.contract_id,
            'body': m.decrypted_body,
            'created_at': m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]
    return success_response(results)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversations(request):
    user = request.user
    
    # Find all messages visible to current user
    visible_msgs = Message.objects.filter(
        (Q(sender=user) & Q(deleted_by_sender=False)) |
        (Q(receiver=user) & Q(deleted_by_receiver=False))
    )
    all_msgs = visible_msgs.values_list('sender_id', 'receiver_id', 'contract_id')
    
    threads = set()
    for sender_id, receiver_id, contract_id in all_msgs:
        partner_id = sender_id if receiver_id == user.id else receiver_id
        threads.add((partner_id, contract_id))

    convos = []
    for pid, cid in threads:
        try:
            partner = User.objects.get(id=pid)
        except User.DoesNotExist:
            continue

        filters = (
            (Q(sender=user) & Q(receiver=partner) & Q(deleted_by_sender=False)) |
            (Q(sender=partner) & Q(receiver=user) & Q(deleted_by_receiver=False))
        )
        if cid:
            filters = filters & Q(contract_id=cid)
        else:
            filters = filters & Q(contract_id__isnull=True)

        last_msg = Message.objects.filter(filters).select_related('contract').order_by('-created_at').first()

        if not last_msg:
            continue

        contract_title = None
        if cid and last_msg.contract:
            contract_title = last_msg.contract.title

        convos.append({
            'other_id': partner.id,
            'other_name': partner.name,
            'other_role': partner.role,
            'user_id': partner.id,
            'name': partner.name,
            'role': partner.role,
            'contract_id': cid,
            'contract_title': contract_title,
            'avatar': partner.name[:2].upper() if partner.name else 'U',
            'last_message': last_msg.decrypted_body,
            'last_message_mine': last_msg.sender_id == user.id,
            'last_message_at': last_msg.created_at.isoformat() if last_msg.created_at else None,
            'last_time': last_msg.created_at.strftime('%I:%M %p') if last_msg.created_at else '',
        })

    convos.sort(key=lambda x: x['last_message_at'] or '', reverse=True)
    return success_response(convos)


def find_attachment_file(name=None, url=None):
    """
    Locates an attachment file on disk.
    Tries relative url, SessionFile match, and search across settings.MEDIA_ROOT.
    """
    media_root = Path(settings.MEDIA_ROOT)

    # 1. If explicit url is provided
    if url:
        clean_url = url.split('?')[0].strip()
        if clean_url.startswith('/uploads/'):
            clean_url = clean_url[len('/uploads/'):]
        elif clean_url.startswith('uploads/'):
            clean_url = clean_url[len('uploads/'):]
        candidate = media_root / clean_url
        if candidate.exists() and candidate.is_file():
            return candidate

    if not name:
        return None

    clean_target = name.strip().replace('\\', '/').split('/')[-1]

    # 2. Check SessionFile
    try:
        from ..models import SessionFile
        sf = SessionFile.objects.filter(filename=clean_target).first()
        if sf and sf.file and sf.file.name:
            sf_path = media_root / sf.file.name
            if sf_path.exists() and sf_path.is_file():
                return sf_path
    except Exception:
        pass

    # 3. Search MEDIA_ROOT
    underscore_target = clean_target.replace(' ', '_')

    for item in media_root.rglob('*'):
        if item.is_file():
            if item.name == clean_target or item.name == underscore_target:
                return item
            if underscore_target and underscore_target.lower() in item.name.lower():
                return item

    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_chat_attachment(request):
    file_obj = request.FILES.get('file')
    if not file_obj:
        return error_response('No file provided in request', status.HTTP_422_UNPROCESSABLE_ENTITY)

    if file_obj.size > 25 * 1024 * 1024:
        return error_response('File exceeds 25MB limit', status.HTTP_422_UNPROCESSABLE_ENTITY)

    today = datetime.now()
    date_path = today.strftime('%Y/%m/%d')
    upload_dir = Path(settings.MEDIA_ROOT) / 'chat_attachments' / date_path
    upload_dir.mkdir(parents=True, exist_ok=True)

    clean_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file_obj.name)
    timestamp = int(today.timestamp())
    saved_filename = f"{request.user.id}_{timestamp}_{clean_name}"
    file_path = upload_dir / saved_filename

    with open(file_path, 'wb+') as dest:
        for chunk in file_obj.chunks():
            dest.write(chunk)

    rel_url = f"/uploads/chat_attachments/{date_path}/{saved_filename}"
    return success_response({
        'filename': file_obj.name,
        'url': rel_url,
        'size': file_obj.size,
    }, status_code=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def download_chat_attachment(request):
    name = request.GET.get('name', '').strip()
    url = request.GET.get('url', '').strip()

    file_path = find_attachment_file(name=name, url=url)
    if not file_path or not file_path.exists():
        return error_response('Attachment file not found', status.HTTP_404_NOT_FOUND)

    filename_to_use = name if name else file_path.name
    content_type, _ = mimetypes.guess_type(str(file_path))
    file_handle = open(file_path, 'rb')
    response = FileResponse(file_handle, content_type=content_type or 'application/octet-stream', as_attachment=True, filename=filename_to_use)
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
def view_chat_attachment(request):
    name = request.GET.get('name', '').strip()
    url = request.GET.get('url', '').strip()

    file_path = find_attachment_file(name=name, url=url)
    if not file_path or not file_path.exists():
        return error_response('Attachment file not found', status.HTTP_404_NOT_FOUND)

    filename_to_use = name if name else file_path.name
    content_type, _ = mimetypes.guess_type(str(file_path))
    file_handle = open(file_path, 'rb')
    response = FileResponse(file_handle, content_type=content_type or 'application/octet-stream')
    response['Content-Disposition'] = f'inline; filename="{filename_to_use}"'
    return response


@api_view(['DELETE', 'POST'])
@permission_classes([IsAuthenticated])
def clear_conversation(request):
    """
    Clears all messages in a conversation thread for the requesting user only
    (optionally scoped to a contract). The other participant's chat remains intact.
    """
    user = request.user
    data = request.data or {}
    other_id = request.GET.get('with') or data.get('with') or data.get('other_id')
    try:
        other_id = int(other_id)
    except (ValueError, TypeError):
        other_id = 0

    if other_id <= 0:
        return error_response('Query param or body "with" (other user ID) is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    raw_cid = request.GET.get('contract_id') or data.get('contract_id')
    try:
        contract_id = int(raw_cid) if raw_cid is not None and str(raw_cid).strip() != '' else 0
    except (ValueError, TypeError):
        contract_id = 0

    filters = (Q(sender=user) & Q(receiver_id=other_id)) | (Q(sender_id=other_id) & Q(receiver=user))
    if contract_id > 0:
        filters = filters & Q(contract_id=contract_id)
    else:
        filters = filters & Q(contract_id__isnull=True)

    # Mark as deleted on user's side only
    sent_updated = Message.objects.filter(filters, sender=user).update(deleted_by_sender=True)
    recv_updated = Message.objects.filter(filters, receiver=user).update(deleted_by_receiver=True)

    # Purge messages where both sides have deleted
    Message.objects.filter(filters, deleted_by_sender=True, deleted_by_receiver=True).delete()

    return success_response({
        'deleted_count': sent_updated + recv_updated,
        'message': 'Chat conversation cleared on your side'
    })


@api_view(['DELETE', 'POST'])
@permission_classes([IsAuthenticated])
def delete_message(request, message_id):
    """
    Deletes an individual chat message.
    Supports deleting for 'me' (our side only) or 'everyone' (both sides, only for own sent messages within 1 minute).
    """
    user = request.user
    data = request.data or {}
    delete_for = request.GET.get('delete_for') or data.get('delete_for') or 'me'

    try:
        msg = Message.objects.get(id=message_id)
    except Message.DoesNotExist:
        return error_response('Message not found', status.HTTP_404_NOT_FOUND)

    if msg.sender_id != user.id and msg.receiver_id != user.id:
        return error_response('You do not have permission to delete this message', status.HTTP_403_FORBIDDEN)

    deleted_id = msg.id

    if str(delete_for).lower() == 'everyone':
        # Rule: Only own sent message, and sent within 1 minute (60 seconds)
        if msg.sender_id != user.id:
            return error_response('You can only delete your own sent messages for everyone.', status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        time_diff = (now - msg.created_at).total_seconds() if msg.created_at else 999
        if time_diff > 65:  # 60 seconds with 5s buffer for network latency
            return error_response('Messages can only be deleted for everyone within 1 minute of sending.', status.HTTP_422_UNPROCESSABLE_ENTITY)

        msg.delete()
        return success_response({
            'id': deleted_id,
            'deleted_for': 'everyone',
            'message': 'Message deleted for everyone'
        })
    else:
        # Delete only for requesting user ('me')
        if msg.sender_id == user.id:
            msg.deleted_by_sender = True
            msg.save(update_fields=['deleted_by_sender'])
        elif msg.receiver_id == user.id:
            msg.deleted_by_receiver = True
            msg.save(update_fields=['deleted_by_receiver'])

        # If both sides deleted it, purge from DB
        if msg.deleted_by_sender and msg.deleted_by_receiver:
            msg.delete()

        return success_response({
            'id': deleted_id,
            'deleted_for': 'me',
            'message': 'Message deleted for you'
        })

