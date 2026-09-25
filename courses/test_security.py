"""Permission, reliability, integration, and task tests added during hardening."""
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Course, Enrollment, Feedback, TeacherProfile, WeatherCache
from .forms import UserRegistrationForm
from .services import optional_cache_get
from .tasks import send_enrollment_email, send_feedback_email
from .tests import make_course, make_student, make_teacher


class AuthenticationHardeningTest(TestCase):
    def test_login_rejects_external_next_redirect(self):
        make_student(
            'redirect-student', password='StrongPass123!',
            email='redirect@example.com',
        )
        response = self.client.post(
            reverse('courses:login') + '?next=https://malicious.example/',
            {
                'email': 'redirect@example.com',
                'password': 'StrongPass123!',
            },
        )
        self.assertRedirects(response, reverse('courses:home'))

    @override_settings(ALLOW_INSTRUCTOR_REGISTRATION=False)
    def test_public_demo_registration_cannot_create_instructor(self):
        form = UserRegistrationForm(data={
            'username': 'public-instructor',
            'first_name': 'Demo',
            'last_name': 'Instructor',
            'email': 'public-instructor@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'user_type': 'teacher',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('user_type', form.errors)


class PermissionBoundaryTest(APITestCase):
    def setUp(self):
        self.teacher = make_teacher('boundary-teacher')
        self.other_teacher = make_teacher('other-teacher')
        self.student = make_student('boundary-student')
        self.course = make_course(self.teacher, title='Permission Design')

    def test_anonymous_profile_directory_is_rejected(self):
        response = self.client.get(reverse('student-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_instructor_cannot_enroll_as_learner(self):
        self.client.force_authenticate(self.other_teacher)
        response = self.client.post(
            reverse('api_course_enroll', kwargs={'pk': self.course.pk}), {}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Enrollment.objects.exists())

    def test_unenrolled_learner_cannot_leave_feedback(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            reverse('api_feedback_create', kwargs={'pk': self.course.pk}),
            {'rating': 4, 'comment': 'Not enrolled'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Feedback.objects.exists())

    def test_suspended_learner_cannot_leave_feedback(self):
        Enrollment.objects.create(course=self.course, student=self.student, is_active=False)
        self.client.force_authenticate(self.student)
        response = self.client.post(
            reverse('api_feedback_create', kwargs={'pk': self.course.pk}),
            {'rating': 4, 'comment': 'Suspended'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(CELERY_ENABLED=False)
    def test_enrolled_learner_can_leave_feedback(self):
        Enrollment.objects.create(course=self.course, student=self.student)
        self.client.force_authenticate(self.student)
        response = self.client.post(
            reverse('api_feedback_create', kwargs={'pk': self.course.pk}),
            {'rating': 4, 'comment': 'Useful course'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_non_owner_instructor_cannot_edit_course(self):
        self.client.force_login(self.other_teacher)
        response = self.client.post(
            reverse('courses:course_edit', kwargs={'pk': self.course.pk}),
            {'title': 'Changed', 'description': 'Unauthorized'},
        )
        self.assertRedirects(
            response, reverse('courses:course_detail', kwargs={'pk': self.course.pk})
        )
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, 'Permission Design')

    def test_course_chat_requires_active_course_access(self):
        url = reverse('courses:course_chat', kwargs={'pk': self.course.pk})
        anonymous = self.client.get(url)
        self.assertEqual(anonymous.status_code, 302)

        self.client.force_login(self.student)
        unenrolled = self.client.get(url)
        self.assertRedirects(
            unenrolled, reverse('courses:course_detail', kwargs={'pk': self.course.pk})
        )

        Enrollment.objects.create(course=self.course, student=self.student)
        enrolled = self.client.get(url)
        self.assertEqual(enrolled.status_code, 200)

    def test_public_course_page_does_not_list_learner_identity(self):
        self.student.first_name = 'PrivateLearnerName'
        self.student.save(update_fields=['first_name'])
        Enrollment.objects.create(course=self.course, student=self.student)
        self.client.logout()
        response = self.client.get(
            reverse('courses:course_detail', kwargs={'pk': self.course.pk})
        )
        self.assertNotContains(response, 'PrivateLearnerName')


class DatabaseIntegrityTest(TestCase):
    def test_database_rejects_out_of_range_feedback_rating(self):
        teacher = make_teacher('constraint-teacher')
        student = make_student('constraint-student')
        course = make_course(teacher)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Feedback.objects.create(
                course=course, student=student, rating=8, comment='Invalid'
            )

    def test_creating_teacher_profile_removes_student_role(self):
        user = make_student('role-switch')
        TeacherProfile.objects.create(user=user)
        self.assertFalse(hasattr(user, 'student_profile'))
        self.assertTrue(hasattr(user, 'teacher_profile'))


class BackgroundTaskTest(TestCase):
    def setUp(self):
        self.teacher = make_teacher('task-teacher')
        self.teacher.email = 'instructor@example.com'
        self.teacher.save(update_fields=['email'])
        self.student = make_student('task-student', email='learner@example.com')
        self.course = make_course(self.teacher, title='Async Systems')
        self.enrollment = Enrollment.objects.create(course=self.course, student=self.student)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_enrollment_email_task_sends_expected_notification(self):
        send_enrollment_email.run(self.enrollment.id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['instructor@example.com'])
        self.assertIn('Async Systems', mail.outbox[0].subject)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_feedback_email_task_sends_expected_notification(self):
        feedback = Feedback.objects.create(
            course=self.course, student=self.student, rating=5, comment='Clear material'
        )
        send_feedback_email.run(feedback.id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('5/5', mail.outbox[0].body)

    @patch('courses.tasks.send_mail', side_effect=RuntimeError('mail unavailable'))
    def test_task_failure_is_not_silently_reported_as_success(self, send_mail):
        with self.assertRaises(RuntimeError):
            send_enrollment_email.run(self.enrollment.id)


class ExternalIntegrationTest(APITestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch('courses.api.requests.get')
    def test_daily_quote_uses_application_cache(self, request_get):
        cache.set('daily_quote:v1', {
            'success': True, 'content': 'Cached quote', 'author': 'Demo',
            'source': 'ZenQuotes', 'cached': False,
        })
        response = self.client.get(reverse('api_daily_quote'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['cached'])
        request_get.assert_not_called()

    @patch('courses.services.cache.get', side_effect=ConnectionError)
    def test_cache_failure_degrades_to_a_miss(self, cache_get):
        self.assertIsNone(optional_cache_get('unavailable'))

    @patch('courses.api.requests.get', side_effect=ConnectionError)
    def test_weather_uses_stale_database_cache_on_api_failure(self, request_get):
        cached = WeatherCache.objects.create(
            city='Helsinki', temperature=2.5, weather_code=3,
            weather_description='Overcast',
        )
        WeatherCache.objects.filter(pk=cached.pk).update(
            fetched_at=timezone.now() - timedelta(hours=2)
        )
        response = self.client.get(reverse('api_weather'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['stale'])

    def test_invalid_status_limit_is_clamped_instead_of_crashing(self):
        response = self.client.get(reverse('api_status_list') + '?limit=not-a-number')
        self.assertEqual(response.status_code, 200)
