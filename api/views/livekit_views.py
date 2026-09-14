import os
import time
import json
import jwt
from datetime import timedelta
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status

from ..models import Booking, Payment, MentorProfile, SessionFile, SessionSummary, SessionSignal
from ..helpers import error_response, success_response
from ..notifications import notify_session_completed


def get_livekit_config():
    return {
        'url': getattr(settings, 'LIVEKIT_URL', os.environ.get('LIVEKIT_URL', 'wss://pairup-livekit.cloud')),
        'api_key': getattr(settings, 'LIVEKIT_API_KEY', os.environ.get('LIVEKIT_API_KEY', 'pairup_livekit_api_key')),
        'api_secret': getattr(settings, 'LIVEKIT_API_SECRET', os.environ.get('LIVEKIT_API_SECRET', 'pairup_livekit_secret_token_1234567890')),
    }


def format_file_row(f, request=None):
    file_url = f.file.url if f.file else ''
    if request and file_url.startswith('/'):
        file_url = request.build_absolute_uri(file_url)
    return {
        'id': f.id,
        'booking_id': f.booking_id,
        'filename': f.filename,
        'file_size': f.file_size,
        'file_url': file_url,
        'uploader_id': f.uploader_id,
        'uploader_name': f.uploader.name if f.uploader else 'Anonymous',
        'created_at': f.created_at.isoformat() if f.created_at else None,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def generate_livekit_token(request, booking_id):
    """
    Validates participant eligibility and generates a cryptographically signed
    LiveKit Access Token (JWT) with permissions for audio, video, screen share, and data packets.
    """
    user = request.user
    try:
        booking = Booking.objects.select_related('learner', 'mentor').get(
            Q(learner=user) | Q(mentor=user),
            id=booking_id
        )
    except Booking.DoesNotExist:
        return error_response('Session not found or you are not a participant in this booking', status.HTTP_404_NOT_FOUND)

    if booking.status not in ('paid', 'completed'):
        return error_response(
            f"Cannot join room. Session status must be 'paid' or 'completed' (currently '{booking.status}').",
            status.HTTP_400_BAD_REQUEST
        )

    cfg = get_livekit_config()
    now = int(time.time())
    room_name = f"pairup-session-{booking.id}"
    identity = f"user_{user.id}"

    # LiveKit JWT access token grants
    payload = {
        'iss': cfg['api_key'],
        'sub': identity,
        'name': user.name,
        'iat': now,
        'nbf': now - 5,
        'exp': now + (60 * 60 * 6),  # 6 hours valid
        'video': {
            'room': room_name,
            'roomJoin': True,
            'canPublish': True,
            'canSubscribe': True,
            'canPublishData': True,
            'canPublishSources': ['camera', 'microphone', 'screen_share', 'screen_share_audio'],
            'hidden': False,
        },
        'metadata': json.dumps({
            'user_id': user.id,
            'user_name': user.name,
            'user_role': user.role,
            'booking_id': booking.id,
            'topic': booking.topic,
        })
    }

    token = jwt.encode(payload, cfg['api_secret'], algorithm='HS256')
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    is_mentor = user.id == booking.mentor_id
    other_user = booking.learner if is_mentor else booking.mentor

    return success_response({
        'token': token,
        'server_url': cfg['url'],
        'room_name': room_name,
        'participant_identity': identity,
        'participant_name': user.name,
        'booking_id': booking.id,
        'topic': booking.topic,
        'duration_minutes': booking.duration_minutes,
        'price': float(booking.price),
        'status': booking.status,
        'learner_id': booking.learner_id,
        'learner_name': booking.learner.name,
        'mentor_id': booking.mentor_id,
        'mentor_name': booking.mentor.name,
        'is_mentor': is_mentor,
        'other_name': other_user.name,
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def session_files(request, booking_id):
    """
    List files shared during the session or upload a new file attachment.
    """
    user = request.user
    try:
        booking = Booking.objects.get(Q(learner=user) | Q(mentor=user), id=booking_id)
    except Booking.DoesNotExist:
        return error_response('Session not found or not yours', status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        files = SessionFile.objects.filter(booking=booking).select_related('uploader').order_by('-created_at')
        return success_response([format_file_row(f, request) for f in files])

    # POST file upload
    file_obj = request.FILES.get('file')
    if not file_obj:
        return error_response('No file provided in request', status.HTTP_422_UNPROCESSABLE_ENTITY)

    # 25MB max size limit
    if file_obj.size > 25 * 1024 * 1024:
        return error_response('File exceeds 25MB limit', status.HTTP_422_UNPROCESSABLE_ENTITY)

    filename = request.data.get('filename') or file_obj.name

    session_file = SessionFile.objects.create(
        booking=booking,
        uploader=user,
        file=file_obj,
        filename=filename,
        file_size=file_obj.size,
    )

    return success_response(format_file_row(session_file, request), status_code=status.HTTP_201_CREATED)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def session_summary(request, booking_id):
    """
    Retrieve or save session post-call summary and action items.
    Allows completing the session and releasing escrow funds.
    """
    user = request.user
    try:
        booking = Booking.objects.select_related('learner', 'mentor').get(
            Q(learner=user) | Q(mentor=user),
            id=booking_id
        )
    except Booking.DoesNotExist:
        return error_response('Session not found or not yours', status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        summary = SessionSummary.objects.filter(booking=booking).first()
        if not summary:
            return success_response({
                'booking_id': booking.id,
                'summary_text': '',
                'action_items': '',
                'duration_seconds': 0,
                'is_completed': booking.status == 'completed',
            })
        return success_response({
            'id': summary.id,
            'booking_id': booking.id,
            'summary_text': summary.summary_text,
            'action_items': summary.action_items,
            'duration_seconds': summary.duration_seconds,
            'created_by': summary.created_by.name if summary.created_by else '',
            'created_at': summary.created_at.isoformat() if summary.created_at else None,
            'is_completed': booking.status == 'completed',
        })

    # POST save summary
    data = request.data or {}
    summary_text = str(data.get('summary_text', '')).strip()
    action_items = str(data.get('action_items', '')).strip()
    try:
        duration_seconds = int(data.get('duration_seconds', 0))
    except (ValueError, TypeError):
        duration_seconds = 0

    complete_session = bool(data.get('complete_session', False))

    summary, _ = SessionSummary.objects.get_or_create(booking=booking, defaults={'created_by': user})
    summary.summary_text = summary_text
    summary.action_items = action_items
    if duration_seconds > 0:
        summary.duration_seconds = duration_seconds
    summary.created_by = user
    summary.save()

    # Complete session & release escrow if requested
    if complete_session and booking.status == 'paid':
        booking.status = 'completed'
        booking.save()

        payment = Payment.objects.filter(booking=booking).first()
        Payment.objects.filter(booking=booking).update(status='released')

        profile, _ = MentorProfile.objects.get_or_create(user_id=booking.mentor_id)
        profile.sessions_completed += 1
        profile.save()

        notify_session_completed(booking, payment)

    return success_response({
        'message': 'Session summary saved successfully',
        'is_completed': booking.status == 'completed',
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def session_signal(request, booking_id):
    """
    Real-Time WebRTC signaling channel for peer-to-peer audio, video, and screen sharing.
    POST: Dispatches an SDP offer/answer, ICE candidate, or room state to the other peer.
    GET: Retrieves pending signals sent by the other peer.
    """
    user = request.user
    try:
        booking = Booking.objects.get(Q(learner=user) | Q(mentor=user), id=booking_id)
    except Booking.DoesNotExist:
        return error_response('Session not found or you are not a participant in this booking', status.HTTP_404_NOT_FOUND)

    if request.method == 'POST':
        data = request.data or {}
        signal_type = str(data.get('signal_type', '')).strip()
        signal_payload = data.get('data', {})

        if not signal_type:
            return error_response('signal_type is required', status.HTTP_400_BAD_REQUEST)

        # Create the signal
        sig = SessionSignal.objects.create(
            booking=booking,
            sender=user,
            signal_type=signal_type,
            data=signal_payload,
        )

        # Housekeeping: purge signals older than 10 minutes
        cutoff = timezone.now() - timedelta(minutes=10)
        SessionSignal.objects.filter(booking=booking, created_at__lt=cutoff).delete()

        return success_response({
            'status': 'sent',
            'signal_id': sig.id,
            'signal_type': sig.signal_type,
        }, status_code=status.HTTP_201_CREATED)

    # GET signals from other participant
    try:
        after_id = int(request.query_params.get('after', 0))
    except (ValueError, TypeError):
        after_id = 0

    signals = SessionSignal.objects.filter(
        booking=booking,
        id__gt=after_id
    ).exclude(sender=user).order_by('id')[:50]

    return success_response({
        'signals': [
            {
                'id': s.id,
                'sender_id': s.sender_id,
                'signal_type': s.signal_type,
                'data': s.data,
                'created_at': s.created_at.isoformat(),
            }
            for s in signals
        ]
    })
