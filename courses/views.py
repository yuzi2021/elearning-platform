"""
Traditional Django views - Server-side rendering.

"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Avg, Q
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from functools import wraps
from django.conf import settings
from .models import (
    Course,
    Enrollment,
    Feedback,
    StatusUpdate,
    CourseMaterial,
    Notification,
    StudentProfile,
    TeacherProfile
)
from .forms import (
    CourseForm,
    EnrollmentForm,
    FeedbackForm,
    StatusUpdateForm,
    UserRegistrationForm,
    StudentProfileForm,
    TeacherProfileForm,
    LoginForm,
    CourseMaterialForm
)


# ============================================
# HELPER FUNCTIONS
# ============================================

def is_teacher(user):
    """Return True if the user has a TeacherProfile."""
    return hasattr(user, 'teacher_profile')


def is_student(user):
    """Return True if the user has a StudentProfile."""
    return hasattr(user, 'student_profile')


def get_user_type(user):
    """Return 'teacher', 'student', or 'anonymous'."""
    if not user.is_authenticated:
        return 'anonymous'
    if is_teacher(user):
        return 'teacher'
    elif is_student(user):
        return 'student'
    return 'unknown'


def can_access_course(user, course):
    """Return whether a user may access enrolled course content and chat."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or course.created_by_id == user.id:
        return True
    return Enrollment.objects.filter(
        course=course,
        student=user,
        is_active=True,
    ).exists()


# ============================================
# CUSTOM DECORATORS
# ============================================

def teacher_required(view_func):
    """Require the user to be logged in AND have a teacher profile."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in to access this page.')
            from django.urls import reverse
            login_url = reverse('courses:login')
            next_url = request.get_full_path()
            return redirect(f'{login_url}?next={next_url}')
        if not is_teacher(request.user):
            messages.error(request, 'Only teachers can access this page.')
            return redirect('courses:home')
        return view_func(request, *args, **kwargs)
    return wrapper


def student_required(view_func):
    """Require the user to be logged in AND have a student profile."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please log in to access this page.')
            from django.urls import reverse
            login_url = reverse('courses:login')
            next_url = request.get_full_path()
            return redirect(f'{login_url}?next={next_url}')
        if not is_student(request.user):
            messages.error(request, 'Only students can access this page.')
            return redirect('courses:home')
        return view_func(request, *args, **kwargs)
    return wrapper


# ============================================
# PROFILE VIEW
# ============================================

@login_required
def profile_view(request):
    """
    Show the logged-in user's profile page.
    Teachers see their created courses; students see their enrolled courses.
    """
    user = request.user
    user_type = get_user_type(user)
    profile = None
    enrolled_courses = []
    created_courses = []
    courses_count = 0

    if user_type == 'teacher':
        profile = user.teacher_profile
        created_courses = Course.objects.filter(
            created_by=user
        ).order_by('-created_at')
        courses_count = created_courses.count()

    elif user_type == 'student':
        profile = user.student_profile
        # Use student FK directly — no email lookup needed
        enrollments = Enrollment.objects.filter(
            student=user,
            is_active=True
        ).select_related('course')
        enrolled_courses = [e.course for e in enrollments]
        courses_count = len(enrolled_courses)

    context = {
        'profile': profile,
        'user_type': user_type,
        'enrolled_courses': enrolled_courses,
        'created_courses': created_courses,
        'courses_count': courses_count,
    }
    return render(request, 'courses/profile.html', context)


# ============================================
# HOME VIEW
# ============================================

def home_view(request):
    """Role-aware landing page focused on the user's next useful action."""
    total_courses = Course.objects.count()
    total_enrollments = Enrollment.objects.filter(is_active=True).count()
    recent_courses = Course.objects.select_related('created_by')[:6]
    user_type = get_user_type(request.user)
    learner_enrollments = Enrollment.objects.none()
    instructor_courses = Course.objects.none()
    recent_notifications = Notification.objects.none()

    if user_type == 'student':
        learner_enrollments = Enrollment.objects.filter(
            student=request.user,
            is_active=True,
        ).select_related('course', 'course__created_by').prefetch_related(
            'course__materials'
        )[:6]
        recent_notifications = Notification.objects.filter(
            user=request.user
        ).select_related('course')[:4]
    elif user_type == 'teacher':
        instructor_courses = Course.objects.filter(
            created_by=request.user
        ).annotate(
            enrollment_count=Count(
                'enrollments',
                filter=Q(enrollments__is_active=True),
                distinct=True,
            ),
            material_count=Count('materials', distinct=True),
        )[:6]
        recent_notifications = Notification.objects.filter(
            user=request.user
        ).select_related('course')[:4]

    context = {
        'user_type': user_type,
        'total_courses': total_courses,
        'total_enrollments': total_enrollments,
        'recent_courses': recent_courses,
        'learner_enrollments': learner_enrollments,
        'instructor_courses': instructor_courses,
        'recent_notifications': recent_notifications,
    }
    return render(request, 'courses/home.html', context)


def api_docs_view(request):
    """Human-readable guide to representative REST endpoints."""
    return render(request, 'courses/api_docs.html')


# ============================================
# COURSE VIEWS
# ============================================

def course_list_view(request):
    """
    List all courses with enrollment count and average rating annotations.
    Teachers see a 'Create Course' button; students see 'Enroll' buttons.
    """
    courses = Course.objects.select_related('created_by').annotate(
        enrollment_count=Count(
            'enrollments',
            filter=Q(enrollments__is_active=True),
            distinct=True,
        ),
        avg_rating=Avg('feedbacks__rating')
    )

    can_create_course = False
    can_enroll = False
    user_type = 'anonymous'

    if request.user.is_authenticated:
        user_type = get_user_type(request.user)
        if user_type == 'teacher':
            can_create_course = True
        elif user_type == 'student':
            can_enroll = True

    context = {
        'courses': courses,
        'can_create_course': can_create_course,
        'can_enroll': can_enroll,
        'user_type': user_type,
    }
    return render(request, 'courses/course_list.html', context)


def course_detail_view(request, pk):
    """
    Show course details with role-specific actions:
    - Teachers: edit button, manage students button
    - Students: enroll button (if not enrolled), feedback form (if enrolled)
    - Anonymous: login prompt
    """
    course = get_object_or_404(
        Course.objects.select_related('created_by').prefetch_related('materials'),
        pk=pk,
    )
    enrollments = Enrollment.objects.none()
    feedbacks = course.feedbacks.select_related('student')[:10]
    enrollment_form = EnrollmentForm()
    feedback_form = FeedbackForm()

    can_edit = False
    can_enroll = False
    can_give_feedback = False
    is_enrolled = False
    has_course_access = can_access_course(request.user, course)

    if request.user.is_authenticated:
        if is_teacher(request.user):
            can_edit = course.created_by_id == request.user.id
            if can_edit:
                enrollments = course.enrollments.filter(
                    is_active=True
                ).select_related('student')[:10]
        elif is_student(request.user):
            can_enroll = True
            # Use student FK directly — no email lookup needed
            is_enrolled = course.enrollments.filter(
                student=request.user,
                is_active=True
            ).exists()
            if is_enrolled:
                can_enroll = False
                can_give_feedback = True

    context = {
        'course': course,
        'enrollments': enrollments,
        'feedbacks': feedbacks,
        'enrollment_form': enrollment_form,
        'feedback_form': feedback_form,
        'enrollment_count': course.get_enrollment_count(),
        'avg_rating': course.get_average_rating(),
        'can_edit': can_edit,
        'can_enroll': can_enroll,
        'can_give_feedback': can_give_feedback,
        'is_enrolled': is_enrolled,
        'has_course_access': has_course_access,
    }
    return render(request, 'courses/course_detail.html', context)


@teacher_required
def course_create_view(request):
    """
    Create a new course.
    created_by is set from request.user — instructor_name and instructor_email
    are derived properties on the model and no longer need to be set manually.
    """
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.created_by = request.user
            course.save()
            messages.success(request, f'Course "{course.title}" created successfully!')
            return redirect('courses:course_detail', pk=course.pk)
    else:
        form = CourseForm()

    context = {'form': form, 'title': 'Create New Course'}
    return render(request, 'courses/course_form.html', context)


@teacher_required
def course_edit_view(request, pk):
    """Edit an existing course. Only the course creator can edit it."""
    course = get_object_or_404(Course, pk=pk)

    if course.created_by != request.user:
        messages.error(request, 'You can only edit your own courses.')
        return redirect('courses:course_detail', pk=pk)

    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f'Course "{course.title}" updated successfully!')
            return redirect('courses:course_detail', pk=course.pk)
    else:
        form = CourseForm(instance=course)

    context = {
        'form': form,
        'title': f'Edit: {course.title}',
        'course': course
    }
    return render(request, 'courses/course_form.html', context)


@login_required
def course_chat_view(request, pk):
    """Chat room for a specific course. Loads the last 50 messages."""
    course = get_object_or_404(Course, pk=pk)
    if not can_access_course(request.user, course):
        messages.error(request, 'Enroll in this course to join its discussion.')
        return redirect('courses:course_detail', pk=pk)

    chat_messages = list(
        course.chat_messages.select_related('sender').order_by('-created_at')[:50]
    )
    chat_messages.reverse()

    context = {
        'course': course,
        'messages': chat_messages,
    }
    return render(request, 'courses/chat.html', context)


# ============================================
# AUTH VIEWS
# ============================================

def register(request):
    """
    Handle user registration.
    GET: Display empty registration form.
    POST: Validate, create user and the appropriate profile type.
    """
    if request.user.is_authenticated:
        messages.info(request, "You're already registered and logged in!")
        return redirect('courses:home')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            user_type = form.cleaned_data['user_type']
            messages.success(request, f'Account created successfully! Welcome, {user.username}!')
            if user_type == 'teacher':
                messages.info(request, 'Teacher profile created! You can edit it later.')
                return redirect('courses:home')
            else:
                messages.info(request, 'Student profile created! Start exploring courses.')
                return redirect('courses:course_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserRegistrationForm()

    return render(request, 'courses/register.html', {'form': form})


def user_login(request):
    """
    Handle email-based login.
    The email is passed to authenticate() as 'username' because that is
    Django's fixed kwarg name. Our custom EmailBackend resolves it correctly.
    Supports 'remember me' (2-week session) and redirect to next URL.
    """
    if request.user.is_authenticated:
        messages.info(request, f"You're already logged in as {request.user.username}.")
        return redirect('courses:home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data['remember_me']
            # Pass email as 'username' — EmailBackend treats it as an email lookup
            user = authenticate(request=request, username=email, password=password)
            if user is not None:
                login(request, user)
                request.session.set_expiry(1209600 if remember_me else 0)
                messages.success(request, f'Welcome back, {user.username}!')
                next_url = request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)
                return redirect('courses:home')
            else:
                messages.error(request, 'Invalid email or password. Please try again.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoginForm()

    return render(request, 'courses/login.html', {'form': form})


@login_required
@require_POST
def user_logout(request):
    """Log the user out and redirect to home."""
    username = request.user.username
    logout(request)
    messages.success(request, f'Goodbye, {username}! You have been logged out.')
    return redirect('courses:home')


# ============================================
# PROFILE EDIT VIEWS
# ============================================

@login_required
def edit_profile(request):
    """
    Allow the logged-in user to edit their profile.
    Renders the correct form based on whether they are a teacher or student.
    """
    user_type = get_user_type(request.user)

    if user_type == 'teacher':
        profile = request.user.teacher_profile
        FormClass = TeacherProfileForm
    elif user_type == 'student':
        profile = request.user.student_profile
        FormClass = StudentProfileForm
    else:
        messages.error(request, 'No profile found.')
        return redirect('courses:home')

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('courses:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = FormClass(instance=profile)

    context = {
        'form': form,
        'user_type': user_type,
    }
    return render(request, 'courses/profile.html', context)


# ============================================
# COURSE MATERIALS VIEWS
# ============================================

@teacher_required
def upload_material(request, course_pk):
    """
    Allow a teacher to upload a file to one of their courses.
    Only the course creator can upload to it.
    """
    course = get_object_or_404(Course, pk=course_pk)

    if not settings.MEDIA_UPLOADS_ENABLED:
        messages.info(
            request,
            'File uploads are disabled in this demo because persistent object storage is not configured.',
        )
        return redirect('courses:course_detail', pk=course_pk)

    if course.created_by != request.user:
        messages.error(request, 'You can only upload materials to your own courses.')
        return redirect('courses:course_detail', pk=course_pk)

    if request.method == 'POST':
        form = CourseMaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.course = course
            material.uploaded_by = request.user
            material.save()
            messages.success(request, f'"{material.title}" uploaded successfully.')
            return redirect('courses:course_detail', pk=course_pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CourseMaterialForm()

    context = {
        'course': course,
        'form': form,
    }
    return render(request, 'courses/upload_material.html', context)


@login_required
def download_material(request, pk):
    """Increment the download counter and redirect to the file URL."""
    material = get_object_or_404(CourseMaterial, pk=pk)
    if not can_access_course(request.user, material.course):
        messages.error(request, 'Enroll in this course to access its materials.')
        return redirect('courses:course_detail', pk=material.course_id)
    material.increment_download_count()
    return redirect(material.file.url)


@teacher_required
def delete_material(request, pk):
    """
    Permanently delete a course material file.
    Only the course creator can delete files from their course.
    Only accepts POST for security.
    """
    material = get_object_or_404(CourseMaterial, pk=pk)
    course = material.course

    if course.created_by != request.user:
        messages.error(request, 'You can only delete material from your own courses.')
        return redirect('courses:course_detail', pk=course.pk)

    if request.method == 'POST':
        title = material.title
        material.delete()
        messages.success(request, f'"{title}" deleted successfully.')
        return redirect('courses:course_detail', pk=course.pk)

    return redirect('courses:course_detail', pk=course.pk)


# ============================================
# NOTIFICATION VIEWS
# ============================================

@login_required
def notifications_list(request):
    """
    Show all notifications for the logged-in user.
    Reading the list does not mutate notification state.
    URL: /notifications/
    """
    notifications = Notification.objects.filter(user=request.user)
    unread_count = notifications.filter(is_read=False).count()

    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    return render(request, 'courses/notifications.html', context)


@login_required
@require_POST
def mark_notification_read(request, pk):
    """
    Mark a single notification as read and redirect to its related course.
    URL: /notifications/<id>/read/
    """
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_read()
    if notification.course:
        return redirect('courses:course_detail', pk=notification.course.pk)
    return redirect('courses:notifications_list')


@login_required
def mark_all_notifications_read(request):
    """
    Mark all unread notifications as read in one action.
    Only accepts POST for security.
    URL: /notifications/read-all/
    """
    if request.method == 'POST':
        Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
        messages.success(request, 'All notifications marked as read.')
    return redirect('courses:notifications_list')


# ============================================
# SEARCH VIEW
# ============================================

@teacher_required
def search_users(request):
    """
    Teachers can search for students and other teachers.
    Searches across username, email, first name, last name, and
    organisation (students) or subject expertise (teachers).
    URL: /search/?q=john&type=students
    """
    query = request.GET.get('q', '').strip()
    search_type = request.GET.get('type', 'students')
    results = []
    result_count = 0

    if query:
        if search_type == 'students':
            results = StudentProfile.objects.filter(
                Q(user__username__icontains=query) |
                Q(user__email__icontains=query) |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(organization__icontains=query)
            ).select_related('user')
        else:
            results = TeacherProfile.objects.filter(
                Q(user__username__icontains=query) |
                Q(user__email__icontains=query) |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(subject_expertise__icontains=query)
            ).select_related('user')
        result_count = results.count()

    context = {
        'query': query,
        'search_type': search_type,
        'results': results,
        'result_count': result_count,
    }
    return render(request, 'courses/search.html', context)


# ============================================
# STUDENT MANAGEMENT VIEWS
# ============================================

@teacher_required
def manage_course_students(request, pk):
    """
    Teacher views and manages all students enrolled in their course.
    URL: /courses/<id>/students/
    """
    course = get_object_or_404(Course, pk=pk)

    if course.created_by != request.user:
        messages.error(request, 'You can only manage students in your own courses.')
        return redirect('courses:course_detail', pk=pk)

    enrollments = Enrollment.objects.filter(
        course=course
    ).select_related('student')

    active_count = enrollments.filter(is_active=True).count()
    blocked_count = enrollments.filter(is_active=False).count()

    context = {
        'course': course,
        'enrollments': enrollments,
        'active_count': active_count,
        'blocked_count': blocked_count,
    }
    return render(request, 'courses/manage_students.html', context)


@teacher_required
def toggle_student_enrollment(request, pk):
    """
    Block or unblock a student from a course by toggling is_active.
    Only accepts POST to prevent accidental changes via URL.
    URL: /enrollments/<id>/toggle/
    """
    if request.method != 'POST':
        return redirect('courses:home')

    enrollment = get_object_or_404(Enrollment, pk=pk)
    course = enrollment.course

    if course.created_by != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('courses:course_detail', pk=course.pk)

    enrollment.is_active = not enrollment.is_active
    enrollment.save(update_fields=['is_active'])

    if enrollment.is_active:
        messages.success(
            request,
            f'{enrollment.student_name} has been re-activated on "{course.title}".'
        )
    else:
        messages.warning(
            request,
            f'{enrollment.student_name} has been blocked from "{course.title}".'
        )
    return redirect('courses:manage_students', pk=course.pk)


@teacher_required
def remove_student_enrollment(request, pk):
    """
    Permanently delete a student's enrollment record.
    Only accepts POST for security.
    URL: /enrollments/<id>/remove/
    """
    if request.method != 'POST':
        return redirect('courses:home')

    enrollment = get_object_or_404(Enrollment, pk=pk)
    course = enrollment.course

    if course.created_by != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('courses:course_detail', pk=course.pk)

    student_name = enrollment.student_name
    enrollment.delete()
    messages.success(
        request,
        f'{student_name} has been permanently removed from "{course.title}".'
    )
    return redirect('courses:manage_students', pk=course.pk)
