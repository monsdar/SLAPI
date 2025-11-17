"""
Authentication for the SLAPI API.
"""
from typing import Any, Optional

from django.conf import settings
from django.http import HttpRequest
from ninja.security import HttpBearer


class APITokenAuth(HttpBearer):
    """
    Bearer token authentication for API endpoints.
    
    Expects the API token to be provided in the Authorization header:
    Authorization: Bearer <token>
    
    If SLAPI_API_TOKEN is not set in the environment, authentication is disabled
    and all requests are allowed through.
    """
    
    def __call__(self, request: HttpRequest) -> Optional[Any]:
        """
        Override the __call__ method to bypass authentication when no token is configured.
        
        Args:
            request: The HTTP request object
            
        Returns:
            True if authentication succeeds or is disabled, None if it fails
        """
        # If no token is configured, allow all requests (development mode)
        if settings.SLAPI_API_TOKEN is None:
            return True
        
        # Otherwise, use the default HttpBearer authentication
        return super().__call__(request)
    
    def authenticate(self, request: HttpRequest, token: str) -> Optional[bool]:
        """
        Validate the provided token against the configured API token.
        
        Args:
            request: The HTTP request object
            token: The token extracted from the Authorization header
            
        Returns:
            True if authentication succeeds, None if it fails
        """
        # Check if the provided token matches the configured token
        if token == settings.SLAPI_API_TOKEN:
            return True
        
        return None

