from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from ..models import (
    MentorExperience, MentorProject, MentorEducation,
    MentorCertification, MentorAward, MentorAvailability
)
from ..permissions import IsMentor
from ..helpers import error_response, success_response


# --- Experience ---
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMentor])
def add_experience(request):
    data = request.data or {}
    job_title = str(data.get('job_title') or data.get('role', '')).strip()
    company = str(data.get('company', '')).strip()
    start_date = str(data.get('start_date', '')).strip()
    if not start_date and data.get('duration'):
        dur = str(data.get('duration')).strip()
        start_date = dur.split('-')[0].strip() if '-' in dur else dur
    if not start_date:
        start_date = 'Present'

    if not job_title or not company:
        return error_response('job_title and company are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    exp = MentorExperience.objects.create(
        user=request.user,
        job_title=job_title,
        company=company,
        start_date=start_date,
        end_date=data.get('end_date'),
        description=data.get('description'),
        sort_order=int(data.get('sort_order', 0) or 0)
    )
    return success_response({'id': exp.id}, status_code=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsMentor])
def delete_experience(request, item_id):
    deleted, _ = MentorExperience.objects.filter(id=item_id, user=request.user).delete()
    if not deleted:
        return error_response('Not found', status.HTTP_404_NOT_FOUND)
    return success_response({'message': 'Deleted'})


# --- Projects ---
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMentor])
def add_project(request):
    data = request.data or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return error_response('name is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    proj = MentorProject.objects.create(
        user=request.user,
        name=name,
        description=data.get('description'),
        url=data.get('url'),
        sort_order=int(data.get('sort_order', 0) or 0)
    )
    return success_response({'id': proj.id}, status_code=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsMentor])
def delete_project(request, item_id):
    deleted, _ = MentorProject.objects.filter(id=item_id, user=request.user).delete()
    if not deleted:
        return error_response('Not found', status.HTTP_404_NOT_FOUND)
    return success_response({'message': 'Deleted'})


# --- Education ---
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMentor])
def add_education(request):
    data = request.data or {}
    degree = str(data.get('degree', '')).strip()
    university = str(data.get('university', '')).strip()
    if not degree or not university:
        return error_response('degree and university are required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    edu = MentorEducation.objects.create(
        user=request.user,
        degree=degree,
        university=university,
        year=data.get('year'),
        sort_order=int(data.get('sort_order', 0) or 0)
    )
    return success_response({'id': edu.id}, status_code=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsMentor])
def delete_education(request, item_id):
    deleted, _ = MentorEducation.objects.filter(id=item_id, user=request.user).delete()
    if not deleted:
        return error_response('Not found', status.HTTP_404_NOT_FOUND)
    return success_response({'message': 'Deleted'})


# --- Certifications ---
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMentor])
def add_certification(request):
    data = request.data or {}
    name = str(data.get('name') or data.get('title', '')).strip()
    if not name:
        return error_response('name or title is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    cert = MentorCertification.objects.create(
        user=request.user,
        name=name,
        issuer=data.get('issuer'),
        year=data.get('year'),
        sort_order=int(data.get('sort_order', 0) or 0)
    )
    return success_response({'id': cert.id}, status_code=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsMentor])
def delete_certification(request, item_id):
    deleted, _ = MentorCertification.objects.filter(id=item_id, user=request.user).delete()
    if not deleted:
        return error_response('Not found', status.HTTP_404_NOT_FOUND)
    return success_response({'message': 'Deleted'})


# --- Awards ---
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMentor])
def add_award(request):
    data = request.data or {}
    title = str(data.get('title', '')).strip()
    if not title:
        return error_response('title is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    award = MentorAward.objects.create(
        user=request.user,
        title=title,
        description=data.get('description'),
        year=data.get('year'),
        sort_order=int(data.get('sort_order', 0) or 0)
    )
    return success_response({'id': award.id}, status_code=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsMentor])
def delete_award(request, item_id):
    deleted, _ = MentorAward.objects.filter(id=item_id, user=request.user).delete()
    if not deleted:
        return error_response('Not found', status.HTTP_404_NOT_FOUND)
    return success_response({'message': 'Deleted'})


# --- Availability ---
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def set_availability(request):
    user = request.user

    if request.method == 'GET':
        avail = MentorAvailability.objects.filter(user=user).order_by('day_of_week', 'start_time')
        return success_response({
            'slots': [
                {
                    'id': av.id,
                    'day_of_week': av.day_of_week,
                    'start_time': av.start_time,
                    'end_time': av.end_time,
                }
                for av in avail
            ]
        })

    data = request.data or {}
    slots = data.get('slots', [])

    MentorAvailability.objects.filter(user=user).delete()

    created_objs = []
    for slot in slots:
        try:
            day = int(slot.get('day_of_week', 0))
            start_time = str(slot.get('start_time', '')).strip()
            end_time = str(slot.get('end_time', '')).strip()
            if start_time and end_time:
                created_objs.append(
                    MentorAvailability(user=user, day_of_week=day, start_time=start_time, end_time=end_time)
                )
        except (ValueError, TypeError):
            continue

    if created_objs:
        MentorAvailability.objects.bulk_create(created_objs)

    return success_response({
        'message': 'Availability updated',
        'count': len(created_objs),
    })
