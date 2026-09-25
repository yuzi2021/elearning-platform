"""
Custom authentication backend — email-based login.

Django's default backend authenticates with username + password.
This backend authenticates with email + password instead, which is
more user-friendly and aligns with the course requirement to use a
unique email as the primary login identifier.

Registration: UserRegistrationForm already enforces unique email via clean_email().
Login:        EmailBackend looks up the User by email, then verifies the password.

To activate, add to settings.py:
    AUTHENTICATION_BACKENDS = [
        'courses.backends.EmailBackend',
        'django.contrib.auth.backends.ModelBackend',  # fallback for admin
    ]
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailBackend(ModelBackend):
    """
    Authenticate using email address instead of username.

    Django calls each backend in AUTHENTICATION_BACKENDS in order.
    If this backend returns None, Django tries the next one.
    If it returns a User, authentication succeeds.
    If it raises PermissionDenied, authentication stops immediately.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Look up the user by email (passed in the 'username' parameter because
        Django's authenticate() always uses the 'username' kwarg regardless of
        what the login form calls the field).
        """
        if username is None or password is None:
            return None

        # Treat the 'username' argument as an email address
        email = username.strip().lower()

        try:
            # Email is unique (enforced at registration), so get() is safe
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Run the default password hasher to prevent timing attacks
            # (avoids leaking whether an email is registered via response time)
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # Shouldn't happen because clean_email() enforces uniqueness,
            # but handle gracefully just in case
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None

    def get_user(self, user_id):
        """
        Required by Django — called on every request to reload the user
        from the session.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None