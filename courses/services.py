"""Adapters for optional infrastructure used by the core request path."""
import logging

from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)


def dispatch_optional_task(task, *args, **kwargs):
    """Queue a Celery task when configured without failing the HTTP request."""
    if not settings.CELERY_ENABLED:
        logger.info('Skipping optional task %s: Celery is disabled', task.name)
        return False

    try:
        task.delay(*args, **kwargs)
    except Exception:
        logger.warning(
            'Could not queue optional task %s; core operation remains complete',
            task.name,
            exc_info=True,
        )
        return False
    return True


def optional_cache_get(key):
    """Read an optional cache without making Redis a core dependency."""
    try:
        return cache.get(key)
    except Exception:
        logger.warning('Optional cache read failed for key %s', key, exc_info=True)
        return None


def optional_cache_set(key, value, timeout):
    """Write an optional cache without failing the user-facing request."""
    try:
        cache.set(key, value, timeout=timeout)
        return True
    except Exception:
        logger.warning('Optional cache write failed for key %s', key, exc_info=True)
        return False
