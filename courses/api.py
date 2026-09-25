"""
REST API endpoints for AJAX interactions and external data.

"""

from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from rest_framework import status, viewsets, permissions
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.contrib.auth.models import User
from .models import (
    Course, Enrollment, Feedback, StatusUpdate,
    WeatherCache, StudentProfile, TeacherProfile
)
from .serializers import (
    CourseSerializer,
    EnrollmentSerializer,
    FeedbackSerializer,
    StatusUpdateSerializer,
    UserSerializer,
    StudentProfileSerializer,
    TeacherProfileSerializer
)
from .tasks import send_enrollment_email, send_feedback_email
from .services import dispatch_optional_task, optional_cache_get, optional_cache_set
import requests
import logging
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings


logger = logging.getLogger(__name__)


# ============================================
# ENROLLMENT API
# ============================================

@api_view(['POST'])
def api_course_enroll(request, pk):
    """
    AJAX endpoint for course enrollment.
    Requires authentication — the logged-in user is the student.
    No longer accepts student_name/student_email in the request body.

    POST /api/courses/<pk>/enroll/
    Returns 401 if not authenticated, 400 if already enrolled, 201 on success.
    """
    if not request.user.is_authenticated:
        return Response(
            {'success': False, 'message': 'You must be logged in to enroll.'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    if (
        not hasattr(request.user, 'student_profile')
        or hasattr(request.user, 'teacher_profile')
    ):
        return Response(
            {'success': False, 'message': 'Only learner accounts can enroll.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    course = get_object_or_404(Course, pk=pk)

    try:
        with transaction.atomic():
            enrollment = Enrollment.objects.create(
                course=course,
                student=request.user
            )
            transaction.on_commit(
                lambda: dispatch_optional_task(send_enrollment_email, enrollment.id)
            )

        serializer = EnrollmentSerializer(enrollment)
        return Response({
            'success': True,
            'message': f'Successfully enrolled in {course.title}!',
            'enrollment': serializer.data,
            'enrollment_count': course.get_enrollment_count()
        }, status=status.HTTP_201_CREATED)

    except IntegrityError:
        return Response(
            {'success': False, 'message': 'You are already enrolled in this course.'},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============================================
# FEEDBACK API
# ============================================

@api_view(['POST'])
def api_feedback_create(request, pk):
    """
    AJAX endpoint for submitting course feedback.
    Requires authentication — the logged-in user is the student.
    No longer accepts student_name/student_email in the request body.

    POST /api/courses/<pk>/feedback/
    Body: { "rating": 1-5, "comment": "..." }
    """
    if not request.user.is_authenticated:
        return Response(
            {'success': False, 'message': 'You must be logged in to leave feedback.'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    if (
        not hasattr(request.user, 'student_profile')
        or hasattr(request.user, 'teacher_profile')
    ):
        return Response(
            {'success': False, 'message': 'Only learner accounts can leave feedback.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    course = get_object_or_404(Course, pk=pk)
    if not Enrollment.objects.filter(
        course=course, student=request.user, is_active=True
    ).exists():
        return Response(
            {'success': False, 'message': 'Enroll in this course before leaving feedback.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    rating = request.data.get('rating')
    comment = request.data.get('comment')

    if not all([rating, comment]):
        return Response(
            {'success': False, 'message': 'Rating and comment are required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError()
    except (ValueError, TypeError):
        return Response(
            {'success': False, 'message': 'Rating must be a number between 1 and 5.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():
        feedback = Feedback.objects.create(
            course=course,
            student=request.user,
            rating=rating,
            comment=comment.strip(),
        )
        transaction.on_commit(
            lambda: dispatch_optional_task(send_feedback_email, feedback.id)
        )

    serializer = FeedbackSerializer(feedback)
    return Response({
        'success': True,
        'message': 'Thank you for your feedback!',
        'feedback': serializer.data,
        'avg_rating': course.get_average_rating()
    }, status=status.HTTP_201_CREATED)


# ============================================
# STATUS UPDATE API
# ============================================

@api_view(['POST'])
def api_status_create(request):
    """
    AJAX endpoint for posting a status update.
    Requires authentication — the logged-in user is the author.
    No longer accepts author_name/author_email in the request body.

    POST /api/status/
    Body: { "content": "..." }
    """
    if not request.user.is_authenticated:
        return Response(
            {'success': False, 'message': 'You must be logged in to post a status update.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    content = request.data.get('content')

    if not content:
        return Response(
            {'success': False, 'message': 'Content is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if len(content) > 500:
        return Response(
            {'success': False, 'message': 'Status update must be 500 characters or less.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    status_update = StatusUpdate.objects.create(
        author=request.user,
        content=content
    )

    serializer = StatusUpdateSerializer(status_update)
    return Response({
        'success': True,
        'message': 'Status posted!',
        'status_update': serializer.data
    }, status=status.HTTP_201_CREATED)


# ============================================
# COURSE LIST / DETAIL API
# ============================================

@api_view(['GET'])
def api_course_list(request):
    """
    Return a list of all courses, with optional title search.
    GET /api/courses/?search=python
    """
    courses = Course.objects.select_related('created_by').annotate(
        enrollment_count=Count(
            'enrollments',
            filter=Q(enrollments__is_active=True),
            distinct=True,
        ),
        avg_rating=Avg('feedbacks__rating'),
    )
    search = request.query_params.get('search', None)
    if search:
        courses = courses.filter(title__icontains=search)

    serializer = CourseSerializer(courses, many=True)
    return Response({
        'success': True,
        'count': courses.count(),
        'courses': serializer.data
    })


@api_view(['GET'])
def api_course_detail(request, pk):
    """
    Return details for a single course.
    GET /api/courses/<pk>/
    """
    course = get_object_or_404(
        Course.objects.select_related('created_by').annotate(
            enrollment_count=Count(
                'enrollments',
                filter=Q(enrollments__is_active=True),
                distinct=True,
            ),
            avg_rating=Avg('feedbacks__rating'),
        ),
        pk=pk,
    )
    serializer = CourseSerializer(course)
    return Response({
        'success': True,
        'course': serializer.data,
        'enrollment_count': course.get_enrollment_count(),
        'avg_rating': course.get_average_rating()
    })


# ============================================
# STATUS LIST API
# ============================================

@api_view(['GET'])
def api_status_list(request):
    """
    Return a list of recent status updates.
    GET /api/status/?limit=5
    Fixed: count() is now called before slicing the queryset.
    """
    try:
        limit = int(request.query_params.get('limit', 5))
    except (TypeError, ValueError):
        limit = 5
    limit = max(1, min(limit, 50))
    queryset = StatusUpdate.objects.select_related('author')
    total_count = queryset.count()  # Count before slicing
    updates = queryset[:limit]
    serializer = StatusUpdateSerializer(updates, many=True)
    return Response({
        'success': True,
        'count': total_count,
        'updates': serializer.data
    })


# ============================================
# EXTERNAL API: DAILY QUOTE
# ============================================

@require_http_methods(["GET"])
def api_get_daily_quote(request):
    """
    Fetch a random inspirational quote from ZenQuotes API.
    External API: https://zenquotes.io/api/random
    No authentication required.
    """
    cache_key = 'daily_quote:v1'
    cached = optional_cache_get(cache_key)
    if cached:
        return JsonResponse({**cached, 'cached': True})

    fallback = {
        'success': True,
        'content': 'Small, reliable steps make durable systems.',
        'author': 'eLearning Platform demo',
        'source': 'fallback',
        'cached': False,
    }

    try:
        response = requests.get(
            'https://zenquotes.io/api/random',
            timeout=settings.EXTERNAL_API_TIMEOUT,
        )

        if response.status_code != 200:
            return JsonResponse(fallback)

        data = response.json()

        if not data or len(data) == 0:
            return JsonResponse(fallback)

        quote = data[0]
        result = {
            'success': True,
            'content': str(quote.get('q', '')).strip(),
            'author': str(quote.get('a', 'Unknown')).strip(),
            'source': 'ZenQuotes',
            'cached': False,
        }
        if not result['content']:
            return JsonResponse(fallback)
        optional_cache_set(cache_key, result, timeout=60 * 60 * 24)
        return JsonResponse(result)

    except requests.exceptions.Timeout:
        logger.warning('Quote API timed out; serving local fallback')
        return JsonResponse(fallback)

    except (requests.exceptions.ConnectionError, ConnectionError):
        logger.warning('Quote API connection failed; serving local fallback')
        return JsonResponse(fallback)

    except (requests.RequestException, ValueError, TypeError, KeyError):
        logger.warning('Quote API response was unavailable or invalid', exc_info=True)
        return JsonResponse(fallback)


# ============================================
# EXTERNAL API: WEATHER
# ============================================

@require_http_methods(["GET"])
def api_get_weather(request):
    """
    Fetch current weather for Helsinki using Open-Meteo API.
    Caches results in WeatherCache to avoid excessive API calls.
    External API: https://api.open-meteo.com/
    No authentication required.
    """
    city = "Helsinki"

    cached = None
    try:
        # Check for fresh cached data
        try:
            cached = WeatherCache.objects.get(city=city)
            if not cached.is_stale():
                return JsonResponse({
                    'success': True,
                    'temperature': float(cached.temperature),
                    'description': cached.weather_description,
                    'cached': True,
                    'fetched_at': cached.fetched_at.isoformat()
                })
        except WeatherCache.DoesNotExist:
            pass

        # Fetch fresh data
        latitude = 60.1695
        longitude = 24.9354
        api_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={latitude}&longitude={longitude}"
            f"&current=temperature_2m,weather_code"
            f"&timezone=Europe/Helsinki"
        )

        response = requests.get(api_url, timeout=settings.EXTERNAL_API_TIMEOUT)

        if response.status_code != 200:
            raise requests.exceptions.RequestException(
                f'Weather API returned status {response.status_code}'
            )

        data = response.json()
        current = data.get('current', {})
        temperature = current.get('temperature_2m')
        weather_code = current.get('weather_code')

        if temperature is None or weather_code is None:
            raise ValueError('Invalid weather data received')

        description = WeatherCache.get_weather_description(weather_code)

        # Update or create cache entry
        WeatherCache.objects.update_or_create(
            city=city,
            defaults={
                'temperature': temperature,
                'weather_code': weather_code,
                'weather_description': description
            }
        )

        return JsonResponse({
            'success': True,
            'temperature': temperature,
            'description': description,
            'cached': False,
            'fetched_at': timezone.now().isoformat()
        })

    except (requests.RequestException, ConnectionError, ValueError, TypeError):
        logger.warning('Weather API unavailable; attempting cached fallback', exc_info=True)
        if cached is not None:
            return JsonResponse({
                'success': True,
                'temperature': float(cached.temperature),
                'description': cached.weather_description,
                'cached': True,
                'stale': True,
                'fetched_at': cached.fetched_at.isoformat(),
            })
        return JsonResponse({
            'success': False,
            'error': 'Weather is temporarily unavailable',
        }, status=503)


# ============================================
# EXTERNAL API: COURSE DIFFICULTY ANALYSER
# ============================================

def analyze_course_difficulty_ai(course_title, course_description):
    """
    Analyse course difficulty using the TextRazor NLP API.
    Falls back to keyword-based analysis if the API is unavailable.

    Args:
        course_title (str): Course title.
        course_description (str): Full course description.

    Returns:
        dict with keys: difficulty_score (1-5), difficulty_label,
        explanation, keywords, ai_powered, api_used.
    """
    if not settings.TEXTRAZOR_API_KEY:
        return analyze_course_difficulty_fallback(course_title, course_description)

    text = f"{course_title}. {course_description}"
    api_url = "https://api.textrazor.com/"
    headers = {"X-TextRazor-Key": settings.TEXTRAZOR_API_KEY}
    data = {
        "text": text,
        "extractors": "entities,topics,words",
        "languageOverride": "eng"
    }

    try:
        response = requests.post(
            api_url,
            headers=headers,
            data=data,
            timeout=settings.TEXTRAZOR_TIMEOUT,
        )

        if response.status_code != 200:
            return analyze_course_difficulty_fallback(course_title, course_description)

        result = response.json()

        if 'response' not in result:
            return analyze_course_difficulty_fallback(course_title, course_description)

        ai_topics = []
        ai_entities = []

        if 'topics' in result['response']:
            ai_topics = [t['label'] for t in result['response']['topics'][:10]]

        if 'entities' in result['response']:
            ai_entities = [e['entityId'] for e in result['response']['entities'][:10]]

        text_lower = text.lower()

        advanced_keywords = [
            'advanced', 'expert', 'professional', 'complex', 'sophisticated',
            'neural', 'algorithm', 'optimization', 'architecture', 'paradigm',
            'graduate', 'phd', 'research', 'cutting-edge', 'state-of-the-art'
        ]
        intermediate_keywords = [
            'intermediate', 'practical', 'development', 'programming',
            'application', 'implementation', 'project', 'framework',
            'build', 'create', 'working knowledge', 'hands-on'
        ]
        beginner_keywords = [
            'beginner', 'introduction', 'basics', 'fundamental', 'simple',
            'getting started', 'first', 'learn', 'start', 'basic',
            'intro', 'overview', 'primer', 'essentials', 'foundations'
        ]

        advanced_count = sum(1 for kw in advanced_keywords if kw in text_lower)
        intermediate_count = sum(1 for kw in intermediate_keywords if kw in text_lower)
        beginner_count = sum(1 for kw in beginner_keywords if kw in text_lower)

        has_prerequisites = any(phrase in text_lower for phrase in [
            'requires', 'prerequisite', 'must have', 'should know',
            'experience with', 'background in', 'familiarity with', 'assumes'
        ])
        no_prerequisites = any(phrase in text_lower for phrase in [
            'no experience', 'no prerequisites', 'no prior knowledge',
            'complete beginner', 'never coded', 'from scratch', 'zero to'
        ])

        if no_prerequisites or (beginner_count >= 3 and advanced_count == 0):
            score, label = 1, "Absolute Beginner"
        elif beginner_count >= 1 and advanced_count == 0 and intermediate_count <= 1:
            score, label = 2, "Beginner"
        elif intermediate_count >= 2 or (beginner_count >= 1 and intermediate_count >= 1):
            score, label = 3, "Intermediate"
        elif advanced_count >= 3 or (has_prerequisites and advanced_count >= 1):
            score, label = 4, "Advanced"
        elif advanced_count >= 5 or 'phd' in text_lower or 'graduate level' in text_lower:
            score, label = 5, "Expert"
        else:
            score, label = 2, "Beginner"

        if score >= 4:
            found_keywords = [kw for kw in advanced_keywords if kw in text_lower]
        elif score == 3:
            found_keywords = [kw for kw in intermediate_keywords if kw in text_lower]
        else:
            found_keywords = [kw for kw in beginner_keywords if kw in text_lower]

        explanation = f"TextRazor AI analysis suggests {label} level based on content analysis."
        if found_keywords:
            explanation += f" Key indicators: {', '.join(found_keywords[:3])}"
        if ai_topics:
            explanation += f" AI detected topics: {', '.join(ai_topics[:3])}"

        return {
            'difficulty_score': score,
            'difficulty_label': label,
            'explanation': explanation,
            'keywords': found_keywords[:5],
            'ai_powered': True,
            'api_used': 'TextRazor',
            'ai_topics': ai_topics[:5],
            'ai_entities': ai_entities[:5]
        }

    except requests.exceptions.Timeout:
        logger.warning('TextRazor timed out; using deterministic analysis')
        return analyze_course_difficulty_fallback(course_title, course_description)

    except (requests.RequestException, ValueError, TypeError, KeyError):
        logger.warning('TextRazor unavailable; using deterministic analysis', exc_info=True)
        return analyze_course_difficulty_fallback(course_title, course_description)


def analyze_course_difficulty_fallback(course_title, course_description):
    """
    Keyword-based difficulty analysis used when TextRazor is unavailable.
    Ensures the feature always works without an external API.
    """
    text = f"{course_title} {course_description}".lower()

    advanced_keywords = ['advanced', 'expert', 'professional', 'complex', 'sophisticated']
    intermediate_keywords = ['intermediate', 'practical', 'development', 'programming']
    beginner_keywords = ['beginner', 'introduction', 'basics', 'fundamental', 'simple']

    advanced_count = sum(1 for kw in advanced_keywords if kw in text)
    intermediate_count = sum(1 for kw in intermediate_keywords if kw in text)
    beginner_count = sum(1 for kw in beginner_keywords if kw in text)

    if advanced_count >= 2:
        score, label = 4, "Advanced"
        keywords = [kw for kw in advanced_keywords if kw in text]
    elif intermediate_count >= 2:
        score, label = 3, "Intermediate"
        keywords = [kw for kw in intermediate_keywords if kw in text]
    elif beginner_count >= 1:
        score, label = 2, "Beginner"
        keywords = [kw for kw in beginner_keywords if kw in text]
    else:
        score, label = 2, "Beginner"
        keywords = []

    return {
        'difficulty_score': score,
        'difficulty_label': label,
        'explanation': f"Keyword-based analysis suggests {label} level.",
        'keywords': keywords[:5],
        'ai_powered': False,
        'api_used': 'Fallback'
    }


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def api_analyze_course(request):
    """
    Analyse course difficulty using TextRazor AI.

    POST /api/course/analyze/
    Body: { "title": "...", "description": "..." }
    """
    if not hasattr(request.user, 'teacher_profile'):
        return Response(
            {'success': False, 'error': 'Only instructor accounts can analyse course drafts.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    title = request.data.get('title', '').strip()
    description = request.data.get('description', '').strip()

    if not title or not description:
        return Response(
            {'success': False, 'error': 'Both title and description are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if len(title) < 5:
        return Response(
            {'success': False, 'error': 'Title must be at least 5 characters'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if len(description) < 20:
        return Response(
            {'success': False, 'error': 'Description must be at least 20 characters'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        analysis = analyze_course_difficulty_ai(title, description)
        return Response({'success': True, **analysis})
    except Exception:
        logger.exception('Unexpected course-analysis failure')
        return Response(
            {'success': False, 'error': 'Analysis is temporarily unavailable.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================
# USER API VIEWSETS
# ============================================

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission: read access for everyone,
    write access only for the owner of the object.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user.is_authenticated:
            return False
        if isinstance(obj, User):
            return obj == request.user
        return obj.user == request.user


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for listing and retrieving User objects.
    Supports filtering by ?type=students or ?type=teachers.
    Includes a custom /api/users/me/ endpoint.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    http_method_names = ['get', 'patch', 'put', 'head', 'options']

    def get_queryset(self):
        queryset = User.objects.order_by('pk')
        if not (
            self.request.user.is_staff
            or hasattr(self.request.user, 'teacher_profile')
        ):
            queryset = queryset.filter(pk=self.request.user.pk)
        user_type = self.request.query_params.get('type', None)
        if user_type == 'students':
            queryset = queryset.filter(student_profile__isnull=False)
        elif user_type == 'teachers':
            queryset = queryset.filter(teacher_profile__isnull=False)
        return queryset

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Return the profile of the currently authenticated user."""
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class StudentProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for StudentProfile objects.
    Supports filtering by ?organization=<name>.
    """
    queryset = StudentProfile.objects.all().select_related('user')
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    http_method_names = ['get', 'patch', 'put', 'head', 'options']

    def get_queryset(self):
        queryset = StudentProfile.objects.all().select_related('user')
        if not (
            self.request.user.is_staff
            or hasattr(self.request.user, 'teacher_profile')
        ):
            queryset = queryset.filter(user=self.request.user)
        org = self.request.query_params.get('organization', None)
        if org:
            queryset = queryset.filter(organization__icontains=org)
        return queryset


class TeacherProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for TeacherProfile objects.
    Supports filtering by ?subject=<expertise>.
    """
    queryset = TeacherProfile.objects.all().select_related('user')
    serializer_class = TeacherProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    http_method_names = ['get', 'patch', 'put', 'head', 'options']

    def get_queryset(self):
        queryset = TeacherProfile.objects.all().select_related('user')
        subject = self.request.query_params.get('subject', None)
        if subject:
            queryset = queryset.filter(subject_expertise__icontains=subject)
        return queryset
