from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Q
from ..models import ProblemPost, ProblemProposal, Booking, MentorProfile, Payment, Notification
from ..permissions import IsLearner, IsMentor
from ..helpers import error_response, success_response, get_commission_percent
from ..notifications import notify_matching_mentors, notify_proposal_submitted, notify_proposal_accepted, notify_payment_held
from .mentor_views import split_comma_string


def format_problem(problem):
    b = float(problem.budget) if problem.budget is not None else None
    learner_name = 'Learner'
    try:
        if hasattr(problem, 'learner') and problem.learner:
            learner_name = problem.learner.name or problem.learner.email.split('@')[0]
    except Exception:
        pass

    return {
        'id': problem.id,
        'learner_id': problem.learner_id,
        'learner_name': learner_name,
        'title': problem.title,
        'description': problem.description,
        'skills': split_comma_string(problem.skills),
        'budget': b,
        'budget_min': b,
        'budget_max': b,
        'status': problem.status,
        'created_at': problem.created_at.isoformat() if problem.created_at else None,
    }


@api_view(['GET', 'POST'])
def problems_endpoint(request):
    if request.method == 'POST':
        if not request.user or not request.user.is_authenticated:
            return error_response('Authentication required', status.HTTP_401_UNAUTHORIZED)
        return create_problem(request)
    return list_problems(request)


def create_problem(request):
    data = request.data or {}
    title = str(data.get('title', '')).strip()
    description = str(data.get('description', '')).strip()
    skills = data.get('skills', '')
    if isinstance(skills, list):
        skills = ', '.join(skills)
    skills = str(skills).strip()

    budget = data.get('budget')
    if budget is not None and str(budget).strip() != '':
        try:
            budget = float(budget)
        except (ValueError, TypeError):
            budget = None
    else:
        budget = None

    if not title or not description:
        return error_response('title and description are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    problem = ProblemPost.objects.create(
        learner=request.user,
        title=title,
        description=description,
        skills=skills,
        budget=budget,
        status='open'
    )
    notify_matching_mentors(problem)
    return success_response({'id': problem.id}, status_code=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_problems(request):
    problems = ProblemPost.objects.filter(learner=request.user).order_by('-created_at')
    results = [format_problem(p) for p in problems]
    return success_response(results)


def list_problems(request):

    qs = ProblemPost.objects.filter(status='open').select_related('learner').order_by('-created_at')

    skill = request.GET.get('skill', '').strip()
    if skill:
        qs = qs.filter(skills__icontains=skill)

    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

    results = []
    for p in qs:
        item = format_problem(p)
        item['learner_name'] = p.learner.name
        results.append(item)
    return success_response(results)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def close_problem(request, problem_id):
    updated = ProblemPost.objects.filter(id=problem_id, learner=request.user).update(status='closed')
    if not updated:
        return error_response('Problem not found or not yours', status.HTTP_404_NOT_FOUND)
    return success_response({'message': 'Marked as closed'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_problem(request, problem_id):
    deleted, _ = ProblemPost.objects.filter(id=problem_id, learner=request.user).delete()
    if not deleted:
        return error_response('Problem not found or not yours', status.HTTP_404_NOT_FOUND)
    return success_response({'message': 'Deleted'})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def problem_proposals_endpoint(request, problem_id):
    if request.method == 'POST':
        if request.user.role != 'mentor':
            return error_response("This action requires the 'mentor' role", status.HTTP_403_FORBIDDEN)
        return submit_proposal(request, problem_id)
    return list_proposals_for_problem(request, problem_id)


def submit_proposal(request, problem_id):
    user = request.user
    data = request.data or {}
    message = str(data.get('message', '')).strip()
    try:
        price = float(data.get('proposed_price', 0))
    except (ValueError, TypeError):
        price = 0.0

    if not message or price <= 0:
        return error_response('message and a proposed_price greater than 0 are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        problem = ProblemPost.objects.get(id=problem_id)
    except ProblemPost.DoesNotExist:
        return error_response('Problem not found', status.HTTP_404_NOT_FOUND)

    if problem.status != 'open':
        return error_response('This problem is no longer open', status.HTTP_409_CONFLICT)

    if ProblemProposal.objects.filter(problem=problem, mentor=user).exists():
        return error_response('You already submitted a proposal on this problem', status.HTTP_409_CONFLICT)

    prop = ProblemProposal.objects.create(
        problem=problem,
        mentor=user,
        message=message,
        proposed_price=price,
        status='pending'
    )
    notify_proposal_submitted(prop)
    return success_response({'id': prop.id}, status_code=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsMentor])
def my_proposals(request):
    proposals = ProblemProposal.objects.filter(mentor=request.user).select_related(
        'problem', 'problem__learner'
    ).order_by('-created_at')

    results = []
    for pr in proposals:
        results.append({
            'id': pr.id,
            'problem_id': pr.problem_id,
            'mentor_id': pr.mentor_id,
            'message': pr.message,
            'proposed_price': float(pr.proposed_price),
            'counter_price': float(pr.counter_price) if pr.counter_price is not None else None,
            'counter_message': pr.counter_message or '',
            'last_action_by': pr.last_action_by,
            'status': pr.status,
            'created_at': pr.created_at.isoformat() if pr.created_at else None,
            'updated_at': pr.updated_at.isoformat() if pr.updated_at else None,
            'problem_title': pr.problem.title,
            'problem_status': pr.problem.status,
            'learner_name': pr.problem.learner.name,
            'learner_id': pr.problem.learner_id,
        })
    return success_response(results)


def list_proposals_for_problem(request, problem_id):
    user = request.user
    try:
        problem = ProblemPost.objects.get(id=problem_id, learner=user)
    except ProblemPost.DoesNotExist:
        return error_response('Problem not found or not yours', status.HTTP_404_NOT_FOUND)

    proposals = ProblemProposal.objects.filter(problem=problem).select_related('mentor').order_by('-created_at')

    results = []
    for pr in proposals:
        profile = MentorProfile.objects.filter(user=pr.mentor).first()
        results.append({
            'id': pr.id,
            'problem_id': pr.problem_id,
            'mentor_id': pr.mentor_id,
            'message': pr.message,
            'proposed_price': float(pr.proposed_price),
            'counter_price': float(pr.counter_price) if pr.counter_price is not None else None,
            'counter_message': pr.counter_message or '',
            'last_action_by': pr.last_action_by,
            'status': pr.status,
            'created_at': pr.created_at.isoformat() if pr.created_at else None,
            'updated_at': pr.updated_at.isoformat() if pr.updated_at else None,
            'mentor_name': pr.mentor.name,
            'mentor_title': profile.title if profile else '',
            'mentor_photo_url': profile.photo_url if profile else None,
            'mentor_rating_avg': float(profile.rating_avg) if profile else 0.0,
            'mentor_hourly_rate': float(profile.hourly_rate) if profile else 0.0,
        })
    return success_response(results)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_proposal(request, problem_id, proposal_id):
    user = request.user
    try:
        problem = ProblemPost.objects.get(id=problem_id, learner=user)
    except ProblemPost.DoesNotExist:
        return error_response('Problem not found or not yours', status.HTTP_404_NOT_FOUND)

    try:
        proposal = ProblemProposal.objects.get(id=proposal_id, problem=problem)
    except ProblemProposal.DoesNotExist:
        return error_response('Proposal not found', status.HTTP_404_NOT_FOUND)

    if proposal.status == 'accepted':
        return error_response('Cannot reject an already accepted proposal', status.HTTP_400_BAD_REQUEST)

    proposal.status = 'rejected'
    proposal.save()

    Notification.objects.create(
        user=proposal.mentor,
        notification_type='proposal',
        title='Proposal Declined',
        message=f'{user.name} has declined your proposal for "{problem.title}".',
        link='/mentor/my-proposals'
    )

    return success_response({
        'message': 'Proposal rejected successfully',
        'proposal_id': proposal.id,
        'status': proposal.status,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def counter_proposal(request, problem_id, proposal_id):
    user = request.user
    try:
        problem = ProblemPost.objects.get(id=problem_id)
    except ProblemPost.DoesNotExist:
        return error_response('Problem not found', status.HTTP_404_NOT_FOUND)

    try:
        proposal = ProblemProposal.objects.select_related('mentor', 'problem', 'problem__learner').get(
            id=proposal_id, problem=problem
        )
    except ProblemProposal.DoesNotExist:
        return error_response('Proposal not found', status.HTTP_404_NOT_FOUND)

    if user.id != problem.learner_id and user.id != proposal.mentor_id:
        return error_response('Permission denied', status.HTTP_403_FORBIDDEN)

    if problem.status != 'open':
        return error_response('Problem is no longer open for negotiation', status.HTTP_409_CONFLICT)

    data = request.data or {}
    try:
        counter_price = float(data.get('counter_price', 0))
    except (ValueError, TypeError):
        return error_response('Valid counter_price is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    if counter_price <= 0:
        return error_response('Counter price must be greater than 0', status.HTTP_422_UNPROCESSABLE_ENTITY)

    counter_message = str(data.get('counter_message', '')).strip()

    proposal.counter_price = counter_price
    proposal.counter_message = counter_message
    proposal.status = 'negotiating'
    proposal.last_action_by = 'learner' if user.id == problem.learner_id else 'mentor'
    proposal.save()

    if user.id == problem.learner_id:
        Notification.objects.create(
            user=proposal.mentor,
            notification_type='proposal',
            title='Counter-Offer Received',
            message=f'{user.name} proposed ₹{counter_price:g} for "{problem.title}".',
            link='/mentor/my-proposals'
        )
    else:
        Notification.objects.create(
            user=problem.learner,
            notification_type='proposal',
            title='Revised Proposal Quote',
            message=f'{user.name} submitted a revised quote of ₹{counter_price:g} for "{problem.title}".',
            link='/learner/my-problems'
        )

    return success_response({
        'message': 'Counter-offer submitted successfully',
        'proposal': {
            'id': proposal.id,
            'proposed_price': float(proposal.proposed_price),
            'counter_price': float(proposal.counter_price),
            'counter_message': proposal.counter_message,
            'status': proposal.status,
            'last_action_by': proposal.last_action_by,
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_counter_offer(request, problem_id, proposal_id):
    user = request.user
    try:
        problem = ProblemPost.objects.get(id=problem_id)
    except ProblemPost.DoesNotExist:
        return error_response('Problem not found', status.HTTP_404_NOT_FOUND)

    try:
        proposal = ProblemProposal.objects.select_related('mentor', 'problem', 'problem__learner').get(
            id=proposal_id, problem=problem
        )
    except ProblemProposal.DoesNotExist:
        return error_response('Proposal not found', status.HTTP_404_NOT_FOUND)

    if user.id != problem.learner_id and user.id != proposal.mentor_id:
        return error_response('Permission denied', status.HTTP_403_FORBIDDEN)

    if proposal.status != 'negotiating' or proposal.counter_price is None:
        return error_response('No active counter-offer to accept', status.HTTP_400_BAD_REQUEST)

    # The person who did NOT submit the last counter can accept it
    if (proposal.last_action_by == 'learner' and user.id == problem.learner_id) or \
       (proposal.last_action_by == 'mentor' and user.id == proposal.mentor_id):
        return error_response('You cannot accept your own counter-offer; wait for the other party', status.HTTP_400_BAD_REQUEST)

    agreed_price = proposal.counter_price
    proposal.proposed_price = agreed_price
    proposal.counter_price = None
    proposal.counter_message = ''
    proposal.status = 'pending'
    proposal.last_action_by = 'mentor' if user.id == proposal.mentor_id else 'learner'
    proposal.save()

    other_user = problem.learner if user.id == proposal.mentor_id else proposal.mentor
    target_link = '/learner/my-problems' if other_user.role == 'learner' else '/mentor/my-proposals'
    Notification.objects.create(
        user=other_user,
        notification_type='proposal',
        title='Counter-Offer Accepted!',
        message=f'{user.name} accepted the counter-offer of ₹{agreed_price:g} for "{problem.title}". Agreement reached!',
        link=target_link
    )

    return success_response({
        'message': f'Counter-offer accepted! Final agreed price is ₹{agreed_price:g}.',
        'agreed_price': float(agreed_price),
        'status': proposal.status,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_proposal(request, problem_id, proposal_id):
    user = request.user
    try:
        problem = ProblemPost.objects.get(id=problem_id, learner=user)
    except ProblemPost.DoesNotExist:
        return error_response('Problem not found or not yours', status.HTTP_404_NOT_FOUND)

    if problem.status != 'open':
        return error_response('Problem is no longer open', status.HTTP_409_CONFLICT)

    try:
        proposal = ProblemProposal.objects.select_related('mentor').get(
            id=proposal_id, problem=problem, status__in=['pending', 'negotiating']
        )
    except ProblemProposal.DoesNotExist:
        return error_response('Proposal not found or cannot be accepted', status.HTTP_404_NOT_FOUND)

    data = request.data or {}
    payment_method = str(data.get('payment_method', 'escrow_direct'))
    is_paid = data.get('is_paid', True)

    final_price = float(proposal.counter_price if (proposal.counter_price and proposal.last_action_by == 'mentor') else proposal.proposed_price)

    booking = Booking.objects.create(
        learner=user,
        mentor=proposal.mentor,
        topic=problem.title,
        duration_minutes=60,
        price=final_price,
        status='paid' if is_paid else 'accepted'
    )

    payment = None
    if is_paid:
        commission_percent = get_commission_percent()
        platform_fee = round(final_price * (commission_percent / 100.0), 2)

        payment = Payment.objects.create(
            booking=booking,
            amount=final_price,
            platform_fee=platform_fee,
            status='held'
        )
        notify_payment_held(booking, payment)

    proposal.status = 'accepted'
    proposal.proposed_price = final_price
    proposal.counter_price = None
    proposal.save()

    # Decline other proposals
    ProblemProposal.objects.filter(problem=problem).exclude(id=proposal.id).update(status='declined')

    problem.status = 'closed'
    problem.save()

    notify_proposal_accepted(proposal, booking)

    if is_paid:
        Notification.objects.create(
            user=proposal.mentor,
            notification_type='payment',
            title='Session Booked & Escrow Paid!',
            message=f'{user.name} accepted your proposal for "{problem.title}". ₹{final_price:g} is held safely in Escrow.',
            link='/mentor/sessions'
        )

    return success_response({
        'message': 'Proposal accepted! Escrow payment held and booking confirmed.',
        'booking_id': booking.id,
        'booking_status': booking.status,
        'price': final_price,
        'payment_id': payment.id if payment else None,
        'room_url': f"/session?booking_id={booking.id}",
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsMentor])
def withdraw_proposal(request, proposal_id):
    deleted, _ = ProblemProposal.objects.filter(id=proposal_id, mentor=request.user, status__in=['pending', 'negotiating']).delete()
    if not deleted:
        return error_response('Proposal not found or cannot be withdrawn', status.HTTP_404_NOT_FOUND)
    return success_response({'message': 'Proposal withdrawn successfully'})

