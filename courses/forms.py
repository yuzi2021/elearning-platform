"""
Django forms for the eLearning platform.

"""
from django import forms
from .models import (
    Course, Enrollment, Feedback, StatusUpdate,
    StudentProfile, TeacherProfile, CourseMaterial
)
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.conf import settings


# ==============================================================================
# COURSE FORM
# ==============================================================================

class CourseForm(forms.ModelForm):
    """
    Form for creating and editing courses.
    instructor_name and instructor_email are removed — they are now derived
    from created_by on the Course model and do not need to be entered separately.
    """
    class Meta:
        model = Course
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            }),
        }


# ==============================================================================
# ENROLLMENT FORM
# ==============================================================================

class EnrollmentForm(forms.ModelForm):
    """
    Form for course enrollment.
    No fields are shown — the student FK is set from request.user in the view.
    The form exists so the view can call form.save(commit=False) cleanly.
    """
    class Meta:
        model = Enrollment
        fields = []


# ==============================================================================
# FEEDBACK FORM
# ==============================================================================

class FeedbackForm(forms.ModelForm):
    """
    Form for submitting course feedback.
    student_name and student_email removed — the student FK is set from
    request.user in the view. Only rating and comment are needed from the user.
    """
    class Meta:
        model = Feedback
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(
                choices=[(i, f'{i} Star{"s" if i > 1 else ""}') for i in range(1, 6)],
                attrs={'class': 'form-control'}
            ),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Share your feedback'
            }),
        }


# ==============================================================================
# STATUS UPDATE FORM
# ==============================================================================

class StatusUpdateForm(forms.ModelForm):
    """
    Form for posting a status update.
    author_name and author_email removed — the author FK is set from
    request.user in the view.
    """
    class Meta:
        model = StatusUpdate
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': "What's on your mind?"
            }),
        }


# ==============================================================================
# USER REGISTRATION FORM
# ==============================================================================

class UserRegistrationForm(UserCreationForm):
    """
    Form for user registration.
    Extends Django's built-in UserCreationForm which provides:
    - username field
    - password1 (password)
    - password2 (password confirmation)
    - Built-in password validation

    Additional fields added:
    - email (validated as unique)
    - first_name, last_name
    - user_type (student or teacher)
    """
    email = forms.EmailField(
        required=True,
        help_text="Enter a valid email address"
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        help_text="Your first name"
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        help_text="Your last name"
    )
    user_type = forms.ChoiceField(
        choices=[
            ('student', 'Student'),
            ('teacher', 'Teacher')
        ],
        required=True,
        widget=forms.RadioSelect,
        help_text="Select your role"
    )

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'password1',
            'password2',
            'user_type'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.ALLOW_INSTRUCTOR_REGISTRATION:
            self.fields['user_type'].choices = [('student', 'Learner')]

    def clean_email(self):
        """
        Validate that the email address is not already registered.
        Django calls clean_<fieldname>() automatically during form validation.
        """
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def clean_username(self):
        """Ensure username contains only letters, numbers, and underscores."""
        username = self.cleaned_data.get('username')
        if not username.replace('_', '').isalnum():
            raise ValidationError(
                'Username can only contain letters, numbers, and underscores.'
            )
        return username

    def save(self, commit=True):
        """
        Override save() to set email, first_name, last_name, and create the
        correct profile type based on user_type selection.

        For teachers: the StudentProfile created by the post_save signal is
        deleted and a TeacherProfile is created in its place.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            user_type = self.cleaned_data['user_type']
            if user_type == 'teacher':
                # Remove the StudentProfile created by the signal
                if hasattr(user, 'student_profile'):
                    user.student_profile.delete()
                TeacherProfile.objects.create(user=user)
        return user


# ==============================================================================
# STUDENT PROFILE FORM
# ==============================================================================

class StudentProfileForm(forms.ModelForm):
    """Form for editing a student's extended profile."""
    class Meta:
        model = StudentProfile
        fields = [
            'organization',
            'bio',
            'profile_picture',
            'date_of_birth'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Tell us about yourself...'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date'
            }),
            'organization': forms.TextInput(attrs={
                'placeholder': 'University of Helsinki'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.MEDIA_UPLOADS_ENABLED:
            self.fields.pop('profile_picture', None)


# ==============================================================================
# TEACHER PROFILE FORM
# ==============================================================================

class TeacherProfileForm(forms.ModelForm):
    """Form for editing a teacher's extended profile."""
    class Meta:
        model = TeacherProfile
        fields = [
            'bio',
            'profile_picture',
            'qualifications',
            'subject_expertise',
            'years_of_experience',
            'phone_number',
            'office_hours'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Share your teaching philosophy...'
            }),
            'qualifications': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'List your degrees, certifications, and experience...'
            }),
            'subject_expertise': forms.TextInput(attrs={
                'placeholder': 'Python, Django, Web Development, etc.'
            }),
            'office_hours': forms.TextInput(attrs={
                'placeholder': 'e.g., Mon-Wed 2-4pm, Fri 10am-12pm'
            }),
            'phone_number': forms.TextInput(attrs={
                'placeholder': '+358 50 123 4567'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.MEDIA_UPLOADS_ENABLED:
            self.fields.pop('profile_picture', None)


# ==============================================================================
# LOGIN FORM
# ==============================================================================

class LoginForm(forms.Form):
    """
    Form for email-based login.
    Uses email instead of username as the login identifier, matching the
    course requirement and the unique-email constraint enforced at registration.
    The email value is passed to authenticate() in the 'username' kwarg because
    Django's authenticate() signature always uses that name — our custom
    EmailBackend (courses/backends.py) handles it correctly.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password',
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Keep me logged in for 2 weeks"
    )


# ==============================================================================
# COURSE MATERIAL FORM
# ==============================================================================

class CourseMaterialForm(forms.ModelForm):
    """Form for teachers to upload files to a course."""
    class Meta:
        model = CourseMaterial
        fields = ['title', 'description', 'file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Week 1 Lecture Notes',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional: Describe what this file contains...'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.txt,.zip'
            }),
        }
        labels = {
            'title': 'Material Title',
            'description': 'Description (optional)',
            'file': 'Choose File'
        }
        help_texts = {
            'file': 'Max 10MB. Allowed: PDF, DOC, PPT, images, ZIP'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
