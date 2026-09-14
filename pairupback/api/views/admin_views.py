import json
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg, F
from django.db.models.functions import TruncDate
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from ..models import (
    User, MentorProfile, Booking, Payment, Review,
    ProblemPost, PlatformSetting, AuditLog, ContactMessage
)
from ..permissions import IsAdminOrSuperAdmin, IsSuperAdmin
from ..helpers import error_response, success_response, log_audit
from ..notifications import notify_mentor_approval, notify_dispute_resolved
from .mentor_views import split_comma_string


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def stats(request):
    total_learners = User.objects.filter(role='learner').count()
    total_mentors = User.objects.filter(role='mentor').count()
    total_bookings = Booking.objects.count()

    status_counts = Booking.objects.values('status').annotate(c=Count('id'))
    bookings_by_status = {'pending': 0, 'accepted': 0, 'paid': 0, 'completed': 0, 'cancelled': 0, 'disputed': 0}
    for item in status_counts:
        bookings_by_status[item['status']] = item['c']

    released_payments = Payment.objects.filter(status='released')
    held_payments = Payment.objects.filter(status='held')
    refunded_payments = Payment.objects.filter(status='refunded')

    total_revenue = released_payments.aggregate(s=Sum('amount'))['s'] or 0.0
    total_escrow_held = held_payments.aggregate(s=Sum('amount'))['s'] or 0.0
    total_refunded = refunded_payments.aggregate(s=Sum('amount'))['s'] or 0.0

    total_platform_fees = released_payments.aggregate(s=Sum('platform_fee'))['s'] or 0.0
    pending_platform_fees = held_payments.aggregate(s=Sum('platform_fee'))['s'] or 0.0
    total_mentor_payouts = total_revenue - total_platform_fees

    fourteen_days_ago = timezone.now() - timedelta(days=14)
    daily_rows = (
        Payment.objects.filter(status__in=['released', 'held'], created_at__gte=fourteen_days_ago)
        .annotate(d=TruncDate('created_at'))
        .values('d')
        .annotate(total=Sum('amount'))
        .order_by('d')
    )
    revenue_by_day = [
        {'date': row['d'].strftime('%Y-%m-%d') if row['d'] else '', 'total': float(row['total'] or 0.0)}
        for row in daily_rows
    ]

    return success_response({
        'total_learners': total_learners,
        'total_mentors': total_mentors,
        'total_bookings': total_bookings,
        'bookings_by_status': bookings_by_status,
        'total_revenue_released': float(total_revenue),
        'total_escrow_held': float(total_escrow_held),
        'total_refunded': float(total_refunded),
        'total_platform_fees': float(total_platform_fees),
        'pending_platform_fees': float(pending_platform_fees),
        'total_mentor_payouts': float(total_mentor_payouts),
        'revenue_by_day': revenue_by_day,
    })


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def list_users(request):
    role = request.GET.get('role')
    if role == 'mentor':
        mentors = MentorProfile.objects.select_related('user').filter(user__role='mentor').order_by('-user__created_at')
        results = [
            {
                'id': m.user.id,
                'user_id': m.user.id,
                'mentor_id': m.id,
                'name': m.user.name,
                'email': m.user.email,
                'created_at': m.user.created_at.isoformat() if m.user.created_at else None,
                'title': m.title,
                'hourly_rate': float(m.hourly_rate),
                'rating_avg': float(m.rating_avg),
                'sessions_completed': m.sessions_completed,
                'disputes_count': m.disputes_count,
                'online_status': m.online_status,
                'approval_status': m.approval_status,
            }
            for m in mentors
        ]
    else:
        qs = User.objects.all()
        if role == 'learner':
            qs = qs.filter(role='learner')
        else:
            qs = qs.exclude(role='admin')
        qs = qs.order_by('-created_at')
        results = [
            {
                'id': u.id,
                'name': u.name,
                'email': u.email,
                'role': u.role,
                'created_at': u.created_at.isoformat() if u.created_at else None,
            }
            for u in qs
        ]

    return success_response(results)


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def list_all_users(request):
    users = User.objects.all().select_related('mentor_profile').order_by('-created_at')
    results = []
    for u in users:
        item = {
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role,
            'created_at': u.created_at.isoformat() if u.created_at else None,
        }
        mp = getattr(u, 'mentor_profile', None)
        if mp:
            item['mentor_id'] = mp.id
            item['mentor_title'] = mp.title
            item['hourly_rate'] = float(mp.hourly_rate)
            item['rating_avg'] = float(mp.rating_avg)
            item['sessions_completed'] = mp.sessions_completed
            item['disputes_count'] = mp.disputes_count
            item['approval_status'] = mp.approval_status
        results.append(item)
    return success_response(results)


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def list_payments(request):
    payments = Payment.objects.select_related('booking', 'booking__learner', 'booking__mentor').order_by('-created_at')
    results = [
        {
            'id': p.id,
            'amount': float(p.amount),
            'platform_fee': float(p.platform_fee),
            'net_payout': float(p.amount - p.platform_fee),
            'status': p.status,
            'created_at': p.created_at.isoformat() if p.created_at else None,
            'booking_id': p.booking.id,
            'topic': p.booking.topic,
            'booking_status': p.booking.status,
            'learner_name': p.booking.learner.name,
            'mentor_name': p.booking.mentor.name,
        }
        for p in payments
    ]
    return success_response(results)


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def list_bookings(request):
    bookings = Booking.objects.select_related('learner', 'mentor').prefetch_related('payments').order_by('-created_at')
    results = []
    for b in bookings:
        last_pay = b.payments.first()
        results.append({
            'id': b.id,
            'topic': b.topic,
            'price': float(b.price),
            'duration_minutes': b.duration_minutes,
            'status': b.status,
            'created_at': b.created_at.isoformat() if b.created_at else None,
            'learner_name': b.learner.name,
            'mentor_name': b.mentor.name,
            'payment_status': last_pay.status if last_pay else None,
        })
    return success_response(results)


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def pending_mentors(request):
    pending = MentorProfile.objects.filter(approval_status='pending').select_related('user').order_by('user__created_at')
    results = [
        {
            'id': m.user.id,
            'user_id': m.user.id,
            'mentor_id': m.id,
            'profile_id': m.id,
            'name': m.user.name,
            'email': m.user.email,
            'created_at': m.user.created_at.isoformat() if m.user.created_at else None,
            'title': m.title,
            'bio': m.bio,
            'skills': split_comma_string(m.skills),
            'hourly_rate': float(m.hourly_rate),
            'approval_status': m.approval_status,
        }
        for m in pending
    ]
    return success_response(results)


@api_view(['POST'])
@permission_classes([IsAdminOrSuperAdmin])
def approve_mentor(request, mentor_id):
    profile = MentorProfile.objects.filter(Q(user_id=mentor_id) | Q(id=mentor_id)).first()
    if not profile:
        return error_response('Mentor profile not found', status.HTTP_404_NOT_FOUND)

    profile.approval_status = 'approved'
    profile.save()
    User.objects.filter(id=profile.user_id).update(role='mentor')

    notify_mentor_approval(profile, approved=True)
    log_audit(request.user, 'mentor.approve', 'user', profile.user_id)
    return success_response({'message': 'Mentor approved — they now appear in search results'})


@api_view(['POST'])
@permission_classes([IsAdminOrSuperAdmin])
def reject_mentor(request, mentor_id):
    profile = MentorProfile.objects.filter(Q(user_id=mentor_id) | Q(id=mentor_id)).first()
    if not profile:
        return error_response('Mentor profile not found', status.HTTP_404_NOT_FOUND)

    profile.approval_status = 'rejected'
    profile.save()

    notify_mentor_approval(profile, approved=False)
    log_audit(request.user, 'mentor.reject', 'user', profile.user_id)
    return success_response({'message': 'Mentor rejected'})


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def list_disputes(request):
    disputed = Booking.objects.filter(status='disputed').select_related('learner', 'mentor', 'disputed_by').order_by('-created_at')
    results = [
        {
            'id': b.id,
            'topic': b.topic,
            'price': float(b.price),
            'created_at': b.created_at.isoformat() if b.created_at else None,
            'dispute_reason': b.dispute_reason,
            'learner_name': b.learner.name,
            'mentor_name': b.mentor.name,
            'disputed_by_name': b.disputed_by.name if b.disputed_by else 'Unknown',
        }
        for b in disputed
    ]
    return success_response(results)


@api_view(['POST'])
@permission_classes([IsAdminOrSuperAdmin])
def resolve_dispute(request, booking_id):
    data = request.data or {}
    resolution = str(data.get('action', '')).strip().lower()
    if resolution not in ('release', 'refund'):
        return error_response('action must be either "release" or "refund"', status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        booking = Booking.objects.select_related('learner', 'mentor').get(id=booking_id, status='disputed')
    except Booking.DoesNotExist:
        return error_response('Disputed booking not found', status.HTTP_404_NOT_FOUND)

    profile, _ = MentorProfile.objects.get_or_create(user_id=booking.mentor_id)

    if resolution == 'release':
        booking.status = 'completed'
        booking.save()
        Payment.objects.filter(booking=booking).update(status='released')
        profile.sessions_completed += 1
    else:
        booking.status = 'cancelled'
        booking.save()
        Payment.objects.filter(booking=booking).update(status='refunded')

    profile.disputes_count += 1
    profile.save()

    notify_dispute_resolved(booking, resolution)
    log_audit(request.user, f'dispute.resolve.{resolution}', 'booking', booking_id)
    return success_response({'message': f'Dispute resolved: {resolution}'})


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def payouts(request):
    mentors = MentorProfile.objects.select_related('user').filter(user__role='mentor').order_by('user__name')
    results = []
    for m in mentors:
        payments = Payment.objects.filter(booking__mentor=m.user)
        gross_paid = payments.filter(status='released').aggregate(s=Sum('amount'))['s'] or 0.0
        fee_taken = payments.filter(status='released').aggregate(s=Sum('platform_fee'))['s'] or 0.0
        net_paid_out = gross_paid - fee_taken

        pending_gross = payments.filter(status='held').aggregate(s=Sum('amount'))['s'] or 0.0
        pending_fee = payments.filter(status='held').aggregate(s=Sum('platform_fee'))['s'] or 0.0
        pending_net = pending_gross - pending_fee

        payout_count = payments.filter(status='released').count()

        results.append({
            'id': m.user.id,
            'name': m.user.name,
            'email': m.user.email,
            'gross_paid': float(gross_paid),
            'platform_fee_taken': float(fee_taken),
            'net_paid_out': float(net_paid_out),
            'pending_escrow_gross': float(pending_gross),
            'pending_escrow_net': float(pending_net),
            'payout_count': payout_count,
        })

    results.sort(key=lambda x: x['net_paid_out'], reverse=True)
    return success_response(results)


@api_view(['GET', 'PUT'])
def admin_settings(request):
    if request.method == 'GET':
        if not (request.user and request.user.role in ('admin', 'superadmin')):
            return error_response('Admin access required', status.HTTP_403_FORBIDDEN)
        settings_dict = {s.setting_key: s.setting_value for s in PlatformSetting.objects.all()}
        if 'commission_percent' not in settings_dict:
            settings_dict['commission_percent'] = '10'
        if 'allow_role_switching' not in settings_dict:
            settings_dict['allow_role_switching'] = 'true'
        return success_response(settings_dict)

    # PUT is Admin or Superadmin
    if not (request.user and request.user.role in ('admin', 'superadmin')):
        return error_response('Admin access required to update platform settings', status.HTTP_403_FORBIDDEN)

    data = request.data or {}
    for key, value in data.items():
        PlatformSetting.objects.update_or_create(
            setting_key=str(key),
            defaults={'setting_value': str(value)}
        )

    log_audit(request.user, 'settings.update', 'platform_settings', details=json.dumps(data))
    return success_response({'message': 'Settings updated'})


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def list_reviews(request):
    reviews = Review.objects.select_related('learner', 'mentor', 'booking').order_by('-created_at')
    results = [
        {
            'id': r.id,
            'rating': r.rating,
            'comment': r.comment or '',
            'created_at': r.created_at.isoformat() if r.created_at else None,
            'learner_name': r.learner.name,
            'mentor_name': r.mentor.name,
            'topic': r.booking.topic,
        }
        for r in reviews
    ]
    return success_response(results)


@api_view(['DELETE'])
@permission_classes([IsAdminOrSuperAdmin])
def delete_review(request, review_id):
    try:
        review = Review.objects.get(id=review_id)
    except Review.DoesNotExist:
        return error_response('Review not found', status.HTTP_404_NOT_FOUND)

    mentor_id = review.mentor_id
    review.delete()

    avg = Review.objects.filter(mentor_id=mentor_id).aggregate(Avg('rating'))['rating__avg']
    profile, _ = MentorProfile.objects.get_or_create(user_id=mentor_id)
    profile.rating_avg = round(float(avg or 0.0), 2)
    profile.save()

    log_audit(request.user, 'review.delete', 'review', review_id)
    return success_response({'message': 'Review deleted'})


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def admin_problems(request):
    problems = ProblemPost.objects.select_related('learner').annotate(
        proposal_count=Count('proposals')
    ).order_by('-created_at')

    results = []
    for p in problems:
        results.append({
            'id': p.id,
            'title': p.title,
            'description': p.description,
            'skills': split_comma_string(p.skills),
            'budget': float(p.budget) if p.budget is not None else None,
            'status': p.status,
            'created_at': p.created_at.isoformat() if p.created_at else None,
            'learner_name': p.learner.name,
            'proposal_count': p.proposal_count,
        })
    return success_response(results)


@api_view(['POST'])
@permission_classes([IsAdminOrSuperAdmin])
def admin_close_problem(request, problem_id):
    updated = ProblemPost.objects.filter(id=problem_id).update(status='closed')
    if not updated:
        return error_response('Problem post not found', status.HTTP_404_NOT_FOUND)

    log_audit(request.user, 'problem.close', 'problem_post', problem_id)
    return success_response({'message': 'Problem post closed'})


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def list_refunds(request):
    refunds = Payment.objects.filter(status='refunded').select_related('booking', 'booking__learner', 'booking__mentor').order_by('-created_at')
    results = [
        {
            'id': p.id,
            'amount': float(p.amount),
            'created_at': p.created_at.isoformat() if p.created_at else None,
            'booking_id': p.booking.id,
            'topic': p.booking.topic,
            'dispute_reason': p.booking.dispute_reason,
            'learner_name': p.booking.learner.name,
            'mentor_name': p.booking.mentor.name,
        }
        for p in refunds
    ]
    return success_response(results)


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def notifications(request):
    alerts = []

    pending_count = MentorProfile.objects.filter(approval_status='pending').count()
    if pending_count > 0:
        alerts.append({
            'type': 'mentor_pending',
            'severity': 'info',
            'message': f"{pending_count} mentor{'s' if pending_count != 1 else ''} waiting for approval",
            'link': 'verification.php'
        })

    disputes_count = Booking.objects.filter(status='disputed').count()
    if disputes_count > 0:
        alerts.append({
            'type': 'dispute_open',
            'severity': 'warning',
            'message': f"{disputes_count} open dispute{'s' if disputes_count != 1 else ''} need resolution",
            'link': 'disputes.php'
        })

    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_contacts = ContactMessage.objects.filter(created_at__gte=seven_days_ago).count()
    if recent_contacts > 0:
        alerts.append({
            'type': 'contact_new',
            'severity': 'info',
            'message': f"{recent_contacts} new contact message{'s' if recent_contacts != 1 else ''} in the last 7 days",
            'link': 'reports.php'
        })

    recent_refunds = Payment.objects.filter(status='refunded', created_at__gte=seven_days_ago).count()
    if recent_refunds > 0:
        alerts.append({
            'type': 'refunds_recent',
            'severity': 'info',
            'message': f"{recent_refunds} refund{'s' if recent_refunds != 1 else ''} in the last 7 days",
            'link': 'refunds.php'
        })

    return success_response({'alerts': alerts})


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def audit_logs(request):
    logs = AuditLog.objects.all().order_by('-created_at')[:200]
    results = [
        {
            'id': l.id,
            'actor_id': l.actor_id,
            'actor_name': l.actor_name,
            'action': l.action,
            'target_type': l.target_type,
            'target_id': l.target_id,
            'details': l.details,
            'created_at': l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]
    return success_response(results)


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def contact_messages(request):
    msgs = ContactMessage.objects.all().order_by('-created_at')[:200]
    results = [
        {
            'id': m.id,
            'name': m.name,
            'email': m.email,
            'subject': m.subject,
            'message': m.message,
            'created_at': m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]
    return success_response(results)


@api_view(['POST'])
@permission_classes([IsAdminOrSuperAdmin])
def admin_switch_user_role(request, user_id):
    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return error_response('User not found', status.HTTP_404_NOT_FOUND)

    if target_user.role == 'superadmin':
        return error_response('Cannot change the role of a superadmin', status.HTTP_403_FORBIDDEN)
    if target_user.role == 'admin' and request.user.role != 'superadmin':
        return error_response('Only superadmins can change the role of an admin', status.HTTP_403_FORBIDDEN)

    data = request.data or {}
    target_role = str(data.get('role', '')).strip().lower()
    if not target_role:
        target_role = 'mentor' if target_user.role == 'learner' else 'learner'

    if target_role not in ('learner', 'mentor'):
        return error_response('Role must be either "learner" or "mentor"', status.HTTP_422_UNPROCESSABLE_ENTITY)

    old_role = target_user.role
    target_user.role = target_role
    target_user.save()

    if target_role == 'mentor':
        profile, _ = MentorProfile.objects.get_or_create(user=target_user)
        if profile.approval_status != 'approved':
            profile.approval_status = 'approved'
            profile.save()

    log_audit(request.user, 'user.switch_role', 'user', target_user.id)

    return success_response({
        'message': f'Successfully switched {target_user.name} from {old_role} to {target_role}',
        'user': {
            'id': target_user.id,
            'name': target_user.name,
            'email': target_user.email,
            'role': target_user.role,
        }
    })
