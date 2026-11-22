"""Identity resolution for Google sign-in (RF-P1-09, RF-P1-10, RF-P1-11).

Three-way branch, keyed on ``sub`` (stored as ``google_id``), never on email:

1. A user with this ``google_id`` exists -> login (existing session flow).
2. The email matches an existing account without ``google_id`` -> ALWAYS the
   pending-link state. The account is never auto-linked on
   ``email_verified`` alone (RF-P1-10); the real link arrives with the email
   verification flow.
3. No match at all: creation is gated by the ``GOOGLE_AUTO_CREATE`` flag.
   When allowed the account is created (role defaults to customer); when not
   allowed (production) the caller gets the no-account state so the user is
   pointed at the purchase email instead (RF-P1-11).
"""

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from domain.models import User
from domain.repositories import UserRepository

SignInState = Literal["signed_in", "no_account", "link_pending"]


@dataclass(frozen=True)
class GoogleSignInOutcome:
    state: SignInState
    user: Optional[User] = None


class GoogleSignIn:
    def __init__(self, user_repository: UserRepository, auto_create: bool):
        self.user_repository = user_repository
        self.auto_create = auto_create

    async def execute(self, payload: Dict[str, Any]) -> GoogleSignInOutcome:
        google_id = payload["sub"]

        user = await self.user_repository.get_by_google_id(google_id)
        if user is not None:
            return GoogleSignInOutcome(state="signed_in", user=user)

        email = (payload.get("email") or "").strip().lower()
        if email:
            existing = await self.user_repository.get_by_email(email)
            if existing is not None:
                # Never auto-link: Google verifying the inbox once is not
                # proof that this person owns the local account. This also
                # covers an account already bound to a DIFFERENT google_id
                # (two Google accounts sharing one email): auto-creating
                # would violate the email uniqueness constraint.
                return GoogleSignInOutcome(state="link_pending", user=existing)

        if not self.auto_create:
            return GoogleSignInOutcome(state="no_account")

        user = User(email=email, google_id=google_id)
        await self.user_repository.save(user)
        return GoogleSignInOutcome(state="signed_in", user=user)
