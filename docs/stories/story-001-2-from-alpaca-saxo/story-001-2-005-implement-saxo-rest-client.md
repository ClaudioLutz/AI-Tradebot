# Story 001-2-005: Implement Saxo REST Client Module

## Epic
Epic 001.2: Saxo Bank Migration and Integration

## User Story
As a developer, I want to implement a Saxo REST client module that handles API communication so that the application can make authenticated requests to the Saxo OpenAPI.

## Description
Create a new `saxo_client.py` module in the `data/` directory that provides a clean interface for making HTTP requests to the Saxo OpenAPI. This client will replace the Alpaca SDK functionality with direct REST API calls.

## Prerequisites
- Story 001-2-002 completed (`requests` library installed)
- Story 001-2-003 completed (environment variables configured)
- Story 001-2-004 completed (verification working)

## Acceptance Criteria
- [ ] `data/saxo_client.py` created
- [ ] Client loads credentials from environment variables
- [ ] GET and POST methods implemented
- [ ] Proper error handling included
- [ ] Authorization header automatically added
- [ ] Timeout handling implemented
- [ ] Client can be imported and instantiated

## Technical Details

### Module Location
`data/saxo_client.py`

### Key Features
1. **Environment Loading:** Reads `SAXO_REST_BASE` and `SAXO_ACCESS_TOKEN` from `.env`
2. **Authentication:** Automatically adds Bearer token to all requests
3. **Error Handling:** Raises clear exceptions for API errors
4. **Timeout:** 30-second timeout for all requests
5. **Reusability:** Drop-in replacement for Alpaca SDK

### Design Pattern
Simple, stateless REST client following the existing project's modular architecture.

## Implementation

### Complete saxo_client.py

```python
"""
Saxo Bank OpenAPI REST Client
Provides simple interface for making authenticated API calls to Saxo Bank.
"""
import os
from dotenv import load_dotenv
import requests
from typing import Dict, Any, Optional


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
        
        Raises:
            SaxoAuthenticationError: If required credentials are missing.
        """
        load_dotenv()
        
        self.base_url = os.getenv("SAXO_REST_BASE")
        self.token = os.getenv("SAXO_ACCESS_TOKEN")
        self.env = os.getenv("SAXO_ENV", "SIM")
        
        if not self.base_url:
            raise SaxoAuthenticationError(
                "SAXO_REST_BASE not found in environment variables"
            )
        
        if not self.token:
            raise SaxoAuthenticationError(
                "SAXO_ACCESS_TOKEN not found in environment variables"
            )
        
        # Remove trailing slash from base URL if present
        self.base_url = self.base_url.rstrip('/')
    
    @property
    def headers(self) -> Dict[str, str]:
        """
        Generate headers for API requests.
        
        Returns:
            Dictionary of HTTP headers including Authorization.
        """
        return {
            "Authorization": f"Bearer {self.token}",
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
            raise SaxoAuthenticationError(
                f"Authentication failed (HTTP {status_code}): {error_msg}. "
                "Check your SAXO_ACCESS_TOKEN. Token may be expired (24h limit)."
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
        return self.env == "SIM" or "/sim/" in self.base_url.lower()


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
```

## Files to Create
- `data/saxo_client.py` - New Saxo REST client module

## Verification Steps
- [ ] File created in correct location
- [ ] No syntax errors
- [ ] Can import module
- [ ] Can instantiate client
- [ ] Client loads environment variables
- [ ] Error handling works

## Testing

### Test 1: Import and Instantiate
```python
from data.saxo_client import SaxoClient

client = SaxoClient()
print(f"Client initialized: {client.is_sim_environment()}")
```

Expected: Prints "Client initialized: True"

### Test 2: Missing Credentials Error
```python
# Temporarily rename .env
import os
os.rename('.env', '.env.backup')

try:
    from data.saxo_client import SaxoClient
    client = SaxoClient()
except Exception as e:
    print(f"Expected error: {type(e).__name__}: {e}")
finally:
    os.rename('.env.backup', '.env')
```

Expected: SaxoAuthenticationError about missing credentials

### Test 3: Headers Generation
```python
from data.saxo_client import SaxoClient

client = SaxoClient()
headers = client.headers
print("Authorization" in headers)
print(headers["Content-Type"])
```

Expected:
```
True
application/json
```

### Test 4: URL Construction
```python
from data.saxo_client import SaxoClient

client = SaxoClient()
# Internal test - would be used in actual API call
test_path = "/port/v1/accounts/me"
full_url = f"{client.base_url}{test_path}"
print(full_url)
```

Expected: `https://gateway.saxobank.com/sim/openapi/port/v1/accounts/me`

## Documentation

### Module Docstring
Include comprehensive docstring explaining:
- Purpose of the module
- Basic usage examples
- Authentication requirements
- Error handling

### Class Docstring
Document:
- Initialization requirements
- Available methods
- Example usage

### Method Docstrings
Each method should document:
- Parameters
- Return type
- Exceptions raised
- Usage examples

## Time Estimate
**45 minutes** (implement + test + document)

## Dependencies
- Story 001-2-002 completed (requests installed)
- Story 001-2-003 completed (environment configured)

## Blocks
- Story 001-2-006 (connection test needs this client)
- Story 001-2-007 (market data needs this client)
- Story 001-2-008 (trade execution needs this client)

## Architecture Notes
- **Location:** `data/` directory (similar to market_data.py)
- **Pattern:** Follows existing modular design
- **Reusability:** Can be used across all modules
- **Simplicity:** Minimal dependencies, clear interface

## Error Handling Strategy
1. **Missing Credentials:** Fail fast with clear error
2. **HTTP Errors:** Convert to domain-specific exceptions
3. **Timeouts:** 30-second limit with clear message
4. **JSON Errors:** Handle invalid responses gracefully
5. **Token Expiry:** Special message for 401/403 errors

## Future Enhancements (Not in this story)
- WebSocket support for streaming
- Request retry logic
- Response caching
- Rate limit handling
- Request logging

## Security Considerations
- Never log full token
- Token loaded from environment only
- HTTPS enforced by base URL
- Timeout prevents hanging requests

## Common Issues and Solutions

### Issue: Import errors
**Solution:** Ensure file is in `data/` directory

### Issue: Missing requests module
**Solution:** Run Story 001-2-002

### Issue: Authentication errors
**Solution:** Run Story 001-2-003 to configure .env

## References
- Analysis Document: `docs/Alpaca-to-Saxo-analysis.md` (Section 6)
- [Requests Documentation](https://requests.readthedocs.io/)
- [Saxo OpenAPI](https://developer.saxobank.com)

## Success Criteria
✅ Story is complete when:
1. `saxo_client.py` created in `data/` directory
2. All methods implemented
3. Error handling working
4. Can import and instantiate
5. All verification tests pass
6. Code is well-documented
