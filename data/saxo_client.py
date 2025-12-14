"""
Saxo Bank OpenAPI REST Client
Provides interface for making authenticated API calls to Saxo Bank with rate limiting and retry support.

Rate Limiting (Story 003-004):
- Parses all X-RateLimit-* headers from Saxo responses
- Implements exponential backoff with jitter for retries
- Respects Retry-After header when present
- Retries only on: 429, 5xx, timeouts/transient network errors
- Does NOT retry on: 400, 401, 403
"""
import os
import re
import time
import random
import logging
from dotenv import load_dotenv
import requests
from typing import Dict, Any, Optional, Tuple, List, Set

from auth.saxo_oauth import get_access_token


# Configure module logger
logger = logging.getLogger(__name__)


class SaxoClientError(Exception):
    """Base exception for Saxo client errors."""
    pass


class SaxoAuthenticationError(SaxoClientError):
    """Raised when authentication fails."""
    pass


class SaxoAPIError(SaxoClientError):
    """Raised when API returns an error response."""
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 error_code: Optional[str] = None, rate_limit_info: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.rate_limit_info = rate_limit_info or {}


class SaxoRateLimitError(SaxoAPIError):
    """Raised specifically for rate limit (429) errors."""
    def __init__(self, message: str, retry_after: Optional[int] = None, 
                 rate_limit_info: Optional[Dict] = None):
        super().__init__(message, status_code=429, error_code="RateLimitExceeded", 
                        rate_limit_info=rate_limit_info)
        self.retry_after = retry_after


# =============================================================================
# Rate Limit Configuration (Story 003-004)
# =============================================================================

# Minimum polling intervals (seconds) - configurable via env
# NOTE: we parse defensively to avoid import-time crashes if env values are invalid.

def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        val = float(raw) if raw is not None else default
        return max(val, 0.0)
    except (TypeError, ValueError):
        return default


MIN_QUOTES_POLL_SECONDS = _float_env("SAXO_MIN_QUOTES_POLL_SECONDS", 5.0)
MIN_BARS_POLL_SECONDS = _float_env("SAXO_MIN_BARS_POLL_SECONDS", 10.0)

# Retry configuration
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 60.0
JITTER_FACTOR = 0.5  # 50% jitter

# HTTP status codes that should trigger retry
RETRYABLE_STATUS_CODES: Set[int] = {429, 500, 502, 503, 504}

# HTTP status codes that should NOT be retried
NON_RETRYABLE_STATUS_CODES: Set[int] = {400, 401, 403}


# =============================================================================
# Rate Limit Header Parsing (Story 003-004)
# =============================================================================

def parse_rate_limit_headers(headers: Dict[str, str]) -> Dict[str, Any]:
    """
    Parse all X-RateLimit-* headers from a Saxo API response.
    
    Saxo returns multiple rate limit dimensions:
    - X-RateLimit-Session-Remaining / X-RateLimit-Session-Reset
    - X-RateLimit-AppDay-Remaining / X-RateLimit-AppDay-Reset
    - (and potentially others like Orders)
    
    Note: Reset headers are expressed as seconds-until-reset, not epoch timestamps.
    
    Args:
        headers: Response headers dictionary
        
    Returns:
        Dictionary with parsed rate limit info organized by dimension
        
    Example output:
        {
            "session": {"remaining": 115, "reset": 45},
            "appday": {"remaining": 9500, "reset": 3600},
            "raw_headers": {...}
        }
    """
    rate_limits: Dict[str, Any] = {"raw_headers": {}}
    
    # Find all X-RateLimit-* headers (case-insensitive)
    rate_limit_pattern = re.compile(r'^X-RateLimit-(.+)', re.IGNORECASE)
    
    for header_name, header_value in headers.items():
        match = rate_limit_pattern.match(header_name)
        if match:
            # Store raw header
            rate_limits["raw_headers"][header_name] = header_value
            
            # Parse the header: e.g., "Session-Remaining" → dimension="session", field="remaining"
            parts = match.group(1).split('-')
            if len(parts) >= 2:
                dimension = parts[0].lower()  # e.g., "session", "appday"
                field = '-'.join(parts[1:]).lower()  # e.g., "remaining", "reset"
                
                # Initialize dimension dict if needed
                if dimension not in rate_limits:
                    rate_limits[dimension] = {}
                
                # Try to parse as integer
                try:
                    rate_limits[dimension][field] = int(header_value)
                except ValueError:
                    rate_limits[dimension][field] = header_value
    
    return rate_limits


def get_best_retry_delay(
    response: Optional[requests.Response], 
    rate_limit_info: Dict[str, Any],
    attempt: int
) -> float:
    """
    Determine the best retry delay based on headers and backoff.
    
    Priority:
    1. Retry-After header (if present)
    2. Best available X-RateLimit-*-Reset header
    3. Exponential backoff with jitter
    
    Args:
        response: The HTTP response (may be None for connection errors)
        rate_limit_info: Parsed rate limit headers
        attempt: Current retry attempt number (0-indexed)
        
    Returns:
        Delay in seconds before retrying
    """
    # 1. Check Retry-After header first (highest priority)
    if response is not None:
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass  # Not a valid number, continue to other methods
    
    # 2. Look for any reset header in rate limit info
    min_reset = None
    for dimension, info in rate_limit_info.items():
        if dimension == "raw_headers":
            continue
        if isinstance(info, dict) and 'reset' in info:
            reset_value = info['reset']
            if isinstance(reset_value, (int, float)):
                if min_reset is None or reset_value < min_reset:
                    min_reset = reset_value
    
    if min_reset is not None and min_reset > 0:
        # Add small buffer to ensure limit has reset
        return min_reset + 1.0
    
    # 3. Fall back to exponential backoff with jitter
    base_delay = BASE_BACKOFF_SECONDS * (2 ** attempt)
    jitter = random.uniform(-JITTER_FACTOR, JITTER_FACTOR) * base_delay
    delay = min(base_delay + jitter, MAX_BACKOFF_SECONDS)
    
    return max(delay, 1.0)  # Minimum 1 second


def log_rate_limit_info(rate_limit_info: Dict[str, Any], context: str = ""):
    """
    Log rate limit information at appropriate levels.
    
    Args:
        rate_limit_info: Parsed rate limit headers
        context: Additional context string for the log message
    """
    if not rate_limit_info or not rate_limit_info.get("raw_headers"):
        return
    
    parts = [f"Rate limit info{' (' + context + ')' if context else ''}:"]
    
    for dimension, info in rate_limit_info.items():
        if dimension == "raw_headers":
            continue
        if isinstance(info, dict):
            remaining = info.get('remaining', 'N/A')
            reset = info.get('reset', 'N/A')
            parts.append(f"{dimension}: {remaining} remaining, reset in {reset}s")
    
    if len(parts) > 1:
        logger.debug(" | ".join(parts))


# =============================================================================
# Main Client Class
# =============================================================================

class SaxoClient:
    """
    REST client for Saxo Bank OpenAPI with rate limiting and retry support.
    
    Features:
    - Automatic authentication via OAuth
    - Rate limit header parsing and logging
    - Exponential backoff with jitter for retries
    - Respects Retry-After header
    
    Example:
        client = SaxoClient()
        
        # Simple GET
        accounts = client.get("/port/v1/accounts/me")
        
        # GET with headers returned (for rate limit awareness)
        data, rate_info = client.get_with_headers("/trade/v1/infoprices/list", params={...})
    """
    
    def __init__(self):
        """
        Initialize Saxo client with credentials from environment.
        
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
        
        # Track last request times for rate limiting
        self._last_request_times: Dict[str, float] = {}
    
    @property
    def headers(self) -> Dict[str, str]:
        """
        Generate headers for API requests.
        
        Returns:
            Dictionary of HTTP headers including Authorization.
        """
        return {
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json",
        }
    
    def _enforce_min_interval(self, endpoint_type: str = "default"):
        """
        Enforce minimum polling interval for an endpoint type.
        
        Args:
            endpoint_type: Type of endpoint ("quotes", "bars", or "default")
        """
        min_intervals = {
            "quotes": MIN_QUOTES_POLL_SECONDS,
            "bars": MIN_BARS_POLL_SECONDS,
            "default": 1.0
        }
        
        min_interval = min_intervals.get(endpoint_type, 1.0)
        last_time = self._last_request_times.get(endpoint_type, 0)
        elapsed = time.time() - last_time
        
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s before {endpoint_type} request")
            time.sleep(sleep_time)
        
        self._last_request_times[endpoint_type] = time.time()
    
    def get_with_headers(
        self, 
        path: str, 
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        endpoint_type: str = "default",
        max_retries: int = MAX_RETRIES
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Make GET request to Saxo API, returning both data and rate limit info.
        
        Args:
            path: API endpoint path
            params: Optional query parameters
            headers: Optional HTTP headers to merge with default headers
            endpoint_type: Type of endpoint for rate limiting ("quotes", "bars", "default")
            max_retries: Maximum number of retries for transient errors
        
        Returns:
            Tuple of (JSON response dict, rate limit info dict)
        
        Raises:
            SaxoRateLimitError: If rate limit exceeded and all retries exhausted
            SaxoAPIError: If request fails or returns error status
            SaxoAuthenticationError: For 401/403 errors
        """
        self._enforce_min_interval(endpoint_type)
        
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None
        last_rate_info: Dict[str, Any] = {}
        
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        for attempt in range(max_retries + 1):
            try:
                response = requests.get(
                    url,
                    headers=request_headers,
                    params=params,
                    timeout=30
                )
                
                # Parse rate limit headers on every response
                rate_limit_info = parse_rate_limit_headers(dict(response.headers))
                last_rate_info = rate_limit_info
                log_rate_limit_info(rate_limit_info, f"GET {path}")
                
                # Check for success
                if response.status_code < 400:
                    return response.json(), rate_limit_info
                
                # Handle rate limit (429)
                if response.status_code == 429:
                    error_body = self._try_parse_json_error(response)
                    delay = get_best_retry_delay(response, rate_limit_info, attempt)
                    
                    logger.warning(
                        f"Rate limit hit (429) on GET {path}. "
                        f"Error: {error_body}. "
                        f"Attempt {attempt + 1}/{max_retries + 1}. "
                        f"Waiting {delay:.2f}s before retry."
                    )
                    
                    if attempt < max_retries:
                        time.sleep(delay)
                        continue
                    else:
                        raise SaxoRateLimitError(
                            f"Rate limit exceeded on GET {path} after {max_retries + 1} attempts",
                            retry_after=int(delay),
                            rate_limit_info=rate_limit_info
                        )
                
                # Handle non-retryable errors
                if response.status_code in NON_RETRYABLE_STATUS_CODES:
                    self._handle_http_error_response(response, path, rate_limit_info)
                
                # Handle retryable server errors (5xx)
                if response.status_code in RETRYABLE_STATUS_CODES:
                    delay = get_best_retry_delay(response, rate_limit_info, attempt)
                    logger.warning(
                        f"Server error ({response.status_code}) on GET {path}. "
                        f"Attempt {attempt + 1}/{max_retries + 1}. "
                        f"Waiting {delay:.2f}s before retry."
                    )
                    
                    if attempt < max_retries:
                        time.sleep(delay)
                        continue
                
                # Other errors - don't retry
                self._handle_http_error_response(response, path, rate_limit_info)
                
            except requests.exceptions.Timeout as e:
                last_error = e
                delay = get_best_retry_delay(response if 'response' in locals() else None, 
                                            last_rate_info, attempt)
                logger.warning(
                    f"Timeout on GET {path}. "
                    f"Attempt {attempt + 1}/{max_retries + 1}. "
                    f"Waiting {delay:.2f}s before retry."
                )
                
                if attempt < max_retries:
                    time.sleep(delay)
                    continue
                    
            except requests.exceptions.ConnectionError as e:
                last_error = e
                delay = get_best_retry_delay(None, last_rate_info, attempt)
                logger.warning(
                    f"Connection error on GET {path}: {e}. "
                    f"Attempt {attempt + 1}/{max_retries + 1}. "
                    f"Waiting {delay:.2f}s before retry."
                )
                
                if attempt < max_retries:
                    time.sleep(delay)
                    continue
            
            except (SaxoAuthenticationError, SaxoAPIError):
                # Don't retry auth or API errors
                raise
            
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error on GET {path}: {e}")
                raise SaxoAPIError(f"Request failed: {str(e)}")
        
        # All retries exhausted
        if last_error:
            raise SaxoAPIError(f"GET {path} failed after {max_retries + 1} attempts: {last_error}")
        
        raise SaxoAPIError(f"GET {path} failed after {max_retries + 1} attempts")
    
    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make GET request to Saxo API.
        
        Args:
            path: API endpoint path
            params: Optional query parameters
            headers: Optional HTTP headers
        
        Returns:
            JSON response as dictionary
        
        Raises:
            SaxoAPIError: If request fails or returns error status
        """
        data, _ = self.get_with_headers(path, params, headers=headers)
        return data
    
    def post(
        self,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make POST request to Saxo API.
        
        Args:
            path: API endpoint path
            json_body: Optional JSON body for request
            params: Optional query parameters
            headers: Optional HTTP headers
        
        Returns:
            JSON response as dictionary
        
        Raises:
            SaxoAPIError: If request fails or returns error status
        """
        url = f"{self.base_url}{path}"
        
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        try:
            response = requests.post(
                url,
                headers=request_headers,
                json=json_body,
                params=params,
                timeout=30
            )
            
            # Parse and log rate limit headers
            rate_limit_info = parse_rate_limit_headers(dict(response.headers))
            log_rate_limit_info(rate_limit_info, f"POST {path}")
            
            response.raise_for_status()
            
            # Some endpoints return empty response
            if response.text:
                return response.json()
            return {}
        
        except requests.exceptions.HTTPError as e:
            rate_info = parse_rate_limit_headers(dict(response.headers)) if response else {}
            self._handle_http_error(e, response, rate_info)
        except requests.exceptions.Timeout:
            raise SaxoAPIError(f"Request timeout for POST {path}")
        except requests.exceptions.RequestException as e:
            raise SaxoAPIError(f"Request failed: {str(e)}")
        except ValueError as e:
            raise SaxoAPIError(f"Invalid JSON response: {str(e)}")
    
    def delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make DELETE request to Saxo API.
        
        Args:
            path: API endpoint path
            params: Optional query parameters
            headers: Optional HTTP headers
        
        Returns:
            JSON response as dictionary
        
        Raises:
            SaxoAPIError: If request fails or returns error status
        """
        url = f"{self.base_url}{path}"
        
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        try:
            response = requests.delete(
                url,
                headers=request_headers,
                params=params,
                timeout=30
            )
            
            # Parse and log rate limit headers
            rate_limit_info = parse_rate_limit_headers(dict(response.headers))
            log_rate_limit_info(rate_limit_info, f"DELETE {path}")
            
            response.raise_for_status()
            
            if response.text:
                return response.json()
            return {}
        
        except requests.exceptions.HTTPError as e:
            rate_info = parse_rate_limit_headers(dict(response.headers)) if response else {}
            self._handle_http_error(e, response, rate_info)
        except requests.exceptions.Timeout:
            raise SaxoAPIError(f"Request timeout for DELETE {path}")
        except requests.exceptions.RequestException as e:
            raise SaxoAPIError(f"Request failed: {str(e)}")
        except ValueError as e:
            raise SaxoAPIError(f"Invalid JSON response: {str(e)}")
    
    def _try_parse_json_error(self, response: requests.Response) -> Dict[str, Any]:
        """Try to parse JSON error body from response."""
        try:
            return response.json()
        except:
            return {"text": response.text}
    
    def _handle_http_error_response(
        self, 
        response: requests.Response, 
        path: str,
        rate_limit_info: Dict[str, Any]
    ):
        """Handle HTTP error response with detailed error messages."""
        status_code = response.status_code
        error_body = self._try_parse_json_error(response)
        error_msg = error_body.get("Message", error_body.get("text", str(error_body)))
        error_code = error_body.get("ErrorCode", error_body.get("Code"))
        
        # Handle authentication errors
        if status_code in [401, 403]:
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
            f"API request failed (HTTP {status_code}): {error_msg}",
            status_code=status_code,
            error_code=error_code,
            rate_limit_info=rate_limit_info
        )
    
    def _handle_http_error(
        self, 
        error: requests.exceptions.HTTPError, 
        response: requests.Response,
        rate_limit_info: Optional[Dict[str, Any]] = None
    ):
        """Legacy error handler for backwards compatibility."""
        self._handle_http_error_response(response, "", rate_limit_info or {})
    
    def is_sim_environment(self) -> bool:
        """Check if client is configured for SIM environment."""
        if self.env == "SIM":
            return True
        if self.base_url and "/sim/" in self.base_url.lower():
            return True
        return False


def create_client() -> SaxoClient:
    """
    Create and return a configured SaxoClient instance.
    
    Returns:
        Configured SaxoClient
    
    Raises:
        SaxoAuthenticationError: If credentials are missing
    """
    return SaxoClient()
