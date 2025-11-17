import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

import api.apps
from api.apps import create_admin_user_from_env


class AdminUserCreationTests(TestCase):
    """Tests for automatic admin user creation from environment variables."""

    def setUp(self):
        """Set up test fixtures."""
        self.User = get_user_model()
        # Reset the global flag before each test to ensure clean state
        api.apps._admin_user_created = False

    def test_admin_user_created_when_env_vars_set_and_user_not_exists(self):
        """Test that admin user is created when env vars are set and user doesn't exist."""
        with patch.dict(os.environ, {
            'SLAPI_ADMIN_USER': 'testadmin',
            'SLAPI_ADMIN_PASSWORD': 'testpass123',
        }):
            # Ensure user doesn't exist
            self.assertFalse(self.User.objects.filter(username='testadmin').exists())

            # Call the function to trigger user creation
            create_admin_user_from_env()

            # Verify user was created
            user = self.User.objects.get(username='testadmin')
            self.assertTrue(user.is_superuser)
            self.assertTrue(user.is_staff)
            self.assertTrue(user.check_password('testpass123'))

    def test_admin_user_not_created_when_user_already_exists(self):
        """Test that admin user is not recreated when user already exists."""
        # Create user first
        existing_user = self.User.objects.create_user(
            username='existingadmin',
            password='oldpassword',
        )

        with patch.dict(os.environ, {
            'SLAPI_ADMIN_USER': 'existingadmin',
            'SLAPI_ADMIN_PASSWORD': 'newpassword',
        }):
            # Call the function to trigger user creation logic
            create_admin_user_from_env()

            # Verify user still exists and password wasn't changed
            user = self.User.objects.get(username='existingadmin')
            self.assertTrue(user.check_password('oldpassword'))
            self.assertFalse(user.check_password('newpassword'))

    def test_admin_user_not_created_when_username_missing(self):
        """Test that admin user is not created when SLAPI_ADMIN_USER is not set."""
        with patch.dict(os.environ, {
            'SLAPI_ADMIN_PASSWORD': 'testpass123',
        }, clear=False):
            # Remove SLAPI_ADMIN_USER if it exists
            os.environ.pop('SLAPI_ADMIN_USER', None)

            # Call the function
            create_admin_user_from_env()

            # Verify no user was created
            self.assertEqual(self.User.objects.count(), 0)

    def test_admin_user_not_created_when_password_missing(self):
        """Test that admin user is not created when SLAPI_ADMIN_PASSWORD is not set."""
        with patch.dict(os.environ, {
            'SLAPI_ADMIN_USER': 'testadmin',
        }, clear=False):
            # Remove SLAPI_ADMIN_PASSWORD if it exists
            os.environ.pop('SLAPI_ADMIN_PASSWORD', None)

            # Call the function
            create_admin_user_from_env()

            # Verify no user was created
            self.assertFalse(self.User.objects.filter(username='testadmin').exists())

    def test_admin_user_not_created_when_both_env_vars_missing(self):
        """Test that admin user is not created when both env vars are missing."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove both env vars if they exist
            os.environ.pop('SLAPI_ADMIN_USER', None)
            os.environ.pop('SLAPI_ADMIN_PASSWORD', None)

            # Call the function
            create_admin_user_from_env()

            # Verify no user was created
            self.assertEqual(self.User.objects.count(), 0)

    def test_admin_user_creation_only_runs_once(self):
        """Test that the function only runs once even if called multiple times."""
        with patch.dict(os.environ, {
            'SLAPI_ADMIN_USER': 'testadmin',
            'SLAPI_ADMIN_PASSWORD': 'testpass123',
        }):
            # First call should create the user
            create_admin_user_from_env()
            self.assertEqual(self.User.objects.count(), 1)
            
            # Second call should not create another user or raise an error
            create_admin_user_from_env()
            self.assertEqual(self.User.objects.count(), 1)
            
            # Third call should also be safe
            create_admin_user_from_env()
            self.assertEqual(self.User.objects.count(), 1)

    def test_admin_user_creation_handles_race_condition(self):
        """Test that IntegrityError is handled gracefully (race condition)."""
        # Pre-create a user to simulate a race condition
        self.User.objects.create_superuser(
            username='raceadmin',
            password='oldpassword',
        )
        
        # Reset the flag to simulate the function being called again
        api.apps._admin_user_created = False
        
        with patch.dict(os.environ, {
            'SLAPI_ADMIN_USER': 'raceadmin',
            'SLAPI_ADMIN_PASSWORD': 'newpassword',
        }):
            # This should not raise an error even though user exists
            create_admin_user_from_env()
            
            # Verify only one user exists and password wasn't changed
            self.assertEqual(self.User.objects.filter(username='raceadmin').count(), 1)
            user = self.User.objects.get(username='raceadmin')
            self.assertTrue(user.check_password('oldpassword'))

