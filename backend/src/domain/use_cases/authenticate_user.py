import uuid
from domain.models import User
from domain.repositories import UserRepository

class AuthenticateUser:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def execute(self, email: str = None, google_id: str = None) -> User:
        if not email and not google_id:
            raise ValueError("At least one authentication method must be provided (email or google_id).")

        if google_id:
            user = await self.user_repository.get_by_google_id(google_id)
            if not user:
                # Create new user if it's a new Google login
                user = User(id=str(uuid.uuid4()), email=email, google_id=google_id)
                await self.user_repository.save(user)
            return user

        if email:
            user = await self.user_repository.get_by_email(email)
            if not user:
                # For magic link, we'd create/update the user here
                user = User(id=str(uuid.uuid4()), email=email)
                await self.user_repository.save(user)
            return user
        
        raise ValueError("Invalid authentication parameters.")
