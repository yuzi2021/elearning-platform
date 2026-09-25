"""
Django Admin configuration.

"""
from django.contrib import admin
from .models import Course, Enrollment, Feedback, StatusUpdate, CourseMaterial, Notification


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin interface for Course model."""
    list_display = ['title', 'instructor_name', 'created_at', 'get_enrollment_count']
    list_filter = ['created_at']
    # instructor_name and instructor_email are properties — search via created_by
    search_fields = ['title', 'created_by__username', 'created_by__email',
                     'created_by__first_name', 'created_by__last_name']
    readonly_fields = ['instructor_name', 'instructor_email', 'created_at', 'updated_at']

    fieldsets = (
        ('Course Information', {
            'fields': ('title', 'description')
        }),
        ('Instructor', {
            # created_by is the stored FK; instructor_name/email are read-only
            # derived properties shown for convenience
            'fields': ('created_by', 'instructor_name', 'instructor_email')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_enrollment_count(self, obj):
        return obj.get_enrollment_count()
    get_enrollment_count.short_description = 'Enrollments'


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    """Admin interface for Enrollment model."""
    # student_name and student_email are model properties derived from the FK
    list_display = ['student_name', 'student_email', 'course', 'enrolled_at', 'is_active']
    list_filter = ['is_active', 'enrolled_at']
    # Search via the student FK relationship
    search_fields = ['student__username', 'student__email',
                     'student__first_name', 'student__last_name',
                     'course__title']
    readonly_fields = ['enrolled_at', 'student_name', 'student_email']
    raw_id_fields = ['student']  # FK picker for large user tables


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    """Admin interface for Feedback model."""
    list_display = ['student_name', 'course', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['student__username', 'student__email',
                     'student__first_name', 'student__last_name',
                     'course__title', 'comment']
    readonly_fields = ['created_at', 'student_name', 'student_email']
    raw_id_fields = ['student']


@admin.register(StatusUpdate)
class StatusUpdateAdmin(admin.ModelAdmin):
    """Admin interface for StatusUpdate model."""
    list_display = ['author_name', 'content_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['author__username', 'author__email',
                     'author__first_name', 'author__last_name',
                     'content']
    readonly_fields = ['created_at', 'author_name', 'author_email']
    raw_id_fields = ['author']

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    """Admin interface for CourseMaterial model."""
    list_display = [
        'title',
        'course',
        'file_type',
        'get_file_size_display',
        'uploaded_by',
        'uploaded_at',
        'download_count'
    ]
    list_filter = ['file_type', 'uploaded_at', 'course']
    search_fields = ['title', 'description', 'course__title']
    readonly_fields = ['file_type', 'file_size', 'uploaded_at', 'download_count']
    fieldsets = (
        ('File Information', {
            'fields': ('title', 'description', 'file')
        }),
        ('Course Association', {
            'fields': ('course', 'uploaded_by')
        }),
        ('Metadata (Auto-filled)', {
            'fields': ('file_type', 'file_size', 'uploaded_at', 'download_count'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model."""
    list_display = ['user', 'notification_type', 'message', 'course', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'message', 'course__title']
    readonly_fields = ['created_at']
    actions = ['mark_all_read']

    def mark_all_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f'{queryset.count()} notifications marked as read.')
    mark_all_read.short_description = 'Mark selected as read'