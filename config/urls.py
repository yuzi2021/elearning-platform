"""
URL configuration for config project.

Main URL routing:
- /admin/ - Django admin interface
- / - Main application (courses app)
- /api/ - REST API endpoints
- /media/ - User uploaded files (development only)
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from courses.health import healthcheck, liveness

urlpatterns = [
    path('livez/', liveness, name='liveness'),
    path('healthz/', healthcheck, name='healthcheck'),
    path('readyz/', healthcheck, name='readiness'),
    path('admin/', admin.site.urls),
    path('', include('courses.urls')),
    path('api/', include('courses.api_urls')),
]

# Serve media files in development
# In production, use nginx or similar web server
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
