import os
import sys

from django.apps import AppConfig
from django.contrib.auth import get_user_model
from django.db import OperationalError


def create_admin_user_from_env():
    """Create admin user from environment variables if it doesn't exist."""
    # Skip during migrations to avoid database errors
    if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
        return

    admin_username = os.getenv('SLAPI_ADMIN_USER')
    admin_password = os.getenv('SLAPI_ADMIN_PASSWORD')

    if admin_username and admin_password:
        try:
            User = get_user_model()
            if not User.objects.filter(username=admin_username).exists():
                User.objects.create_superuser(
                    username=admin_username,
                    password=admin_password,
                )
        except OperationalError:
            # Database tables don't exist yet (migrations not run)
            # This is expected during initial setup
            pass


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        """Create admin user from environment variables if it doesn't exist."""
        create_admin_user_from_env()
