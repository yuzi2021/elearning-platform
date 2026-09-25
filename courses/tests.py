"""
Unit tests for the eLearning application.

Run tests:          python manage.py test
Run with coverage:  coverage run --source='.' manage.py test courses

"""

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from decimal import Decimal
from unittest.mock import patch
from .models import (
    Course, Enrollment, Feedback, StatusUpdate,
    CourseMaterial, Notification, StudentProfile, TeacherProfile
)
from .forms import CourseForm, EnrollmentForm, FeedbackForm


# ============================================
# HELPER
# ============================================

def make_student(username='student', password='pass', email=None):
    """Create a User with a StudentProfile (created by signal)."""
    kwargs = dict(username=username, password=password)
    if email:
        kwargs['email'] = email
    return User.objects.create_user(**kwargs)


def make_teacher(username='teacher', password='pass'):
    """Create a User with a TeacherProfile."""
    user = User.objects.create_user(username=username, password=password)
    TeacherProfile.objects.create(user=user)
    return user


def make_course(teacher, title='Test Course', description='Test Description'):
    """
    Create a Course owned by teacher.
    instructor_name and instructor_email are now derived properties —
    they are NOT passed as arguments.
    """
    return Course.objects.create(
        title=title,
        description=description,
        created_by=teacher
    )


# ============================================
# MODEL TESTS
# ============================================

class CourseModelTest(TestCase):
    """Test the Course model."""

    def setUp(self):
        self.teacher = make_teacher('testteacher')
        self.course = make_course(self.teacher, title='Test Course',
                                  description='Test Description')

    def test_course_creation(self):
        """Test that a course can be created and persisted."""
        self.assertEqual(self.course.title, 'Test Course')
        self.assertEqual(self.course.description, 'Test Description')
        self.assertIsInstance(self.course, Course)

    def test_course_str_representation(self):
        """Test the __str__() method of Course."""
        self.assertEqual(str(self.course), 'Test Course')

    def test_instructor_name_property(self):
        """instructor_name should be derived from created_by, not a stored field."""
        expected = self.teacher.get_full_name() or self.teacher.username
        self.assertEqual(self.course.instructor_name, expected)

    def test_instructor_email_property(self):
        """instructor_email should be derived from created_by."""
        self.assertEqual(self.course.instructor_email, self.teacher.email)

    def test_get_enrollment_count(self):
        """
        Test get_enrollment_count():
        1. Zero enrollments returns 0.
        2. Two enrollments returns 2.
        """
        self.assertEqual(self.course.get_enrollment_count(), 0)

        student1 = make_student('s1')
        student2 = make_student('s2')
        Enrollment.objects.create(course=self.course, student=student1)
        Enrollment.objects.create(course=self.course, student=student2)

        self.assertEqual(self.course.get_enrollment_count(), 2)

    def test_get_average_rating(self):
        """
        Test get_average_rating():
        - Returns 0 when no feedback.
        - (5 + 3) / 2 = 4.0 with two entries.
        """
        self.assertEqual(self.course.get_average_rating(), 0)

        student1 = make_student('r1')
        student2 = make_student('r2')
        Feedback.objects.create(course=self.course, student=student1,
                                rating=5, comment='Great!')
        Feedback.objects.create(course=self.course, student=student2,
                                rating=3, comment='Good')

        self.assertEqual(self.course.get_average_rating(), 4.0)


class EnrollmentModelTest(TestCase):
    """Test the Enrollment model."""

    def setUp(self):
        self.teacher = make_teacher()
        self.course = make_course(self.teacher)
        self.student = make_student()

    def test_enrollment_creation(self):
        """
        Test creating an enrollment:
        - student_name property returns correct value.
        - is_active defaults to True.
        - enrolled_at is set automatically.
        """
        enrollment = Enrollment.objects.create(
            course=self.course,
            student=self.student
        )

        # student_name is now a property derived from the FK
        self.assertEqual(enrollment.student_name,
                         self.student.get_full_name() or self.student.username)
        self.assertTrue(enrollment.is_active)
        self.assertIsNotNone(enrollment.enrolled_at)

    def test_unique_enrollment_constraint(self):
        """
        Test that the same student cannot enroll in the same course twice.
        unique_together = ['course', 'student']
        """
        Enrollment.objects.create(course=self.course, student=self.student)

        with self.assertRaises(Exception):  # IntegrityError
            Enrollment.objects.create(course=self.course, student=self.student)


class FeedbackModelTest(TestCase):
    """Test the Feedback model."""

    def setUp(self):
        self.teacher = make_teacher()
        self.course = make_course(self.teacher)

    def test_feedback_creation(self):
        """Test creating a 5-star feedback entry."""
        student = make_student()
        feedback = Feedback.objects.create(
            course=self.course,
            student=student,
            rating=5,
            comment='Excellent!'
        )
        self.assertEqual(feedback.rating, 5)
        self.assertEqual(feedback.comment, 'Excellent!')

    def test_rating_validation(self):
        """
        Test that rating validators (MinValueValidator(1), MaxValueValidator(5))
        accept 1-5 and reject values outside that range.
        """
        # Valid ratings 1–5 should all pass full_clean()
        for i, rating in enumerate([1, 2, 3, 4, 5]):
            student = make_student(f'ratingtest{i}')
            feedback = Feedback(
                course=self.course,
                student=student,
                rating=rating,
                comment='Test'
            )
            feedback.full_clean()  # Should NOT raise
            feedback.save()

        # Rating of 10 should fail
        bad_student = make_student('badrating')
        invalid_feedback = Feedback(
            course=self.course,
            student=bad_student,
            rating=10,
            comment='Test'
        )
        with self.assertRaises(ValidationError):
            invalid_feedback.full_clean()


class NotificationModelTest(TestCase):
    """Test the Notification model."""

    def setUp(self):
        self.user = make_student('testuser')
        self.teacher = make_teacher()
        self.course = make_course(self.teacher)

    def test_notification_creation(self):
        """Test creating a notification — defaults to is_read=False."""
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.ENROLLMENT,
            message='Test notification',
            course=self.course
        )
        self.assertEqual(notification.user, self.user)
        self.assertFalse(notification.is_read)

    def test_mark_as_read(self):
        """Test mark_as_read() flips is_read from False to True."""
        notification = Notification.objects.create(
            user=self.user,
            notification_type=Notification.NEW_MATERIAL,
            message='New material added'
        )
        self.assertFalse(notification.is_read)
        notification.mark_as_read()
        self.assertTrue(notification.is_read)


# ============================================
# FORM TESTS
# ============================================

class CourseFormTest(TestCase):
    """Test the CourseForm."""

    def test_valid_form(self):
        """
        Only title and description are needed — instructor fields were removed
        because they are now derived properties on the model.
        """
        form = CourseForm(data={
            'title': 'Test Course',
            'description': 'Test Description'
        })
        self.assertTrue(form.is_valid())

    def test_required_fields(self):
        """Empty form should fail with errors on title and description."""
        form = CourseForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
        self.assertIn('description', form.errors)

    def test_missing_description(self):
        """Form without description should be invalid."""
        form = CourseForm(data={'title': 'Title only'})
        self.assertFalse(form.is_valid())
        self.assertIn('description', form.errors)


class EnrollmentFormTest(TestCase):
    """
    Test the EnrollmentForm.
    The form has no fields — student is set from request.user in the view.
    An empty submission is therefore VALID.
    """

    def test_empty_form_is_valid(self):
        """
        EnrollmentForm has fields=[] so an empty POST is always valid.
        The student FK is assigned in the view, not via the form.
        """
        form = EnrollmentForm(data={})
        self.assertTrue(form.is_valid())


class FeedbackFormTest(TestCase):
    """
    Test the FeedbackForm.
    student_name and student_email were removed — only rating and comment
    are collected from the user.
    """

    def test_valid_feedback(self):
        """Valid rating and comment should pass."""
        form = FeedbackForm(data={'rating': 5, 'comment': 'Great course!'})
        self.assertTrue(form.is_valid())

    def test_missing_comment(self):
        """Comment is required — form without it should be invalid."""
        form = FeedbackForm(data={'rating': 5})
        self.assertFalse(form.is_valid())
        self.assertIn('comment', form.errors)

    def test_missing_rating(self):
        """Rating is required — form without it should be invalid."""
        form = FeedbackForm(data={'comment': 'Good'})
        self.assertFalse(form.is_valid())
        self.assertIn('rating', form.errors)

    def test_invalid_rating(self):
        """
        Rating must be a valid choice (1–5).
        A value of 6 should fail form validation.
        """
        form = FeedbackForm(data={'rating': 6, 'comment': 'Test'})
        self.assertFalse(form.is_valid())


# ============================================
# VIEW TESTS
# ============================================

class HomeViewTest(TestCase):
    """Test the home page view."""

    def test_home_page_loads(self):
        """Home page returns 200 and uses the correct template."""
        response = self.client.get(reverse('courses:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/home.html')

    def test_home_page_shows_courses(self):
        """Home page displays course titles."""
        teacher = make_teacher('t')
        make_course(teacher, title='Test Course')
        response = self.client.get(reverse('courses:home'))
        self.assertContains(response, 'Test Course')


class CourseListViewTest(TestCase):
    """Test the course list view."""

    def test_course_list_loads(self):
        response = self.client.get(reverse('courses:course_list'))
        self.assertEqual(response.status_code, 200)

    def test_empty_course_list(self):
        response = self.client.get(reverse('courses:course_list'))
        self.assertEqual(len(response.context['courses']), 0)


class CourseDetailViewTest(TestCase):
    """Test the course detail view."""

    def setUp(self):
        self.teacher = make_teacher()
        self.course = make_course(self.teacher, title='Detail Test Course')

    def test_course_detail_loads(self):
        response = self.client.get(
            reverse('courses:course_detail', kwargs={'pk': self.course.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Test Course')

    def test_course_detail_shows_materials(self):
        """Course materials are displayed to an authorized course owner."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        test_file = SimpleUploadedFile(
            'test.pdf', b'file_content', content_type='application/pdf'
        )
        CourseMaterial.objects.create(
            course=self.course,
            title='Test Material',
            file=test_file,
            uploaded_by=self.teacher
        )
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse('courses:course_detail', kwargs={'pk': self.course.pk})
        )
        self.assertContains(response, 'Test Material')


class AuthenticationViewTest(TestCase):
    """Test login/logout views."""

    def setUp(self):
        # Email is required — login is now email-based via EmailBackend
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@test.com',
            password='testpass123'
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse('courses:login'))
        self.assertEqual(response.status_code, 200)

    def test_login_success(self):
        """Successful login with email + password redirects (302)."""
        response = self.client.post(reverse('courses:login'), {
            'email': 'testuser@test.com',
            'password': 'testpass123',
            'remember_me': False
        })
        self.assertEqual(response.status_code, 302)

    def test_login_failure(self):
        """Wrong password stays on login page (200)."""
        response = self.client.post(reverse('courses:login'), {
            'email': 'testuser@test.com',
            'password': 'wrongpassword',
            'remember_me': False
        })
        self.assertEqual(response.status_code, 200)


class ProfileViewTest(TestCase):
    """Test profile views."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_profile_page_loads(self):
        response = self.client.get(reverse('courses:profile'))
        self.assertEqual(response.status_code, 200)


class CourseCreateViewTest(TestCase):
    """Test course creation view."""

    def setUp(self):
        self.teacher = make_teacher()
        self.client.login(username='teacher', password='pass')

    def test_create_course_page_loads(self):
        response = self.client.get(reverse('courses:course_create'))
        self.assertEqual(response.status_code, 200)

    def test_create_course_post(self):
        """POST valid data creates a course and redirects."""
        response = self.client.post(reverse('courses:course_create'), {
            'title': 'New Course',
            'description': 'A great course'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Course.objects.filter(title='New Course').exists())


class NotificationViewTest(TestCase):
    """Test notification views."""

    def setUp(self):
        self.user = make_student('notifuser')
        self.client.login(username='notifuser', password='pass')
        self.teacher = make_teacher()
        self.course = make_course(self.teacher)
        Notification.objects.create(
            user=self.user,
            notification_type=Notification.ENROLLMENT,
            message='Test notification',
            course=self.course
        )

    def test_notifications_list_loads(self):
        response = self.client.get(reverse('courses:notifications_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test notification')

    def test_mark_all_notifications_read(self):
        response = self.client.post(reverse('courses:mark_all_notifications_read'))
        self.assertEqual(response.status_code, 302)
        notif = Notification.objects.get(user=self.user)
        self.assertTrue(notif.is_read)


class SearchViewTest(TestCase):
    """Test search functionality (teacher-only)."""

    def setUp(self):
        self.teacher = make_teacher('searchteacher')
        self.teacher.teacher_profile.subject_expertise = 'Python, Django'
        self.teacher.teacher_profile.save()
        self.client.login(username='searchteacher', password='pass')

        self.student = make_student('searchstudent')
        self.student.student_profile.organization = 'Test University'
        self.student.student_profile.save()

    def test_search_page_loads(self):
        response = self.client.get(reverse('courses:search_users'))
        self.assertEqual(response.status_code, 200)

    def test_search_students(self):
        response = self.client.get(
            reverse('courses:search_users') + '?q=searchstudent&type=students'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'searchstudent')

    def test_search_teachers(self):
        response = self.client.get(
            reverse('courses:search_users') + '?q=Python&type=teachers'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'searchteacher')


class MaterialUploadViewTest(TestCase):
    """Test material upload functionality."""

    def setUp(self):
        self.teacher = make_teacher('matteacher')
        self.client.login(username='matteacher', password='pass')
        self.course = make_course(self.teacher, title='Material Course')

    def test_upload_material_page_loads(self):
        response = self.client.get(
            reverse('courses:upload_material', kwargs={'course_pk': self.course.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add a resource')


class ManageStudentsViewTest(TestCase):
    """Test student management views."""

    def setUp(self):
        self.teacher = make_teacher('mgmtteacher')
        self.client.login(username='mgmtteacher', password='pass')
        self.course = make_course(self.teacher, title='Management Course')

        # Enrollment now uses the student FK, not name/email strings
        self.student = make_student('managedstudent')
        self.student.first_name = 'Test'
        self.student.last_name = 'Student'
        self.student.save()

        self.enrollment = Enrollment.objects.create(
            course=self.course,
            student=self.student
        )

    def test_manage_students_page_loads(self):
        """Manage students page loads and shows the student's name."""
        response = self.client.get(
            reverse('courses:manage_students', kwargs={'pk': self.course.pk})
        )
        self.assertEqual(response.status_code, 200)
        # student_name is a property — should still appear in the template
        self.assertContains(response, 'Test Student')

    def test_toggle_student_enrollment(self):
        """Toggling a student's enrollment flips is_active."""
        response = self.client.post(
            reverse('courses:toggle_enrollment', kwargs={'pk': self.enrollment.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.enrollment.refresh_from_db()
        self.assertFalse(self.enrollment.is_active)


class HomePageTest(TestCase):
    """Test home page with different user scenarios."""

    def test_home_anonymous_user(self):
        response = self.client.get(reverse('courses:home'))
        self.assertEqual(response.status_code, 200)

    def test_home_logged_in_student(self):
        student = make_student('homestudent')
        self.client.login(username='homestudent', password='pass')
        response = self.client.get(reverse('courses:home'))
        self.assertEqual(response.status_code, 200)

    def test_home_logged_in_teacher(self):
        teacher = make_teacher('hometeacher')
        self.client.login(username='hometeacher', password='pass')
        response = self.client.get(reverse('courses:home'))
        self.assertEqual(response.status_code, 200)


# ============================================
# API TESTS
# ============================================

from rest_framework.test import APITestCase
from rest_framework import status as http_status


class UserAPITest(APITestCase):
    """Test the User API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@test.com',
            password='testpass123',
            first_name='API',
            last_name='User'
        )

    def test_list_users(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('user-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)

    def test_get_user_detail(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('user-detail', kwargs={'pk': self.user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'apiuser')

    def test_get_current_user(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('user-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'apiuser')

    def test_me_endpoint_requires_authentication(self):
        url = reverse('user-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


class StudentProfileAPITest(APITestCase):
    """Test the StudentProfile API endpoints."""

    def setUp(self):
        self.student = make_student('apistudent')
        self.profile = self.student.student_profile
        self.profile.organization = 'University'
        self.profile.bio = 'Test bio'
        self.profile.save()

    def test_list_students(self):
        self.client.force_authenticate(user=self.student)
        url = reverse('student-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_filter_students_by_organization(self):
        self.client.force_authenticate(user=self.student)
        url = reverse('student-list') + '?organization=University'
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)

    def test_update_own_profile(self):
        self.client.force_authenticate(user=self.student)
        url = reverse('student-detail', kwargs={'pk': self.profile.pk})
        response = self.client.patch(url, {'bio': 'Updated bio'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, 'Updated bio')

    def test_cannot_update_other_profile(self):
        other = make_student('otherstudent')
        self.client.force_authenticate(user=self.student)
        url = reverse('student-detail', kwargs={'pk': other.student_profile.pk})
        response = self.client.patch(url, {'bio': 'Hacked!'})
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)


class TeacherProfileAPITest(APITestCase):
    """Test the TeacherProfile API endpoints."""

    def setUp(self):
        self.teacher = make_teacher('apiteacher')
        self.profile = self.teacher.teacher_profile
        self.profile.subject_expertise = 'Python, Django'
        self.profile.years_of_experience = 5
        self.profile.save()

    def test_list_teachers(self):
        self.client.force_authenticate(user=self.teacher)
        url = reverse('teacher-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_filter_teachers_by_subject(self):
        self.client.force_authenticate(user=self.teacher)
        url = reverse('teacher-list') + '?subject=Python'
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)

    def test_teacher_courses_included(self):
        """courses_taught appears in the teacher's API response."""
        make_course(self.teacher, title='Python Course')
        self.client.force_authenticate(user=self.teacher)
        url = reverse('teacher-detail', kwargs={'pk': self.profile.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('courses_taught', response.data)
        self.assertEqual(len(response.data['courses_taught']), 1)


class DeploymentResilienceTest(APITestCase):
    """Core workflows remain available when optional infrastructure is absent."""

    def setUp(self):
        self.teacher = make_teacher('resilience-teacher')
        self.course = make_course(self.teacher, title='Reliable Systems')
        self.student = make_student(
            'resilience-student', email='resilience@example.com'
        )

    def test_healthcheck_confirms_database_readiness(self):
        response = self.client.get(reverse('healthcheck'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'database': 'ok'})

    @patch('courses.health.connection.cursor')
    def test_liveness_does_not_require_database(self, database_cursor):
        response = self.client.get(reverse('liveness'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        database_cursor.assert_not_called()

    @patch('courses.health.connection.cursor', side_effect=ConnectionError)
    def test_healthcheck_reports_database_failure(self, database_cursor):
        response = self.client.get(reverse('readiness'))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {'status': 'unhealthy', 'database': 'unavailable'},
        )
        database_cursor.assert_called_once_with()

    @override_settings(CELERY_ENABLED=False)
    @patch('courses.tasks.send_enrollment_email.delay')
    def test_enrollment_succeeds_when_celery_is_disabled(self, email_delay):
        self.client.force_authenticate(user=self.student)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('api_course_enroll', kwargs={'pk': self.course.pk}),
                {},
                format='json',
            )

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertTrue(
            Enrollment.objects.filter(course=self.course, student=self.student).exists()
        )
        email_delay.assert_not_called()

    @override_settings(CELERY_ENABLED=True)
    @patch('courses.tasks.send_feedback_email.delay', side_effect=ConnectionError)
    def test_feedback_succeeds_when_celery_broker_is_unavailable(self, delay):
        self.client.force_authenticate(user=self.student)
        Enrollment.objects.create(course=self.course, student=self.student)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('api_feedback_create', kwargs={'pk': self.course.pk}),
                {'rating': 5, 'comment': 'The core write survives.'},
                format='json',
            )

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertTrue(
            Feedback.objects.filter(course=self.course, student=self.student).exists()
        )
        delay.assert_called_once()

    @override_settings(MEDIA_UPLOADS_ENABLED=False)
    def test_material_upload_redirects_when_persistent_storage_is_disabled(self):
        self.client.force_login(self.teacher)

        response = self.client.get(
            reverse('courses:upload_material', kwargs={'course_pk': self.course.pk})
        )

        self.assertRedirects(
            response,
            reverse('courses:course_detail', kwargs={'pk': self.course.pk}),
        )
        self.assertFalse(CourseMaterial.objects.exists())

    @override_settings(MEDIA_UPLOADS_ENABLED=False)
    def test_profile_api_omits_media_field_when_storage_is_disabled(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get(
            reverse('student-detail', kwargs={'pk': self.student.student_profile.pk})
        )

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertNotIn('profile_picture', response.data)

    @patch('courses.api.requests.get', side_effect=ConnectionError)
    def test_quote_has_local_fallback(self, request_get):
        response = self.client.get(reverse('api_daily_quote'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['source'], 'fallback')
