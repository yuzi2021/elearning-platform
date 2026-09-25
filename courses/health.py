"""Health endpoints for deployment readiness checks."""
import logging

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


logger = logging.getLogger(__name__)


@require_GET
def liveness(request):
    """Confirm that the Django process can serve HTTP without probing dependencies."""
    return JsonResponse({'status': 'ok'})


@require_GET
def healthcheck(request):
    """Report readiness of the database-backed core application."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        logger.exception('Database readiness check failed')
        return JsonResponse({'status': 'unhealthy', 'database': 'unavailable'}, status=503)

    return JsonResponse({'status': 'ok', 'database': 'ok'})
