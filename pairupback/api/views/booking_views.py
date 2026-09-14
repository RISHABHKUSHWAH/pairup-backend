from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Q
from ..models import User, MentorProfile, Booking, Payment, SessionNote
from ..permissions import IsLearner, IsMentor
from ..helpers import error_response, success_response, get_commission_percent
from ..notifications import (
    notify_booking_created,
    notify_booking_accepted,
    notify_payment_held,
    notify_session_completed,
    notify_dispute_raised,
)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def bookings_endpoint(request):
    if request.method == 'POST':
        if request.user.role != 'learner':
            return error_response("This action requires the 'learner' role", status.HTTP_403_FORBIDDEN)
        return create_booking(request)
    return list_mine(request)


def create_booking(request):
    data = request.data or {}
    try:
        mentor_id = int(data.get('mentor_id', 0))
    except (ValueError, TypeError):
        mentor_id = 0

    topic = str(data.get('topic', '')).strip()
    duration = int(data.get('duration_minutes', 30) or 30)
    try:
        price = float(data.get('price', 0))
    except (ValueError, TypeError):
        price = 0.0

    if mentor_id <= 0 or not topic or price <= 0:
        return error_response('mentor_id, topic, and price are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    if not MentorProfile.objects.filter(user_id=mentor_id, approval_status='approved').exists() and not User.objects.filter(id=mentor_id, role='mentor').exists():
        return error_response('Mentor not found', status.HTTP_404_NOT_FOUND)

    booking = Booking.objects.create(
        learner=request.user,
        mentor_id=mentor_id,
        topic=topic,
        duration_minutes=duration,
        price=price,
        status='pending'
    )
    notify_booking_created(booking)
    return success_response(
        {'id': booking.id, 'message': 'Session requested. Waiting for mentor to accept.'},
        status_code=status.HTTP_201_CREATED
    )


def list_mine(request):

    user = request.user
    bookings = Booking.objects.filter(Q(learner=user) | Q(mentor=user)).select_related('learner', 'mentor').order_by('-created_at')

    results = []
    for b in bookings:
        results.append({
            'id': b.id,
            'learner_id': b.learner_id,
            'mentor_id': b.mentor_id,
            'status': b.status,
            'topic': b.topic,
            'duration_minutes': b.duration_minutes,
            'price': float(b.price),
            'scheduled_at': b.scheduled_at,
            'dispute_reason': b.dispute_reason,
            'disputed_by': b.disputed_by_id,
            'created_at': b.created_at.isoformat() if b.created_at else None,
            'learner_name': b.learner.name,
            'mentor_name': b.mentor.name,
        })
    return success_response(results)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMentor])
def accept_booking(request, booking_id):
    user = request.user
    try:
        booking = Booking.objects.select_related('learner', 'mentor').get(id=booking_id, mentor=user, status='pending')
    except Booking.DoesNotExist:
        return error_response('Booking not found, not yours, or already actioned', status.HTTP_404_NOT_FOUND)

    booking.status = 'accepted'
    booking.save()
    notify_booking_accepted(booking)
    return success_response({'message': 'Booking accepted. Learner can now pay to confirm.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsLearner])
def pay_booking(request, booking_id):
    user = request.user
    try:
        booking = Booking.objects.select_related('learner', 'mentor').get(id=booking_id, learner=user, status='accepted')
    except Booking.DoesNotExist:
        return error_response('Booking not found, not yours, or not yet accepted by the mentor', status.HTTP_404_NOT_FOUND)

    commission_percent = get_commission_percent()
    platform_fee = round(booking.price * (commission_percent / 100), 2)

    payment = Payment.objects.create(
        booking=booking,
        amount=booking.price,
        platform_fee=platform_fee,
        status='held'
    )
    booking.status = 'paid'
    booking.save()

    notify_payment_held(booking, payment)
    return success_response({'message': 'Payment held in escrow. Session is confirmed.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_booking(request, booking_id):
    user = request.user
    try:
        booking = Booking.objects.select_related('learner', 'mentor').get(Q(learner=user) | Q(mentor=user), id=booking_id, status='paid')
    except Booking.DoesNotExist:
        return error_response('Booking not found, not yours, or not in a paid state', status.HTTP_404_NOT_FOUND)

    booking.status = 'completed'
    booking.save()

    payment = Payment.objects.filter(booking=booking).first()
    Payment.objects.filter(booking=booking).update(status='released')

    # Update mentor completed sessions
    mentor_profile, _ = MentorProfile.objects.get_or_create(user_id=booking.mentor_id)
    mentor_profile.sessions_completed += 1
    mentor_profile.save()

    notify_session_completed(booking, payment)
    return success_response({'message': 'Session marked complete. Funds released to the mentor.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dispute_booking(request, booking_id):
    user = request.user
    data = request.data or {}
    reason = str(data.get('reason', '')).strip()
    if not reason:
        return error_response('A reason is required to raise a dispute', status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        booking = Booking.objects.select_related('learner', 'mentor').get(Q(learner=user) | Q(mentor=user), id=booking_id, status='paid')
    except Booking.DoesNotExist:
        return error_response('Booking not found, not yours, or not in a paid state (only paid, unfinished sessions can be disputed)', status.HTTP_404_NOT_FOUND)

    booking.status = 'disputed'
    booking.dispute_reason = reason
    booking.disputed_by = user
    booking.save()

    notify_dispute_raised(booking, reason, user)
    return success_response({'message': 'Dispute raised. Our team will review and resolve it.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_detail(request, booking_id):
    user = request.user
    try:
        b = Booking.objects.select_related('learner', 'mentor').get(
            Q(learner=user) | Q(mentor=user),
            id=booking_id
        )
    except Booking.DoesNotExist:
        return error_response('Booking not found or not yours', status.HTTP_404_NOT_FOUND)

    return success_response({
        'id': b.id,
        'learner_id': b.learner_id,
        'mentor_id': b.mentor_id,
        'status': b.status,
        'topic': b.topic,
        'duration_minutes': b.duration_minutes,
        'price': float(b.price),
        'scheduled_at': b.scheduled_at,
        'dispute_reason': b.dispute_reason,
        'disputed_by': b.disputed_by_id,
        'created_at': b.created_at.isoformat() if b.created_at else None,
        'learner_name': b.learner.name,
        'mentor_name': b.mentor.name,
    })


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def session_notes(request, booking_id):
    user = request.user
    if not Booking.objects.filter(Q(learner=user) | Q(mentor=user), id=booking_id).exists():
        return error_response('Booking not found or not yours', status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        note = SessionNote.objects.filter(booking_id=booking_id, user=user).first()
        return success_response({'notes': note.notes if note else ''})

    # PUT
    data = request.data or {}
    notes_text = str(data.get('notes', ''))
    note, _ = SessionNote.objects.get_or_create(booking_id=booking_id, user=user)
    note.notes = notes_text
    note.save()
    return success_response({'message': 'Notes saved'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payments_mine(request):
    user = request.user
    payments = Payment.objects.filter(
        Q(booking__learner=user) | Q(booking__mentor=user)
    ).select_related('booking', 'booking__learner', 'booking__mentor').order_by('-created_at')

    results = []
    for p in payments:
        b = p.booking
        results.append({
            'id': p.id,
            'amount': float(p.amount),
            'platform_fee': float(p.platform_fee),
            'net_amount': float(p.amount - p.platform_fee),
            'status': p.status,
            'created_at': p.created_at.isoformat() if p.created_at else None,
            'booking_id': b.id,
            'topic': b.topic,
            'booking_status': b.status,
            'learner_name': b.learner.name,
            'mentor_name': b.mentor.name,
            'learner_id': b.learner_id,
            'mentor_id': b.mentor_id,
        })
    return success_response(results)
