from datetime import datetime, timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Q
from ..models import User, MentorProfile, Contract, Booking, Payment, Review
from ..helpers import error_response, success_response, get_commission_percent, log_audit
from ..slot_utils import parse_iso_datetime, check_slot_conflict
from ..notifications import (
    notify_contract_proposed,
    notify_contract_paid,
    notify_contract_completed_by_mentor,
    notify_contract_approved,
    notify_contract_disputed,
)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def list_or_create_contracts(request):
    """
    GET: List all contracts where user is learner or mentor.
    POST: Propose a new contract.
    """
    if request.method == 'POST':
        return create_contract(request)
    return list_contracts(request)


def create_contract(request):
    user = request.user
    data = request.data or {}

    try:
        mentor_id = int(data.get('mentor_id', 0))
    except (ValueError, TypeError):
        mentor_id = 0

    try:
        learner_id = int(data.get('learner_id', 0))
    except (ValueError, TypeError):
        learner_id = 0

    # Auto-resolve learner/mentor if one is missing or other_user_id provided
    other_user_id = data.get('other_user_id')
    if other_user_id:
        try:
            other_uid = int(other_user_id)
            if user.role == 'mentor':
                learner_id = other_uid
            elif user.role == 'learner':
                mentor_id = other_uid
        except (ValueError, TypeError):
            pass

    if user.role == 'mentor' and not mentor_id:
        mentor_id = user.id
    elif user.role == 'learner' and not learner_id:
        learner_id = user.id


    if mentor_id <= 0 or learner_id <= 0:
        return error_response('Both mentor_id and learner_id are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    if mentor_id == learner_id:
        return error_response('A user cannot create a contract with themselves', status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        mentor = User.objects.get(id=mentor_id)
        learner = User.objects.get(id=learner_id)
    except User.DoesNotExist:
        return error_response('Mentor or Learner not found', status.HTTP_404_NOT_FOUND)

    title = str(data.get('title', '')).strip()
    if not title:
        title = f"{mentor.name} & {learner.name} Mentorship Contract"

    description = str(data.get('description', '')).strip()
    technology = str(data.get('technology', '')).strip()

    # Topics can be a list or comma-separated string
    raw_topics = data.get('topics', [])
    if isinstance(raw_topics, str):
        topics = [t.strip() for t in raw_topics.split(',') if t.strip()]
    elif isinstance(raw_topics, list):
        topics = [str(t).strip() for t in raw_topics if str(t).strip()]
    else:
        topics = []

    try:
        total_sessions = max(1, int(data.get('total_sessions', 3) or 3))
    except (ValueError, TypeError):
        total_sessions = 3

    try:
        session_duration = max(15, int(data.get('session_duration_minutes', 60) or 60))
    except (ValueError, TypeError):
        session_duration = 60

    try:
        total_price = float(data.get('total_price', 0))
    except (ValueError, TypeError):
        total_price = 0.0

    if total_price <= 0:
        return error_response('A valid total_price greater than 0 is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    contract = Contract.objects.create(
        learner=learner,
        mentor=mentor,
        created_by=user,
        title=title,
        description=description,
        technology=technology,
        topics=topics,
        total_sessions=total_sessions,
        session_duration_minutes=session_duration,
        total_price=total_price,
        status='proposed'
    )

    notify_contract_proposed(contract)
    log_audit(user, 'contract_proposed', 'Contract', contract.id, f"Proposed contract '{title}' for ₹{total_price}")

    return success_response(
        {
            'id': contract.id,
            'message': 'Contract proposed successfully.',
            'contract': _format_contract_summary(contract)
        },
        status_code=status.HTTP_201_CREATED
    )


def list_contracts(request):
    user = request.user
    if user.role in ['admin', 'superadmin']:
        contracts = Contract.objects.all().select_related('learner', 'mentor', 'created_by').order_by('-created_at')
    else:
        contracts = Contract.objects.filter(
            Q(learner=user) | Q(mentor=user)
        ).select_related('learner', 'mentor', 'created_by').order_by('-created_at')

    # Optional status filter
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        contracts = contracts.filter(status=status_filter)

    # Optional search query
    q = str(request.GET.get('q', '')).strip()
    if q:
        contracts = contracts.filter(
            Q(title__icontains=q) |
            Q(technology__icontains=q) |
            Q(mentor__name__icontains=q) |
            Q(learner__name__icontains=q)
        )

    results = []
    for c in contracts:
        results.append(_format_contract_summary(c))

    return success_response(results)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def contract_detail(request, contract_id):
    user = request.user
    try:
        if user.role in ['admin', 'superadmin']:
            contract = Contract.objects.select_related('learner', 'mentor', 'created_by').get(id=contract_id)
        else:
            contract = Contract.objects.select_related('learner', 'mentor', 'created_by').get(
                Q(learner=user) | Q(mentor=user),
                id=contract_id
            )
    except Contract.DoesNotExist:
        return error_response('Contract not found or not accessible', status.HTTP_404_NOT_FOUND)

    # Fetch all linked sessions (Bookings)
    sessions = Booking.objects.filter(contract=contract).order_by('session_number', 'id')
    sessions_data = []
    for s in sessions:
        sessions_data.append({
            'id': s.id,
            'session_number': s.session_number,
            'topic': s.topic,
            'duration_minutes': s.duration_minutes,
            'status': s.status,
            'scheduled_at': s.scheduled_at,
            'room_url': f"/session/{s.id}",
            'has_notes': s.session_notes.exists(),
            'files_count': s.session_files.count(),
            'has_summary': hasattr(s, 'summary'),
        })

    # Fetch escrow payment record if exists
    payment = Payment.objects.filter(contract=contract).first()
    payment_data = None
    if payment:
        payment_data = {
            'id': payment.id,
            'amount': float(payment.amount),
            'platform_fee': float(payment.platform_fee),
            'net_amount': float(payment.amount - payment.platform_fee),
            'status': payment.status,
            'created_at': payment.created_at.isoformat() if payment.created_at else None,
        }

    # Fetch review if submitted
    review = Review.objects.filter(booking__contract=contract).select_related('learner').first()
    review_data = None
    if review:
        review_data = {
            'id': review.id,
            'rating': review.rating,
            'comment': review.comment,
            'learner_name': review.learner.name,
            'created_at': review.created_at.isoformat() if review.created_at else None,
        }

    data = _format_contract_summary(contract)
    data['sessions'] = sessions_data
    data['payment'] = payment_data
    data['review'] = review_data

    return success_response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pay_contract(request, contract_id):
    """
    Learner funds the contract. Total price is locked in platform Escrow (status='held'),
    contract status becomes 'active', and milestone session Booking records are generated.
    """
    user = request.user
    try:
        contract = Contract.objects.select_related('learner', 'mentor').get(
            id=contract_id,
            learner=user,
            status__in=['proposed', 'accepted']
        )
    except Contract.DoesNotExist:
        return error_response('Contract not found, not yours, or already funded', status.HTTP_404_NOT_FOUND)

    commission_percent = get_commission_percent()
    platform_fee = round(contract.total_price * (commission_percent / 100), 2)

    # Create Escrow Payment record
    Payment.objects.create(
        contract=contract,
        amount=contract.total_price,
        platform_fee=platform_fee,
        status='held'
    )

    contract.status = 'active'
    contract.save()

    # Generate milestone session Booking records if not already created
    if not Booking.objects.filter(contract=contract).exists():
        topics = contract.topics or []
        price_per_session = round(contract.total_price / contract.total_sessions, 2)
        for i in range(1, contract.total_sessions + 1):
            topic_title = topics[i - 1] if (i - 1) < len(topics) else f"Milestone Session {i}"
            Booking.objects.create(
                learner=contract.learner,
                mentor=contract.mentor,
                contract=contract,
                session_number=i,
                topic=f"Session {i}: {topic_title}",
                duration_minutes=contract.session_duration_minutes,
                price=price_per_session,
                status='paid' # Funded and ready to be scheduled / conducted
            )

    notify_contract_paid(contract)
    log_audit(user, 'contract_paid_escrow', 'Contract', contract.id, f"Funded ₹{contract.total_price} in escrow")

    return success_response({
        'message': f"Contract funded! ₹{contract.total_price:,.0f} is held in platform escrow. All {contract.total_sessions} sessions are activated.",
        'contract_id': contract.id,
        'status': contract.status
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_contract_by_mentor(request, contract_id):
    """
    Mentor marks all sessions complete and submits the contract for learner review.
    """
    user = request.user
    try:
        contract = Contract.objects.select_related('learner', 'mentor').get(
            id=contract_id,
            mentor=user,
            status='active'
        )
    except Contract.DoesNotExist:
        return error_response('Contract not found, not yours, or not in active state', status.HTTP_404_NOT_FOUND)

    # Mark all linked sessions as completed if not already done
    Booking.objects.filter(contract=contract).update(status='completed')

    contract.status = 'completed_by_mentor'
    contract.save()

    notify_contract_completed_by_mentor(contract)
    log_audit(user, 'contract_completed_by_mentor', 'Contract', contract.id, f"Mentor marked contract '{contract.title}' complete")

    return success_response({
        'message': 'Contract marked as completed! Awaiting learner final review and payout approval.',
        'status': contract.status
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_contract(request, contract_id):
    """
    Learner reviews all completed sessions and approves the contract.
    Requires learner to provide rating & feedback before releasing the escrow payment.
    Releases the held escrow payment to the mentor and increments mentor completed sessions.
    """
    user = request.user
    try:
        contract = Contract.objects.select_related('learner', 'mentor').get(
            id=contract_id,
            learner=user,
            status__in=['active', 'completed_by_mentor']
        )
    except Contract.DoesNotExist:
        return error_response('Contract not found, not yours, or already completed/disputed', status.HTTP_404_NOT_FOUND)

    # Validate rating and feedback review
    data = request.data or {}
    rating = data.get('rating')
    comment = str(data.get('comment', '')).strip()

    if not rating:
        return error_response('A star rating (1 to 5) is required before releasing payment.', status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        rating_val = int(rating)
        if rating_val < 1 or rating_val > 5:
            return error_response('Rating must be between 1 and 5 stars.', status.HTTP_422_UNPROCESSABLE_ENTITY)
    except (ValueError, TypeError):
        return error_response('Invalid rating value provided.', status.HTTP_422_UNPROCESSABLE_ENTITY)

    if not comment:
        return error_response('Written feedback is required before approving and releasing payment.', status.HTTP_422_UNPROCESSABLE_ENTITY)

    contract.status = 'completed'
    contract.save()

    # Mark all sessions completed
    Booking.objects.filter(contract=contract).update(status='completed')

    # Release Escrow Payment to mentor
    Payment.objects.filter(contract=contract, status='held').update(status='released')

    # Increment mentor completed sessions counter
    mentor_profile, _ = MentorProfile.objects.get_or_create(user_id=contract.mentor_id)
    mentor_profile.sessions_completed += contract.total_sessions
    mentor_profile.save()

    # Save learner review
    first_booking = Booking.objects.filter(contract=contract).first()
    if first_booking:
        review_obj, created = Review.objects.get_or_create(
            booking=first_booking,
            defaults={
                'learner': contract.learner,
                'mentor': contract.mentor,
                'rating': rating_val,
                'comment': comment
            }
        )
        if not created:
            review_obj.rating = rating_val
            review_obj.comment = comment
            review_obj.save()

        # Recalculate mentor average rating
        all_reviews = Review.objects.filter(mentor=contract.mentor)
        if all_reviews.exists():
            mentor_profile.rating_avg = round(sum(r.rating for r in all_reviews) / all_reviews.count(), 1)
            mentor_profile.save()

    notify_contract_approved(contract)
    log_audit(user, 'contract_approved_release_escrow', 'Contract', contract.id, f"Learner approved contract; ₹{contract.total_price} released to mentor. Rating: {rating_val}/5")

    return success_response({
        'message': f"Contract approved! Rating & feedback submitted and escrow funds (₹{contract.total_price:,.0f}) have been released to {contract.mentor.name}.",
        'status': contract.status
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dispute_contract(request, contract_id):
    """
    Learner or mentor raises a dispute on an active contract.
    """
    user = request.user
    data = request.data or {}
    reason = str(data.get('reason', '')).strip()
    if not reason:
        return error_response('A dispute reason is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        contract = Contract.objects.select_related('learner', 'mentor').get(
            Q(learner=user) | Q(mentor=user),
            id=contract_id,
            status__in=['active', 'completed_by_mentor']
        )
    except Contract.DoesNotExist:
        return error_response('Contract not found, not yours, or not in an active/review state', status.HTTP_404_NOT_FOUND)

    contract.status = 'disputed'
    contract.dispute_reason = reason
    contract.disputed_by = user
    contract.save()

    # Mark linked sessions as disputed
    Booking.objects.filter(contract=contract, status__in=['paid', 'pending']).update(
        status='disputed',
        dispute_reason=reason,
        disputed_by=user
    )

    notify_contract_disputed(contract, reason, user)
    log_audit(user, 'contract_dispute_raised', 'Contract', contract.id, f"Dispute raised: {reason}")

    return success_response({
        'message': 'Dispute registered. Our platform administrators will review all session recordings, notes, and chat logs.',
        'status': contract.status
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def decline_contract(request, contract_id):
    """
    Declines a proposed contract before payment.
    """
    user = request.user
    try:
        contract = Contract.objects.get(
            Q(learner=user) | Q(mentor=user),
            id=contract_id,
            status='proposed'
        )
    except Contract.DoesNotExist:
        return error_response('Contract not found or not in proposed status', status.HTTP_404_NOT_FOUND)

    contract.status = 'declined'
    contract.save()

    log_audit(user, 'contract_declined', 'Contract', contract.id, f"Contract '{contract.title}' declined")

    return success_response({
        'message': 'Contract proposal declined.',
        'status': contract.status
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def schedule_contract_session(request, contract_id, session_id):
    """
    Sets or updates the scheduled date/time for a milestone session in the contract.
    """
    user = request.user
    data = request.data or {}
    scheduled_at = str(data.get('scheduled_at', '')).strip()
    if not scheduled_at:
        return error_response('scheduled_at is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        session = Booking.objects.get(
            Q(learner=user) | Q(mentor=user),
            id=session_id,
            contract_id=contract_id
        )
    except Booking.DoesNotExist:
        return error_response('Milestone session not found or not yours', status.HTTP_404_NOT_FOUND)

    req_start = parse_iso_datetime(scheduled_at)
    if not req_start:
        return error_response('Invalid scheduled_at format. Expected ISO-8601', status.HTTP_422_UNPROCESSABLE_ENTITY)

    now = datetime.now()
    if req_start < now - timedelta(minutes=5):
        return error_response('Cannot schedule a session in the past', status.HTTP_422_UNPROCESSABLE_ENTITY)

    duration = session.duration_minutes or 60
    has_conflict, _ = check_slot_conflict(session.mentor_id, req_start, duration, exclude_booking_id=session.id)
    if has_conflict:
        return error_response('This date and time is already booked by another learner. Please select an available slot.', status.HTTP_409_CONFLICT)

    session.scheduled_at = scheduled_at
    session.save()

    return success_response({
        'message': f"Session {session.session_number} scheduled for {scheduled_at}.",
        'session_id': session.id,
        'scheduled_at': session.scheduled_at
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_resolve_contract(request, contract_id):
    """
    Administrator dispute resolution for a contract.
    Action:
      - 'release_to_mentor': Approves contract delivery, releases escrow payment to mentor.
      - 'refund_to_learner': Refunds escrow payment to learner, marks contract declined/refunded.
    """
    user = request.user
    if user.role not in ['admin', 'superadmin']:
        return error_response('Admin privileges required', status.HTTP_403_FORBIDDEN)

    try:
        contract = Contract.objects.select_related('learner', 'mentor').get(id=contract_id)
    except Contract.DoesNotExist:
        return error_response('Contract not found', status.HTTP_404_NOT_FOUND)

    data = request.data or {}
    action = data.get('action')
    admin_notes = str(data.get('admin_notes', '')).strip()

    if action == 'release_to_mentor':
        contract.status = 'completed'
        contract.save()
        Booking.objects.filter(contract=contract).update(status='completed')
        Payment.objects.filter(contract=contract, status='held').update(status='released')
        mentor_profile, _ = MentorProfile.objects.get_or_create(user_id=contract.mentor_id)
        mentor_profile.sessions_completed += contract.total_sessions
        mentor_profile.save()

        notify_contract_approved(contract)
        log_audit(user, 'admin_contract_resolve_release', 'Contract', contract.id, f"Admin resolved dispute: released ₹{contract.total_price} to mentor. Notes: {admin_notes}")
        return success_response({
            'message': f"Dispute resolved. Escrow payment (₹{contract.total_price:,.0f}) released to mentor {contract.mentor.name}.",
            'status': contract.status
        })

    elif action == 'refund_to_learner':
        contract.status = 'declined'
        contract.save()
        Booking.objects.filter(contract=contract).update(status='cancelled')
        Payment.objects.filter(contract=contract, status='held').update(status='refunded')

        log_audit(user, 'admin_contract_resolve_refund', 'Contract', contract.id, f"Admin resolved dispute: refunded ₹{contract.total_price} to learner. Notes: {admin_notes}")
        return success_response({
            'message': f"Dispute resolved. Escrow payment (₹{contract.total_price:,.0f}) refunded to learner {contract.learner.name}.",
            'status': contract.status
        })
    else:
        return error_response("Invalid action. Must be 'release_to_mentor' or 'refund_to_learner'.", status.HTTP_422_UNPROCESSABLE_ENTITY)


def _format_contract_summary(contract):
    completed_sessions = contract.sessions.filter(status='completed').count() if hasattr(contract, 'sessions') else 0
    escrow_payment = Payment.objects.filter(contract=contract).first()
    escrow_status = escrow_payment.status if escrow_payment else None

    return {
        'id': contract.id,
        'title': contract.title,
        'description': contract.description,
        'technology': contract.technology,
        'topics': contract.topics or [],
        'total_sessions': contract.total_sessions,
        'completed_sessions': completed_sessions,
        'session_duration_minutes': contract.session_duration_minutes,
        'total_price': float(contract.total_price),
        'status': contract.status,
        'escrow_status': escrow_status,
        'learner_id': contract.learner_id,
        'learner_name': contract.learner.name,
        'mentor_id': contract.mentor_id,
        'mentor_name': contract.mentor.name,
        'created_by_id': contract.created_by_id,
        'dispute_reason': contract.dispute_reason,
        'disputed_by_id': contract.disputed_by_id,
        'created_at': contract.created_at.isoformat() if contract.created_at else None,
        'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
    }

