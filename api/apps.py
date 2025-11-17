import os
import sys

from django.apps import AppConfig
from django.contrib.auth import get_user_model
from django.db import IntegrityError, OperationalError

# Flag to ensure admin user creation only runs once
_admin_user_created = False


def create_admin_user_from_env():
    """Create admin user from environment variables if it doesn't exist."""
    global _admin_user_created
    
    # Only run once to avoid multiple calls during app initialization
    if _admin_user_created:
        return
    
    # Skip during migrations and tests to avoid database errors
    if 'migrate' in sys.argv or 'makemigrations' in sys.argv or 'test' in sys.argv:
        return

    admin_username = os.getenv('SLAPI_ADMIN_USER')
    admin_password = os.getenv('SLAPI_ADMIN_PASSWORD')

    if admin_username and admin_password:
        try:
            User = get_user_model()
            # Use get_or_create to handle race conditions
            user, created = User.objects.get_or_create(
                username=admin_username,
                defaults={'is_staff': True, 'is_superuser': True}
            )
            if created:
                user.set_password(admin_password)
                user.save()
            _admin_user_created = True
        except (OperationalError, IntegrityError):
            # OperationalError: Database tables don't exist yet (migrations not run)
            # IntegrityError: User already exists (race condition)
            # Both are expected scenarios and can be safely ignored
            pass


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        """Create admin user from environment variables if it doesn't exist."""
        create_admin_user_from_env()
