"""
Saxo Bank OpenAPI REST Client
Provides simple interface for making authenticated API calls to Saxo Bank.
"""
import os
from dotenv import load_dotenv
import requests
from typing import Dict, Any, Optional

from auth.saxo_oauth import get_access_token


class SaxoClientError(Exception):
    """Base exception for Saxo client errors."""
    pass


class SaxoAuthenticationError(SaxoClientError):
    """Raised when authentication fails."""
    pass


class SaxoAPIError(SaxoClientError):
    """Raised when API returns an error response."""
    pass


class SaxoClient:
    """
    REST client for Saxo Bank OpenAPI.
    
    Handles authentication, request formatting, and error handling
    for all API calls to Saxo Bank.
    
    Example:
        client = SaxoClient()
        accounts = client.get("/port/v1/accounts/me")
    """
    
    def __init__(self):
        """
        Initialize Saxo client with credentials from environment.
        
        Supports both manual token mode (SAXO_ACCESS_TOKEN) and
        OAuth mode (automatic token refresh).
        
        Raises:
            SaxoAuthenticationError: If required credentials are missing.
        """
        load_dotenv()
        
        self.base_url = os.getenv("SAXO_REST_BASE")
        self.env = os.getenv("SAXO_ENV", "SIM")
        
        if not self.base_url:
            raise SaxoAuthenticationError(
                "SAXO_REST_BASE not found in environment variables"
            )
        
        # Remove trailing slash from base URL if present
        self.base_url = self.base_url.rstrip('/')
    
    @property
    def headers(self) -> Dict[str, str]:
        """
        Generate headers for API requests.
        
        Automatically retrieves valid access token, refreshing if necessary.
        
        Returns:
            Dictionary of HTTP headers including Authorization.
        """
        return {
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json",
        }
    
    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make GET request to Saxo API.
        
        Args:
            path: API endpoint path (e.g., "/port/v1/accounts/me")
            params: Optional query parameters
        
        Returns:
            JSON response as dictionary
        
        Raises:
            SaxoAPIError: If request fails or returns error status
        """
        url = f"{self.base_url}{path}"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e, response)
        except requests.exceptions.Timeout:
            raise SaxoAPIError(f"Request timeout for GET {path}")
        except requests.exceptions.RequestException as e:
            raise SaxoAPIError(f"Request failed: {str(e)}")
        except ValueError as e:
            raise SaxoAPIError(f"Invalid JSON response: {str(e)}")
    
    def post(
        self,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make POST request to Saxo API.
        
        Args:
            path: API endpoint path (e.g., "/trade/v2/orders")
            json_body: Optional JSON body for request
            params: Optional query parameters
        
        Returns:
            JSON response as dictionary
        
        Raises:
            SaxoAPIError: If request fails or returns error status
        """
        url = f"{self.base_url}{path}"
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=json_body,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            # Some endpoints return empty response
            if response.text:
                return response.json()
            return {}
        
        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e, response)
        except requests.exceptions.Timeout:
            raise SaxoAPIError(f"Request timeout for POST {path}")
        except requests.exceptions.RequestException as e:
            raise SaxoAPIError(f"Request failed: {str(e)}")
        except ValueError as e:
            raise SaxoAPIError(f"Invalid JSON response: {str(e)}")
    
    def delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make DELETE request to Saxo API.
        
        Args:
            path: API endpoint path
            params: Optional query parameters
        
        Returns:
            JSON response as dictionary
        
        Raises:
            SaxoAPIError: If request fails or returns error status
        """
        url = f"{self.base_url}{path}"
        
        try:
            response = requests.delete(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            # Some endpoints return empty response
            if response.text:
                return response.json()
            return {}
        
        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e, response)
        except requests.exceptions.Timeout:
            raise SaxoAPIError(f"Request timeout for DELETE {path}")
        except requests.exceptions.RequestException as e:
            raise SaxoAPIError(f"Request failed: {str(e)}")
        except ValueError as e:
            raise SaxoAPIError(f"Invalid JSON response: {str(e)}")
    
    def _handle_http_error(self, error: requests.exceptions.HTTPError, response: requests.Response):
        """
        Handle HTTP errors with detailed error messages.
        
        Args:
            error: The HTTPError exception
            response: The response object
        
        Raises:
            SaxoAuthenticationError: For 401/403 errors
            SaxoAPIError: For other HTTP errors
        """
        status_code = response.status_code
        
        # Try to extract error message from response
        try:
            error_data = response.json()
            error_msg = error_data.get("Message", str(error))
        except:
            error_msg = response.text or str(error)
        
        # Handle authentication errors
        if status_code in [401, 403]:
            # Check which authentication mode is being used
            token = os.getenv("SAXO_ACCESS_TOKEN")
            using_manual_token = token is not None and token.strip() != ""
            
            if using_manual_token:
                auth_help = (
                    "Token may be expired (24h limit). "
                    "Generate a new token at https://developer.saxobank.com and update SAXO_ACCESS_TOKEN in .env"
                )
            else:
                auth_help = (
                    "OAuth token may be invalid or expired. "
                    "Try running: python scripts/saxo_login.py"
                )
            
            raise SaxoAuthenticationError(
                f"Authentication failed (HTTP {status_code}): {error_msg}. {auth_help}"
            )
        
        # Handle other errors
        raise SaxoAPIError(
            f"API request failed (HTTP {status_code}): {error_msg}"
        )
    
    def is_sim_environment(self) -> bool:
        """
        Check if client is configured for SIM environment.
        
        Returns:
            True if using SIM environment
        """
        if self.env == "SIM":
            return True
        if self.base_url and "/sim/" in self.base_url.lower():
            return True
        return False


# Convenience function for quick client creation
def create_client() -> SaxoClient:
    """
    Create and return a configured SaxoClient instance.
    
    Returns:
        Configured SaxoClient
    
    Raises:
        SaxoAuthenticationError: If credentials are missing
    """
    return SaxoClient()
