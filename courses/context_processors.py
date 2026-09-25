"""
Context processors make variables available in ALL templates automatically.
This one adds the unread notification count to every page.
"""
from .models import Notification
from django.conf import settings


def notification_count(request):
    """
    Adds 'unread_notification_count' to every template context.
    Returns 0 for anonymous users.
    """
    if request.user.is_authenticated:
        count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        return {'unread_notification_count': count}

    return {'unread_notification_count': 0}


def deployment_capabilities(request):
    """Expose optional feature availability without probing external services."""
    return {
        'media_uploads_enabled': settings.MEDIA_UPLOADS_ENABLED,
        'distributed_realtime_enabled': bool(settings.REDIS_URL),
        'redis_cache_enabled': bool(settings.CACHE_URL),
    }
