from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import status
from ..models import SitePage
from ..permissions import IsSuperAdmin
from ..helpers import error_response, success_response

VALID_SLUGS = ('privacy', 'terms', 'help', 'contact')


@api_view(['GET'])
@permission_classes([AllowAny])
def get_page(request, slug):
    if slug not in VALID_SLUGS:
        return error_response('Unknown page', status.HTTP_404_NOT_FOUND)

    page = SitePage.objects.filter(slug=slug).first()
    if not page:
        return error_response('Page not found', status.HTTP_404_NOT_FOUND)

    return success_response({
        'slug': page.slug,
        'title': page.title,
        'content_html': page.content_html,
        'updated_at': page.updated_at.isoformat() if page.updated_at else None,
    })


@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def list_pages(request):
    pages = SitePage.objects.all().order_by('slug')
    results = [
        {
            'slug': p.slug,
            'title': p.title,
            'content_html': p.content_html,
            'updated_at': p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in pages
    ]
    return success_response(results)


@api_view(['PUT'])
@permission_classes([IsSuperAdmin])
def update_page(request, slug):
    if slug not in VALID_SLUGS:
        return error_response('Unknown page', status.HTTP_404_NOT_FOUND)

    data = request.data or {}
    title = str(data.get('title', '')).strip()
    content = str(data.get('content_html', ''))

    if not title:
        return error_response('Title is required', status.HTTP_422_UNPROCESSABLE_ENTITY)

    page, _ = SitePage.objects.get_or_create(slug=slug)
    page.title = title
    page.content_html = content
    page.save()

    return success_response({'message': 'Page updated'})
