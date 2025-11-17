from django.test import TestCase
from django.contrib.staticfiles import finders


class StaticFilesTests(TestCase):
    """Test that WhiteNoise is properly configured to serve static files."""

    def test_whitenoise_middleware_is_configured(self):
        """Verify WhiteNoise middleware is in the middleware stack."""
        from django.conf import settings
        self.assertIn(
            'whitenoise.middleware.WhiteNoiseMiddleware',
            settings.MIDDLEWARE
        )

    def test_static_root_is_configured(self):
        """Verify STATIC_ROOT is set."""
        from django.conf import settings
        self.assertIsNotNone(settings.STATIC_ROOT)

    def test_static_url_is_configured(self):
        """Verify STATIC_URL is set."""
        from django.conf import settings
        self.assertIsNotNone(settings.STATIC_URL)
        self.assertTrue(settings.STATIC_URL.endswith('/'))

