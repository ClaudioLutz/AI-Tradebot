"""
Saxo OpenAPI OAuth Token Manager
Handles OAuth Authorization Code Grant with automatic refresh token flow.
"""
import base64
import json
import os
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import load_dotenv

TOKEN_PATH = os.path.join(".secrets", "saxo_tokens.json")


def _ensure_secret_dir():
    """Create .secrets directory if it doesn't exist."""
    os.makedirs(".secrets", exist_ok=True)


def _basic_auth(client_id: str, client_secret: str) -> str:
    """Generate Basic Auth header for token requests."""
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _save(payload: dict) -> None:
    """Save tokens to JSON file."""
    _ensure_secret_dir()
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _load() -> dict | None:
    """Load tokens from JSON file."""
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def _token_request(auth_base: str, headers: dict, data: dict) -> dict:
    """
    Make token request to Saxo OAuth endpoint.
    
    Args:
        auth_base: Base URL for authentication (e.g., https://sim.logonvalidation.net)
        headers: HTTP headers including Authorization
        data: Form data for token request
    
    Returns:
        Token response with expiry timestamps added
    
    Raises:
        requests.HTTPError: If token request fails
    """
    token_url = auth_base.rstrip("/") + "/token"
    r = requests.post(token_url, headers=headers, data=data, timeout=30)
    r.raise_for_status()
    
    p = r.json()
    now = int(time.time())
    
    # Add expiry timestamps with 30-second buffer for safety
    p["access_token_expires_at"] = now + int(p.get("expires_in", 0)) - 30
    p["refresh_token_expires_at"] = now + int(p.get("refresh_token_expires_in", 0)) - 30
    
    return p


def interactive_login() -> dict:
    """
    Perform interactive OAuth login flow.
    
    Opens browser for user authorization, captures the authorization code,
    exchanges it for access and refresh tokens, and saves them.
    
    Returns:
        Token response containing access_token, refresh_token, etc.
    
    Raises:
        RuntimeError: If OAuth flow fails
        KeyError: If required environment variables are missing
    """
    load_dotenv()
    
    auth_base = os.getenv("SAXO_AUTH_BASE", "https://sim.logonvalidation.net")
    client_id = os.environ["SAXO_APP_KEY"]
    client_secret = os.environ["SAXO_APP_SECRET"]
    redirect_uri = os.environ["SAXO_REDIRECT_URI"]
    
    # Parse redirect URI to start local server
    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8765
    redirect_path = parsed.path or "/callback"
    
    class Handler(BaseHTTPRequestHandler):
        """HTTP handler for OAuth callback."""
        code = None
        error = None
        
        def do_GET(self):
            """Handle GET request from OAuth redirect."""
            qs = parse_qs(urlparse(self.path).query)
            
            # Check if this is the callback path
            if urlparse(self.path).path != redirect_path:
                self.send_response(404)
                self.end_headers()
                return
            
            # Extract authorization code or error
            Handler.code = (qs.get("code") or [None])[0]
            Handler.error = (qs.get("error") or [None])[0]
            
            # Send success response
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK. You can close this tab and return to the terminal.")
        
        def log_message(self, *_):
            """Suppress HTTP server logs."""
            return
    
    # Start local HTTP server for OAuth callback
    httpd = HTTPServer((host, port), Handler)
    
    # Build authorization URL
    authorize_url = auth_base.rstrip("/") + "/authorize?" + urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": "saxo",
    })
    
    print(f"Opening browser for Saxo authentication...")
    print(f"If browser doesn't open, visit: {authorize_url}")
    webbrowser.open(authorize_url)
    
    # Wait for OAuth callback
    while Handler.code is None and Handler.error is None:
        httpd.handle_request()
    
    # Check for OAuth errors
    if Handler.error:
        raise RuntimeError(f"OAuth error: {Handler.error}")
    
    # Exchange authorization code for tokens
    headers = {
        "Authorization": _basic_auth(client_id, client_secret),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "code": Handler.code,
        "redirect_uri": redirect_uri,
    }
    
    tokens = _token_request(auth_base, headers, data)
    _save(tokens)
    
    return tokens


def get_access_token() -> str:
    """
    Get valid access token, refreshing if necessary.
    
    This function:
    1. Checks if SAXO_ACCESS_TOKEN is set (manual mode) - returns it if present
    2. Otherwise loads stored OAuth tokens
    3. Refreshes access token if expired
    4. Returns valid access token
    
    Returns:
        Valid access token string
    
    Raises:
        RuntimeError: If no tokens available or required env vars missing
    """
    load_dotenv()
    
    # Manual mode: If SAXO_ACCESS_TOKEN exists in .env, use it
    manual = os.getenv("SAXO_ACCESS_TOKEN")
    if manual:
        return manual
    
    # OAuth mode: Load stored tokens
    tokens = _load()
    if not tokens:
        raise RuntimeError(
            "No stored OAuth tokens. Run: python scripts/saxo_login.py"
        )
    
    # Check if access token needs refresh
    now = int(time.time())
    if now >= int(tokens.get("access_token_expires_at", 0)):
        # Access token expired, refresh it
        auth_base = os.getenv("SAXO_AUTH_BASE", "https://sim.logonvalidation.net")
        client_id = os.environ["SAXO_APP_KEY"]
        client_secret = os.environ["SAXO_APP_SECRET"]
        redirect_uri = os.environ["SAXO_REDIRECT_URI"]
        
        headers = {
            "Authorization": _basic_auth(client_id, client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "redirect_uri": redirect_uri,
        }
        
        try:
            tokens = _token_request(auth_base, headers, data)
            _save(tokens)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [400, 401]:
                raise RuntimeError(
                    "Refresh token expired or invalid. Please login again: "
                    "python scripts/saxo_login.py"
                )
            raise
    
    return tokens["access_token"]


def has_oauth_tokens() -> bool:
    """
    Check if OAuth tokens are stored.
    
    Returns:
        True if token file exists, False otherwise
    """
    return os.path.exists(TOKEN_PATH)
