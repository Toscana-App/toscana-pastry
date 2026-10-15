from abc import ABC, abstractmethod
from typing import Optional, List
from domain.models import User, UserRole, BusinessSettings

class UserRepository(ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    async def get_by_google_id(self, google_id: str) -> Optional[User]:
        pass

    @abstractmethod
    async def save(self, user: User) -> User:
        pass

    @abstractmethod
    async def get_all_by_role(self, role: UserRole) -> List[User]:
        pass

    @abstractmethod
    async def get_all(self) -> List[User]:
        pass


class SettingsRepository(ABC):
    @abstractmethod
    async def get(self) -> Optional[BusinessSettings]:
        pass

    @abstractmethod
    async def save(self, settings: BusinessSettings) -> BusinessSettings:
        pass
