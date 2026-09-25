"""Best-effort email tasks kept outside the HTTP request path."""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def send_enrollment_email(enrollment_id):
    """Notify an instructor after a learner enrollment has committed."""
    from .models import Enrollment

    try:
        enrollment = Enrollment.objects.select_related(
            'course__created_by', 'student'
        ).get(id=enrollment_id)
    except Enrollment.DoesNotExist:
        logger.info('Enrollment email skipped; record id=%s no longer exists', enrollment_id)
        return

    course = enrollment.course
    if not course.instructor_email:
        logger.info('Enrollment email skipped; course id=%s has no recipient', course.id)
        return

    send_mail(
        f'New enrollment in {course.title}',
        (
            f'Hello {course.instructor_name},\n\n'
            f'{enrollment.student_name} enrolled in "{course.title}".\n'
            f'Total active enrollments: {course.get_enrollment_count()}\n\n'
            'eLearning Platform'
        ),
        settings.DEFAULT_FROM_EMAIL,
        [course.instructor_email],
        fail_silently=False,
    )
    logger.info('Enrollment email sent for enrollment_id=%s', enrollment_id)


@shared_task(ignore_result=True)
def send_feedback_email(feedback_id):
    """Notify an instructor after course feedback has committed."""
    from .models import Feedback

    try:
        feedback = Feedback.objects.select_related(
            'course__created_by', 'student'
        ).get(id=feedback_id)
    except Feedback.DoesNotExist:
        logger.info('Feedback email skipped; record id=%s no longer exists', feedback_id)
        return

    course = feedback.course
    if not course.instructor_email:
        logger.info('Feedback email skipped; course id=%s has no recipient', course.id)
        return

    send_mail(
        f'New feedback for {course.title}',
        (
            f'Hello {course.instructor_name},\n\n'
            f'{feedback.student_name} left a {feedback.rating}/5 rating for '
            f'"{course.title}".\n\nComment:\n{feedback.comment}\n\n'
            'eLearning Platform'
        ),
        settings.DEFAULT_FROM_EMAIL,
        [course.instructor_email],
        fail_silently=False,
    )
    logger.info('Feedback email sent for feedback_id=%s', feedback_id)
