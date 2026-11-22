"""Google Sign-In (GIS ID-token) domain logic.

Security rules implemented here (see docs/specs/p01_auth.md RF-P1-08..P1-12,
RNF-P1-06, RNF-P1-07):

- The ID token is verified exactly once, via google-auth against Google's
  JWKS (signature, aud, iss, exp). The credential is never stored or logged.
- ``email_verified == true`` is mandatory.
- ``google_authoritative`` marks addresses Google is authoritative for
  (Gmail or ``hd`` Workspace claim). Per RF-P1-10 the app NEVER auto-links
  an existing account by email; this value is only used to decide whether a
  newly created account can be considered email-verified.
- Login-CSRF (JS/JSON flow only): the decision is pure and fail-closed, and
  it must run BEFORE any token verification.
"""

from typing import Any, Dict, Optional, Sequence

from google.auth.transport import requests as google_transport_requests
from google.oauth2.id_token import verify_oauth2_token


class GoogleSignInNotConfiguredError(Exception):
    """GOOGLE_CLIENT_ID is empty: the feature is intentionally disabled."""


class InvalidGoogleTokenError(ValueError):
    """The Google ID token failed verification or validation."""


# One shared transport instance (connection pooling); safe to reuse across
# verifications. The credential is only ever passed to verify_oauth2_token.
_transport = google_transport_requests.Request()


def google_authoritative(payload: Dict[str, Any]) -> bool:
    """True when Google is authoritative for the address (Gmail or ``hd``).

    Requires ``email_verified``: a Workspace-issued token for an unverified
    address is not proof of current ownership.
    """
    if not payload.get("email_verified"):
        return False
    email = (payload.get("email") or "").lower()
    return email.endswith("@gmail.com") or bool(payload.get("hd"))


def verify_google_id_token(credential: str, client_id: str) -> Dict[str, Any]:
    """Verify a Google ID token and return its payload.

    Raises:
        GoogleSignInNotConfiguredError: ``client_id`` is empty.
        InvalidGoogleTokenError: signature/aud/iss/exp failure, missing
            ``sub``/``email``, or ``email_verified`` is not true.
    """
    if not client_id:
        raise GoogleSignInNotConfiguredError(
            "Google Sign-In is not configured (GOOGLE_CLIENT_ID is empty)"
        )
    try:
        payload = dict(verify_oauth2_token(credential, _transport, client_id))
    except GoogleSignInNotConfiguredError:
        raise
    except Exception as exc:  # google-auth raises a mix of typed exceptions
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
    """Login-CSRF decision for the JSON (JS fetch) delivery flow.

    Fail-closed: only ``Sec-Fetch-Site: same-origin`` (browser-set,
    unforgeable) passes outright. ``cross-site`` / ``same-site`` / ``none``
    are rejected. A missing ``Sec-Fetch-Site`` is NOT same-origin; in that
    case an exact, allowlisted ``Origin`` is the only fallback.
    """
    if sec_fetch_site == "same-origin":
        return True
    if sec_fetch_site in ("cross-site", "same-site", "none"):
        return False
    if sec_fetch_site is None:
        return origin is not None and origin in allowed_origins
    return False
