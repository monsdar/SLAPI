"""
Tests for API token authentication.
"""
from django.conf import settings
from django.test import TestCase, override_settings
from unittest.mock import patch, MagicMock


class AuthenticationTests(TestCase):
    """Tests for API token authentication."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the service to avoid making real HTTP requests
        self.patcher = patch('api.api.service')
        self.mock_service = self.patcher.start()
        
        # Set up mock responses
        self.mock_service.get_leagues.return_value = [
            {"id": "123", "name": "Test League"}
        ]
        self.mock_service.get_associations.return_value = [
            {"id": "1", "label": "Test Verband", "hits": 0}
        ]
        self.mock_service.get_standings.return_value = {
            "league_id": "123",
            "standings": []
        }
        self.mock_service.get_matches.return_value = {
            "league_id": "123",
            "matches": []
        }
        self.mock_service.get_club_leagues.return_value = {
            "club_name": "Test Club",
            "verband_id": 7,
            "leagues": []
        }
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.patcher.stop()
    
    @override_settings(SLAPI_API_TOKEN=None)
    def test_health_endpoint_always_accessible_without_token(self):
        """The /health endpoint should always be accessible without authentication."""
        response = self.client.get("/health")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
    
    @override_settings(SLAPI_API_TOKEN="test-token-123")
    def test_health_endpoint_always_accessible_with_auth_enabled(self):
        """The /health endpoint should be accessible even when authentication is enabled."""
        response = self.client.get("/health")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
    
    @override_settings(SLAPI_API_TOKEN=None)
    def test_no_auth_required_when_token_not_configured(self):
        """When SLAPI_API_TOKEN is not set, endpoints should be accessible without auth."""
        # Test /leagues endpoint
        response = self.client.get("/leagues")
        self.assertEqual(response.status_code, 200)
        
        # Test /verbaende endpoint
        response = self.client.get("/verbaende")
        self.assertEqual(response.status_code, 200)
        
        # Test /leagues/{id}/standings endpoint
        response = self.client.get("/leagues/123/standings")
        self.assertEqual(response.status_code, 200)
        
        # Test /leagues/{id}/matches endpoint
        response = self.client.get("/leagues/123/matches")
        self.assertEqual(response.status_code, 200)
        
        # Test /clubs/{name}/leagues endpoint
        response = self.client.get("/clubs/TestClub/leagues")
        self.assertEqual(response.status_code, 200)
    
    @override_settings(SLAPI_API_TOKEN="test-token-123")
    def test_auth_required_when_token_configured(self):
        """When SLAPI_API_TOKEN is set, endpoints should require authentication."""
        # Test /leagues endpoint
        response = self.client.get("/leagues")
        self.assertEqual(response.status_code, 401)
        
        # Test /verbaende endpoint
        response = self.client.get("/verbaende")
        self.assertEqual(response.status_code, 401)
        
        # Test /leagues/{id}/standings endpoint
        response = self.client.get("/leagues/123/standings")
        self.assertEqual(response.status_code, 401)
        
        # Test /leagues/{id}/matches endpoint
        response = self.client.get("/leagues/123/matches")
        self.assertEqual(response.status_code, 401)
        
        # Test /clubs/{name}/leagues endpoint
        response = self.client.get("/clubs/TestClub/leagues")
        self.assertEqual(response.status_code, 401)
    
    @override_settings(SLAPI_API_TOKEN="test-token-123")
    def test_valid_token_grants_access(self):
        """Providing a valid token should grant access to protected endpoints."""
        headers = {"HTTP_AUTHORIZATION": "Bearer test-token-123"}
        
        # Test /leagues endpoint
        response = self.client.get("/leagues", **headers)
        self.assertEqual(response.status_code, 200)
        
        # Test /verbaende endpoint
        response = self.client.get("/verbaende", **headers)
        self.assertEqual(response.status_code, 200)
        
        # Test /leagues/{id}/standings endpoint
        response = self.client.get("/leagues/123/standings", **headers)
        self.assertEqual(response.status_code, 200)
        
        # Test /leagues/{id}/matches endpoint
        response = self.client.get("/leagues/123/matches", **headers)
        self.assertEqual(response.status_code, 200)
        
        # Test /clubs/{name}/leagues endpoint
        response = self.client.get("/clubs/TestClub/leagues", **headers)
        self.assertEqual(response.status_code, 200)
    
    @override_settings(SLAPI_API_TOKEN="test-token-123")
    def test_invalid_token_denies_access(self):
        """Providing an invalid token should deny access to protected endpoints."""
        headers = {"HTTP_AUTHORIZATION": "Bearer wrong-token"}
        
        # Test /leagues endpoint
        response = self.client.get("/leagues", **headers)
        self.assertEqual(response.status_code, 401)
        
        # Test /verbaende endpoint
        response = self.client.get("/verbaende", **headers)
        self.assertEqual(response.status_code, 401)
        
        # Test /leagues/{id}/standings endpoint
        response = self.client.get("/leagues/123/standings", **headers)
        self.assertEqual(response.status_code, 401)
        
        # Test /leagues/{id}/matches endpoint
        response = self.client.get("/leagues/123/matches", **headers)
        self.assertEqual(response.status_code, 401)
        
        # Test /clubs/{name}/leagues endpoint
        response = self.client.get("/clubs/TestClub/leagues", **headers)
        self.assertEqual(response.status_code, 401)
    
    @override_settings(SLAPI_API_TOKEN="test-token-123")
    def test_malformed_authorization_header_denies_access(self):
        """Malformed Authorization headers should deny access."""
        # Missing "Bearer" prefix
        headers = {"HTTP_AUTHORIZATION": "test-token-123"}
        response = self.client.get("/leagues", **headers)
        self.assertEqual(response.status_code, 401)
        
        # Empty token
        headers = {"HTTP_AUTHORIZATION": "Bearer "}
        response = self.client.get("/leagues", **headers)
        self.assertEqual(response.status_code, 401)
        
        # No token at all
        headers = {"HTTP_AUTHORIZATION": "Bearer"}
        response = self.client.get("/leagues", **headers)
        self.assertEqual(response.status_code, 401)
    
    @override_settings(SLAPI_API_TOKEN="test-token-123")
    def test_query_parameters_work_with_auth(self):
        """Query parameters should work correctly with authentication."""
        headers = {"HTTP_AUTHORIZATION": "Bearer test-token-123"}
        
        # Test with use_cache parameter
        response = self.client.get("/leagues?use_cache=false", **headers)
        self.assertEqual(response.status_code, 200)
        self.mock_service.get_leagues.assert_called_with(use_cache=False)
        
        # Test with verband_id parameter
        response = self.client.get("/clubs/TestClub/leagues?verband_id=5", **headers)
        self.assertEqual(response.status_code, 200)
        self.mock_service.get_club_leagues.assert_called_with("TestClub", 5, use_cache=True)

