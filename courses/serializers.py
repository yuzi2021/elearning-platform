"""
Django REST Framework serializers for the application API.

"""
from rest_framework import serializers
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models import Count, Q
from .models import (
    Course, Enrollment, Feedback, StatusUpdate,
    StudentProfile, TeacherProfile
)


class CourseSerializer(serializers.ModelSerializer):
    """
    Serializer for the Course model.
    instructor_name and instructor_email are read-only — they are derived
    properties on the model (3NF), not stored fields.
    """
    enrollment_count = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description',
            'instructor_name', 'instructor_email',
            'created_at', 'updated_at',
            'enrollment_count', 'avg_rating'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'instructor_name', 'instructor_email'
        ]

    def get_enrollment_count(self, obj):
        annotated = getattr(obj, 'enrollment_count', None)
        return annotated if annotated is not None else obj.get_enrollment_count()

    def get_avg_rating(self, obj):
        annotated = getattr(obj, 'avg_rating', None)
        value = annotated if annotated is not None else obj.get_average_rating()
        return round(value, 1)


class EnrollmentSerializer(serializers.ModelSerializer):
    """
    Serializer for the Enrollment model.
    student_name and student_email are read-only — derived from the student FK
    via properties on the model. They are included so AJAX responses can
    display the student's name without an extra request.
    """
    course_title = serializers.CharField(source='course.title', read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id', 'course', 'course_title',
            'student_name', 'student_email',
            'enrolled_at', 'is_active'
        ]
        read_only_fields = [
            'id', 'enrolled_at',
            'student_name', 'student_email', 'course_title'
        ]


class FeedbackSerializer(serializers.ModelSerializer):
    """
    Serializer for the Feedback model.
    student_name and student_email are read-only — derived from the student FK.
    """
    course_title = serializers.CharField(source='course.title', read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    student_email = serializers.EmailField(source='student.email', read_only=True)

    class Meta:
        model = Feedback
        fields = [
            'id', 'course', 'course_title',
            'student_name', 'student_email',
            'rating', 'comment', 'created_at'
        ]
        read_only_fields = [
            'id', 'created_at',
            'student_name', 'student_email', 'course_title'
        ]


class StatusUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for the StatusUpdate model.
    author_name and author_email are read-only — derived from the author FK.
    """
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    author_email = serializers.EmailField(source='author.email', read_only=True)

    class Meta:
        model = StatusUpdate
        fields = ['id', 'author_name', 'author_email', 'content', 'created_at']
        read_only_fields = ['id', 'created_at', 'author_name', 'author_email']


# ============================================
# USER SERIALIZERS
# ============================================

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for Django's built-in User model.
    Includes derived user_type and nested profile_data.
    """
    user_type = serializers.SerializerMethodField()
    profile_data = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name',
            'date_joined', 'user_type', 'profile_data'
        ]
        read_only_fields = ['id', 'date_joined', 'user_type', 'profile_data']

    def get_user_type(self, obj):
        if hasattr(obj, 'teacher_profile'):
            return 'teacher'
        elif hasattr(obj, 'student_profile'):
            return 'student'
        return 'unknown'

    def get_profile_data(self, obj):
        if hasattr(obj, 'teacher_profile'):
            return TeacherProfileSerializer(obj.teacher_profile).data
        elif hasattr(obj, 'student_profile'):
            return StudentProfileSerializer(obj.student_profile).data
        return None


class PersistentMediaSerializerMixin:
    """Remove upload fields when persistent object storage is unavailable."""

    def get_fields(self):
        fields = super().get_fields()
        if not settings.MEDIA_UPLOADS_ENABLED:
            fields.pop('profile_picture', None)
        return fields


class StudentProfileSerializer(PersistentMediaSerializerMixin, serializers.ModelSerializer):
    """Serializer for StudentProfile, including user identity fields."""
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            'id', 'username', 'full_name',
            'organization', 'bio', 'profile_picture',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_full_name(self, obj):
        return obj.get_full_name()


class TeacherProfileSerializer(PersistentMediaSerializerMixin, serializers.ModelSerializer):
    """Serializer for TeacherProfile, including user identity and courses taught."""
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()
    courses_taught = serializers.SerializerMethodField()

    class Meta:
        model = TeacherProfile
        fields = [
            'id', 'username', 'full_name',
            'bio', 'profile_picture', 'qualifications',
            'subject_expertise', 'years_of_experience',
            'office_hours',
            'created_at', 'updated_at', 'courses_taught'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_courses_taught(self, obj):
        from .models import Course
        courses = Course.objects.filter(created_by=obj.user).annotate(
            enrollment_count=Count(
                'enrollments',
                filter=Q(enrollments__is_active=True),
            )
        )
        return [
            {
                'id': course.id,
                'title': course.title,
                'enrollment_count': course.enrollment_count
            }
            for course in courses
        ]
