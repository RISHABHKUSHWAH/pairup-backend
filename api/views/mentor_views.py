import os
import time
from django.conf import settings
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from ..models import (
    User, MentorProfile, Review,
    MentorExperience, MentorProject, MentorEducation,
    MentorCertification, MentorAward, MentorAvailability
)
from ..auth import generate_jwt
from ..permissions import IsMentor, IsLearner
from ..helpers import error_response, success_response


def split_comma_string(val):
    if not val:
        return []
    return [item.strip() for item in str(val).split(',') if item.strip()]


def format_mentor_row(mentor_profile):
    completed = mentor_profile.sessions_completed
    disputes = mentor_profile.disputes_count
    total_outcomes = completed + disputes
    completion_rate = round((completed / total_outcomes) * 100) if total_outcomes > 0 else None

    return {
        'user_id': mentor_profile.user.id,
        'name': mentor_profile.user.name,
        'photo_url': mentor_profile.photo_url,
        'title': mentor_profile.title,
        'company': mentor_profile.company,
        'years_experience': mentor_profile.years_experience,
        'location': mentor_profile.location,
        'languages': split_comma_string(mentor_profile.languages),
        'skills': split_comma_string(mentor_profile.skills),
        'hourly_rate': float(mentor_profile.hourly_rate),
        'approval_status': mentor_profile.approval_status,
        'verified': mentor_profile.approval_status == 'approved',
        'online': bool(mentor_profile.online_status),
        'rating_avg': float(mentor_profile.rating_avg),
        'sessions_completed': completed,
        'disputes_count': disputes,
        'completion_rate': completion_rate,
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def list_mentors(request):
    qs = MentorProfile.objects.select_related('user').filter(
        approval_status='approved'
    )

    skill = request.GET.get('skill', '').strip()
    if skill:
        skills_list = [s.strip() for s in skill.split(',') if s.strip()]
        if skills_list:
            skill_q = Q()
            for s in skills_list:
                skill_q |= Q(skills__icontains=s)
            qs = qs.filter(skill_q)

    search = request.GET.get('search', '').strip()
    if search:
        if ',' in search:
            search_terms = [t.strip() for t in search.split(',') if t.strip()]
            search_q = Q()
            for t in search_terms:
                search_q |= (
                    Q(user__name__icontains=t) |
                    Q(title__icontains=t) |
                    Q(bio__icontains=t) |
                    Q(skills__icontains=t)
                )
            qs = qs.filter(search_q)
        else:
            search_terms = search.split()
            for t in search_terms:
                qs = qs.filter(
                    Q(user__name__icontains=t) |
                    Q(title__icontains=t) |
                    Q(bio__icontains=t) |
                    Q(skills__icontains=t)
                )

    online = request.GET.get('online', '').strip()
    if online == '1':
        qs = qs.filter(online_status=1)

    sort = request.GET.get('sort', 'rating')
    if sort == 'price_low':
        qs = qs.order_by('hourly_rate')
    elif sort == 'price_high':
        qs = qs.order_by('-hourly_rate')
    elif sort == 'sessions':
        qs = qs.order_by('-sessions_completed')
    else:
        qs = qs.order_by('-rating_avg')

    results = [format_mentor_row(m) for m in qs]
    return success_response(results)


@api_view(['GET'])
@permission_classes([AllowAny])
def mentor_detail(request, mentor_id):
    profile = MentorProfile.objects.select_related('user').filter(Q(user_id=mentor_id) | Q(id=mentor_id)).first()
    if not profile:
        return error_response('Mentor not found', status.HTTP_404_NOT_FOUND)

    actual_user_id = profile.user.id
    data = format_mentor_row(profile)
    data['bio'] = profile.bio or ''
    data['github_url'] = profile.github_url
    data['linkedin_url'] = profile.linkedin_url
    data['portfolio_url'] = profile.portfolio_url
    data['youtube_url'] = profile.youtube_url
    data['x_url'] = profile.x_url
    data['website_url'] = profile.website_url

    reviews = Review.objects.filter(mentor_id=actual_user_id).select_related('learner').order_by('-created_at')[:10]
    data['reviews'] = [
        {
            'rating': r.rating,
            'comment': r.comment or '',
            'created_at': r.created_at.isoformat() if r.created_at else None,
            'learner_name': r.learner.name,
        }
        for r in reviews
    ]

    exp = MentorExperience.objects.filter(user_id=actual_user_id).order_by('-start_date')
    data['experience'] = [
        {
            'id': e.id,
            'job_title': e.job_title,
            'company': e.company,
            'start_date': e.start_date,
            'end_date': e.end_date,
            'description': e.description,
            'sort_order': e.sort_order,
        }
        for e in exp
    ]

    proj = MentorProject.objects.filter(user_id=actual_user_id).order_by('sort_order', 'id')
    data['projects'] = [
        {
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'url': p.url,
            'sort_order': p.sort_order,
        }
        for p in proj
    ]

    edu = MentorEducation.objects.filter(user_id=actual_user_id).order_by('sort_order', 'id')
    data['education'] = [
        {
            'id': ed.id,
            'degree': ed.degree,
            'university': ed.university,
            'year': ed.year,
            'sort_order': ed.sort_order,
        }
        for ed in edu
    ]

    certs = MentorCertification.objects.filter(user_id=actual_user_id).order_by('sort_order', 'id')
    data['certifications'] = [
        {
            'id': c.id,
            'name': c.name,
            'issuer': c.issuer,
            'year': c.year,
            'sort_order': c.sort_order,
        }
        for c in certs
    ]

    awards = MentorAward.objects.filter(user_id=actual_user_id).order_by('sort_order', 'id')
    data['awards'] = [
        {
            'id': a.id,
            'title': a.title,
            'description': a.description,
            'year': a.year,
            'sort_order': a.sort_order,
        }
        for a in awards
    ]

    avail = MentorAvailability.objects.filter(user_id=actual_user_id).order_by('day_of_week', 'start_time')
    data['availability'] = [
        {
            'id': av.id,
            'day_of_week': av.day_of_week,
            'start_time': av.start_time,
            'end_time': av.end_time,
        }
        for av in avail
    ]

    return success_response(data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsMentor])
def update_own_profile(request):
    user = request.user
    profile, _ = MentorProfile.objects.get_or_create(user=user)
    data = request.data or {}

    if 'photo_url' in data:
        profile.photo_url = data.get('photo_url')
    if 'title' in data:
        profile.title = str(data.get('title', ''))
    if 'company' in data:
        profile.company = str(data.get('company', ''))
    if 'years_experience' in data:
        profile.years_experience = int(data.get('years_experience', 0) or 0)
    if 'location' in data:
        profile.location = str(data.get('location', ''))
    if 'languages' in data:
        langs = data.get('languages', '')
        if isinstance(langs, list):
            langs = ', '.join(langs)
        profile.languages = str(langs)
    if 'bio' in data:
        profile.bio = str(data.get('bio', ''))
    if 'skills' in data:
        skills = data.get('skills', '')
        if isinstance(skills, list):
            skills = ', '.join(skills)
        profile.skills = str(skills)
    if 'hourly_rate' in data:
        profile.hourly_rate = float(data.get('hourly_rate', 0.0) or 0.0)
    if 'github_url' in data:
        profile.github_url = data.get('github_url')
    if 'linkedin_url' in data:
        profile.linkedin_url = data.get('linkedin_url')
    if 'portfolio_url' in data:
        profile.portfolio_url = data.get('portfolio_url')
    if 'youtube_url' in data:
        profile.youtube_url = data.get('youtube_url')
    if 'x_url' in data:
        profile.x_url = data.get('x_url')
    if 'website_url' in data:
        profile.website_url = data.get('website_url')
    if 'online_status' in data:
        profile.online_status = 1 if data.get('online_status') else 0

    profile.save()
    return success_response({'message': 'Profile updated'})


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsMentor])
def set_online_status(request):
    user = request.user
    profile, _ = MentorProfile.objects.get_or_create(user=user)
    data = request.data or {}
    is_online = bool(data.get('online'))
    profile.online_status = 1 if is_online else 0
    profile.save()
    return success_response({'online': is_online})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMentor])
@parser_classes([MultiPartParser, FormParser])
def upload_photo(request):
    user = request.user
    if 'photo' not in request.FILES:
        return error_response('No photo uploaded, or the upload failed', status.HTTP_422_UNPROCESSABLE_ENTITY)

    photo = request.FILES['photo']
    if photo.size > 2 * 1024 * 1024:
        return error_response('Photo must be under 2MB', status.HTTP_422_UNPROCESSABLE_ENTITY)

    content_type = photo.content_type.lower()
    allowed_exts = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}
    if content_type not in allowed_exts:
        return error_response('Photo must be a JPEG, PNG, or WebP image', status.HTTP_422_UNPROCESSABLE_ENTITY)

    ext = allowed_exts[content_type]
    upload_dir = settings.MEDIA_ROOT / 'mentors'
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{user.id}_{int(time.time())}.{ext}"
    dest_path = upload_dir / filename

    # Remove any previous photo for this user
    for old in upload_dir.glob(f"{user.id}_*"):
        try:
            old.unlink()
        except OSError:
            pass

    with open(dest_path, 'wb+') as destination:
        for chunk in photo.chunks():
            destination.write(chunk)

    photo_url = f"/uploads/mentors/{filename}"
    profile, _ = MentorProfile.objects.get_or_create(user=user)
    profile.photo_url = photo_url
    profile.save()

    return success_response({'photo_url': photo_url})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_as_mentor(request):
    user = request.user
    if user.role == 'mentor':
        return error_response('You are already a mentor', status.HTTP_409_CONFLICT)
    if user.role != 'learner':
        return error_response('Only learner accounts can apply to become a mentor', status.HTTP_422_UNPROCESSABLE_ENTITY)

    data = request.data or {}
    title = str(data.get('title', '')).strip()
    bio = str(data.get('bio', '')).strip()
    skills = str(data.get('skills', '')).strip()
    try:
        rate = float(data.get('hourly_rate', 0))
    except (ValueError, TypeError):
        rate = 0.0

    if not title or not skills or rate <= 0:
        return error_response('title, skills, and hourly_rate are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    user.role = 'mentor'
    user.save()

    profile, _ = MentorProfile.objects.get_or_create(user=user)
    profile.title = title
    profile.bio = bio
    profile.skills = skills
    profile.hourly_rate = rate
    profile.github_url = data.get('github_url')
    profile.linkedin_url = data.get('linkedin_url')
    profile.approval_status = 'pending'
    profile.save()

    token = generate_jwt(user)
    return success_response({
        'message': 'Mentor application submitted — pending admin approval before you appear in search.',
        'token': token,
        'user': {
            'id': user.id,
            'name': user.name,
            'role': 'mentor',
        }
    })
