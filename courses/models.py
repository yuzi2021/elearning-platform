"""
Course management models for the eLearning platform.

Database design follows Third Normal Form (3NF):
- 1NF: All fields are atomic, no repeating groups.
- 2NF: No partial dependencies — every non-key field depends on the whole primary key.
- 3NF: No transitive dependencies — instructor info is derived from the created_by FK
  rather than stored as separate fields, and student identity is stored as a FK to User
  rather than duplicated as name/email strings across Enrollment, Feedback, StatusUpdate,
  and ChatMessage tables.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import os
from django.core.exceptions import ValidationError


# ==============================================================================
# COURSE
# ==============================================================================

class Course(models.Model):
    """
    A course created by a teacher.

    3NF note: instructor_name and instructor_email are NOT stored as separate
    database fields. They were redundant because the same data is already
    accessible via the created_by FK. Storing them separately would violate 3NF
    (transitive dependency: course -> created_by -> name/email).
    They are exposed as read-only properties for template compatibility.
    """
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_courses',
        help_text='Teacher who created this course'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def instructor_name(self):
        """Derived from created_by — not stored (3NF)."""
        if self.created_by:
            return self.created_by.get_full_name() or self.created_by.username
        return 'Unknown'

    @property
    def instructor_email(self):
        """Derived from created_by — not stored (3NF)."""
        if self.created_by:
            return self.created_by.email
        return ''

    def get_enrollment_count(self):
        """Return the number of active enrollments for this course."""
        return self.enrollments.filter(is_active=True).count()

    def get_average_rating(self):
        """Return the average rating from all feedback, or 0 if none."""
        annotated = getattr(self, 'avg_rating', None)
        if annotated is not None:
            return annotated
        return self.feedbacks.aggregate(value=models.Avg('rating'))['value'] or 0


# ==============================================================================
# ENROLLMENT
# ==============================================================================

class Enrollment(models.Model):
    """
    Records a student's enrolment in a course.

    3NF note: Previously stored student_name and student_email as plain text,
    duplicating data already present on the User model. Replaced with a FK to
    User for referential integrity and to eliminate the duplication.
    student_name and student_email are exposed as properties for template
    compatibility without requiring template changes.
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='enrollments',
        help_text='The student enrolled in this course'
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-enrolled_at']
        unique_together = ['course', 'student']  # One enrolment per student per course

    def __str__(self):
        return f"{self.student.get_full_name() or self.student.username} - {self.course.title}"

    @property
    def student_name(self):
        """Convenience property so templates require no changes."""
        return self.student.get_full_name() or self.student.username

    @property
    def student_email(self):
        """Convenience property so templates require no changes."""
        return self.student.email


# ==============================================================================
# FEEDBACK
# ==============================================================================

class Feedback(models.Model):
    """
    Course feedback submitted by a student.

    3NF note: Previously stored student_name and student_email as plain text.
    Replaced with a FK to User. Properties maintain template compatibility.
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='feedbacks'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='feedbacks',
        help_text='The student who left this feedback'
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name='feedback_rating_between_1_and_5',
            ),
        ]

    def __str__(self):
        name = self.student.get_full_name() or self.student.username
        return f"{name} - {self.course.title} ({self.rating}/5)"

    @property
    def student_name(self):
        """Convenience property so templates require no changes."""
        return self.student.get_full_name() or self.student.username

    @property
    def student_email(self):
        """Convenience property so templates require no changes."""
        return self.student.email


# ==============================================================================
# STATUS UPDATE
# ==============================================================================

class StatusUpdate(models.Model):
    """
    A status update posted by any user to their home page.

    3NF note: Previously stored author_name and author_email as plain text.
    Replaced with a FK to User. Properties maintain template compatibility.
    """
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='status_updates',
        help_text='User who posted this update'
    )
    content = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author.username}: {self.content[:50]}"

    @property
    def author_name(self):
        """Convenience property so templates require no changes."""
        return self.author.get_full_name() or self.author.username

    @property
    def author_email(self):
        """Convenience property so templates require no changes."""
        return self.author.email


# ==============================================================================
# CHAT MESSAGE
# ==============================================================================

class ChatMessage(models.Model):
    """
    A chat message sent in a course chat room.

    3NF note: Previously stored sender_name as plain text. Replaced with a FK
    to User. SET_NULL is used so messages are preserved if the user is deleted.
    sender_name is exposed as a property for template and consumer compatibility.
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_messages',
        help_text='User who sent this message (null if user deleted)'
    )
    message = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        name = self.sender.username if self.sender else 'Anonymous'
        return f"{name} in {self.course.title}: {self.message[:50]}"

    @property
    def sender_name(self):
        """Convenience property for templates and the WebSocket consumer."""
        if self.sender:
            return self.sender.get_full_name() or self.sender.username
        return 'Anonymous'


# ==============================================================================
# WEATHER CACHE
# ==============================================================================

class WeatherCache(models.Model):
    """
    Caches weather API responses to avoid excessive external calls.
    Cache entries are considered stale after 30 minutes.
    """
    city = models.CharField(max_length=100, unique=True)
    temperature = models.DecimalField(max_digits=5, decimal_places=2)
    weather_code = models.IntegerField()
    weather_description = models.CharField(max_length=100)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Weather cache"

    def __str__(self):
        return f"{self.city}: {self.temperature}°C ({self.weather_description})"

    def is_stale(self):
        """Return True if the cached data is older than 30 minutes."""
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() - self.fetched_at > timedelta(minutes=30)

    @classmethod
    def get_weather_description(cls, code):
        """Convert a WMO weather code to a human-readable description."""
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Foggy",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with hail",
            99: "Thunderstorm with heavy hail",
        }
        return weather_codes.get(code, "Unknown")


# ==============================================================================
# FILE VALIDATORS
# ==============================================================================

def validate_file_size(file):
    """Reject files larger than 10 MB."""
    max_size_mb = 10
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f'File size cannot exceed {max_size_mb} MB')


def validate_file_extension(file):
    """Reject files with disallowed extensions."""
    allowed_extensions = [
        '.pdf', '.doc', '.docx', '.ppt', '.pptx',
        '.jpg', '.jpeg', '.png', '.gif', '.txt', '.zip'
    ]
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            f'File type "{ext}" is not allowed. '
            f'Allowed types: {", ".join(allowed_extensions)}'
        )


# ==============================================================================
# COURSE MATERIAL
# ==============================================================================

class CourseMaterial(models.Model):
    """
    A file uploaded by a teacher and attached to a course.
    file_type and file_size are auto-populated on save.
    """
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='materials',
        help_text='Course this material belongs to'
    )
    title = models.CharField(
        max_length=200,
        help_text='Descriptive title (e.g., "Week 1 Lecture Notes")'
    )
    description = models.TextField(
        blank=True,
        help_text='Optional description of the file content'
    )
    file = models.FileField(
        upload_to='course_materials/%Y%m/',
        validators=[validate_file_size, validate_file_extension],
        help_text='Upload PDF, image, or document (max 10MB)'
    )
    file_type = models.CharField(
        max_length=10,
        blank=True,
        help_text='File extension (auto-filled on save)'
    )
    file_size = models.IntegerField(
        default=0,
        help_text='File size in bytes (auto-filled on save)'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_materials',
        help_text='Teacher who uploaded this file'
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the file was uploaded'
    )
    download_count = models.IntegerField(
        default=0,
        help_text='Number of times this file has been downloaded'
    )

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Course Material'
        verbose_name_plural = 'Course Materials'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(file_size__gte=0),
                name='material_file_size_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(download_count__gte=0),
                name='material_download_count_nonnegative',
            ),
        ]

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    def save(self, *args, **kwargs):
        """Auto-populate file_type and file_size before saving."""
        if self.file:
            self.file_type = os.path.splitext(self.file.name)[1].lower()
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def get_file_size_display(self):
        """Return file size as a human-readable string (B / KB / MB)."""
        size_bytes = self.file_size
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def increment_download_count(self):
        """Atomically increment the counter to avoid lost concurrent updates."""
        type(self).objects.filter(pk=self.pk).update(
            download_count=models.F('download_count') + 1
        )
        self.refresh_from_db(fields=['download_count'])


# ==============================================================================
# NOTIFICATION
# ==============================================================================

class Notification(models.Model):
    """
    In-app notification delivered to a user.
    Created automatically via Django signals:
    - When a student enrols, the course teacher is notified.
    - When new material is uploaded, all enrolled students are notified.
    """
    ENROLLMENT = 'enrollment'
    NEW_MATERIAL = 'new_material'
    FEEDBACK = 'feedback'

    NOTIFICATION_TYPES = [
        (ENROLLMENT, 'New Enrollment'),
        (NEW_MATERIAL, 'New Course Material'),
        (FEEDBACK, 'New Feedback'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='User who receives this notification'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default=ENROLLMENT
    )
    message = models.TextField()
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text='Course this notification relates to'
    )
    is_read = models.BooleanField(
        default=False,
        help_text='True once the user has viewed this notification'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"{self.user.username} - {self.get_notification_type_display()}"

    def mark_as_read(self):
        """Mark this notification as read if it isn't already."""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])


# ==============================================================================
# STUDENT PROFILE
# ==============================================================================

class StudentProfile(models.Model):
    """
    Extended profile data for student users.
    OneToOne with User — each student has exactly one profile.
    Created automatically by the create_user_profile signal for student accounts.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )
    organization = models.CharField(
        max_length=200,
        blank=True,
        help_text="School or university name"
    )
    bio = models.TextField(
        blank=True,
        help_text="Tell us about yourself"
    )
    profile_picture = models.ImageField(
        upload_to="profiles/students/",
        blank=True,
        null=True
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}'s Student Profile"

    def get_full_name(self):
        """Return the user's full name, falling back to username."""
        if self.user.first_name and self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}"
        return self.user.username


# ==============================================================================
# TEACHER PROFILE
# ==============================================================================

class TeacherProfile(models.Model):
    """
    Extended profile data for teacher users.
    OneToOne with User — each teacher has exactly one profile.
    Created explicitly in UserRegistrationForm.save() for teacher accounts.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_profile'
    )
    bio = models.TextField(
        blank=True,
        help_text="Professional bio and teaching philosophy"
    )
    profile_picture = models.ImageField(
        upload_to="profiles/teachers/",
        blank=True,
        null=True
    )
    qualifications = models.TextField(
        blank=True,
        help_text="Degrees, certifications, experience"
    )
    subject_expertise = models.CharField(
        max_length=500,
        blank=True,
        help_text="Subjects you specialise in (comma-separated)"
    )
    years_of_experience = models.PositiveIntegerField(
        default=0,
        help_text="Years of teaching experience"
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact number for students"
    )
    office_hours = models.CharField(
        max_length=200,
        blank=True,
        help_text="When students can reach you"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Teacher Profile"
        verbose_name_plural = "Teacher Profiles"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}'s Teacher Profile"

    def get_full_name(self):
        """Return the user's full name, falling back to username."""
        if self.user.first_name and self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}"
        return self.user.username


# ==============================================================================
# SIGNALS
# ==============================================================================

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a StudentProfile for every new User.
    Teacher accounts are handled in UserRegistrationForm.save(), which deletes
    this StudentProfile and creates a TeacherProfile instead.
    """
    if created:
        StudentProfile.objects.create(user=instance)


@receiver(post_save, sender=TeacherProfile)
def enforce_teacher_profile_exclusivity(sender, instance, **kwargs):
    """Keep the application-level student/teacher roles mutually exclusive."""
    StudentProfile.objects.filter(user=instance.user).delete()
    instance.user._state.fields_cache.pop('student_profile', None)


@receiver(post_save, sender=Enrollment)
def notify_teacher_on_enrollment(sender, instance, created, **kwargs):
    """
    Notify the course teacher when a new student enrols.
    Uses instance.student directly — no email lookup needed.
    """
    if not created:
        return
    course = instance.course
    if not course.created_by:
        return

    Notification.objects.create(
        user=course.created_by,
        notification_type=Notification.ENROLLMENT,
        message=(
            f"{instance.student_name} has enrolled in your course "
            f'"{course.title}".'
        ),
        course=course
    )


@receiver(post_save, sender=CourseMaterial)
def notify_students_on_new_material(sender, instance, created, **kwargs):
    """
    Notify all active enrolled students when new material is uploaded.
    Uses the student FK on Enrollment directly — no fragile email lookup needed.
    """
    if not created:
        return
    course = instance.course

    enrollments = Enrollment.objects.filter(
        course=course,
        is_active=True
    ).select_related('student')

    Notification.objects.bulk_create([
        Notification(
            user=enrollment.student,
            notification_type=Notification.NEW_MATERIAL,
            message=(
                f'New material "{instance.title}" has been added '
                f'to "{course.title}".'
            ),
            course=course
        )
        for enrollment in enrollments
    ])
