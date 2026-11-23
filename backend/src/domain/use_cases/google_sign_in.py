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
                return GoogleSignInOutcome(state="link_pending", user=existing)

        if not self.auto_create:
            return GoogleSignInOutcome(state="no_account")

        user = User(email=email, google_id=google_id)
        await self.user_repository.save(user)
        return GoogleSignInOutcome(state="signed_in", user=user)
