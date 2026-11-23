from typing import Any, Dict, Optional, Sequence

from google.auth.transport import requests as google_transport_requests
from google.oauth2.id_token import verify_oauth2_token


class GoogleSignInNotConfiguredError(Exception):
    pass


class InvalidGoogleTokenError(ValueError):
    pass


_transport = google_transport_requests.Request()


def verify_google_id_token(credential: str, client_id: str) -> Dict[str, Any]:
    if not client_id:
        raise GoogleSignInNotConfiguredError(
            "Google Sign-In is not configured (GOOGLE_CLIENT_ID is empty)"
        )
    try:
        payload = dict(verify_oauth2_token(credential, _transport, client_id))
    except Exception as exc:
        raise InvalidGoogleTokenError(str(exc)) from exc
    if not payload.get("sub"):
        raise InvalidGoogleTokenError("Missing 'sub' in payload")
    if not payload.get("email"):
        raise InvalidGoogleTokenError("Missing 'email' in payload")
    if not payload.get("email_verified"):
        raise InvalidGoogleTokenError("Google account email is not verified")
    return payload


def google_json_flow_csrf_trusted(
    sec_fetch_site: Optional[str],
    origin: Optional[str],
    allowed_origins: Sequence[str],
) -> bool:
    if sec_fetch_site == "same-origin":
        return True
    if sec_fetch_site in ("cross-site", "same-site", "none"):
        return False
    if sec_fetch_site is None:
        return origin is not None and origin in allowed_origins
    return False
