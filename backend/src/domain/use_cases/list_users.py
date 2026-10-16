from typing import List
from domain.models import User
from domain.repositories import UserRepository


class ListUsers:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def execute(self) -> List[User]:
        return await self.user_repository.get_all()
