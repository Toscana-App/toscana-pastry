from typing import Optional
from domain.models import User
from domain.repositories import UserRepository


class AuthenticateUser:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def execute(
        self, email: Optional[str] = None, google_id: Optional[str] = None
    ) -> User:
        if not email and not google_id:
            raise ValueError(
                "At least one authentication method must be provided (email or google_id)."
            )

        if google_id:
            user = await self.user_repository.get_by_google_id(google_id)
            if not user:
                user = User(email=email, google_id=google_id)
                await self.user_repository.save(user)
            return user

        user = await self.user_repository.get_by_email(email)
        if not user:
            user = User(email=email)
            await self.user_repository.save(user)
        return user
