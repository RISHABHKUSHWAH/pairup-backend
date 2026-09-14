from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from django.db.models import Avg, Q
from ..models import Booking, Review, MentorProfile
from ..permissions import IsLearner
from ..helpers import error_response, success_response
from ..notifications import notify_review_created


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def reviews_endpoint(request):
    if request.method == 'POST':
        if not request.user or not request.user.is_authenticated:
            return error_response('Authentication required', status.HTTP_401_UNAUTHORIZED)
        if request.user.role != 'learner':
            return error_response("This action requires the 'learner' role", status.HTTP_403_FORBIDDEN)
        return create_review(request)
    return list_reviews(request)


def create_review(request):
    user = request.user
    data = request.data or {}

    try:
        booking_id = int(data.get('booking_id', 0))
    except (ValueError, TypeError):
        booking_id = 0

    try:
        rating = int(data.get('rating', 0))
    except (ValueError, TypeError):
        rating = 0

    comment = str(data.get('comment', '')).strip()

    if booking_id <= 0 or rating < 1 or rating > 5:
        return error_response('booking_id and a rating between 1 and 5 are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        booking = Booking.objects.get(id=booking_id, learner=user, status='completed')
    except Booking.DoesNotExist:
        return error_response('Booking not found, not yours, or not yet marked completed', status.HTTP_404_NOT_FOUND)

    if Review.objects.filter(booking=booking).exists():
        return error_response('You have already reviewed this session', status.HTTP_409_CONFLICT)

    review = Review.objects.create(
        booking=booking,
        learner=user,
        mentor_id=booking.mentor_id,
        rating=rating,
        comment=comment
    )

    # Recalculate average rating for the mentor
    avg = Review.objects.filter(mentor_id=booking.mentor_id).aggregate(Avg('rating'))['rating__avg']
    profile, _ = MentorProfile.objects.get_or_create(user_id=booking.mentor_id)
    profile.rating_avg = round(float(avg or 0.0), 2)
    profile.save()

    notify_review_created(review)

    return success_response({'id': review.id, 'message': 'Review submitted. Thank you!'}, status_code=status.HTTP_201_CREATED)


def list_reviews(request):

    mentor_id = request.GET.get('mentor_id')
    qs = Review.objects.select_related('learner')
    if mentor_id:
        try:
            qs = qs.filter(mentor_id=int(mentor_id))
        except (ValueError, TypeError):
            qs = qs.none()

    qs = qs.order_by('-created_at')
    results = [
        {
            'id': r.id,
            'rating': r.rating,
            'comment': r.comment or '',
            'created_at': r.created_at.isoformat() if r.created_at else None,
            'learner_name': r.learner.name,
        }
        for r in qs
    ]
    return success_response(results)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_reviews(request):
    user = request.user
    qs = Review.objects.filter(Q(learner=user) | Q(mentor=user)).select_related('learner', 'mentor', 'booking').order_by('-created_at')

    results = [
        {
            'id': r.id,
            'rating': r.rating,
            'comment': r.comment or '',
            'created_at': r.created_at.isoformat() if r.created_at else None,
            'learner_name': r.learner.name,
            'mentor_name': r.mentor.name,
            'topic': r.booking.topic,
            'is_mine': r.learner_id == user.id,
        }
        for r in qs
    ]
    return success_response(results)
