
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

@dataclass
class User:
    email: str
    google_id: Optional[str] = None
    id: UUID = None
    created_at: datetime = None

    def __post_init__(self):
        if self.id is None:
            self.id = uuid4()
        if self.created_at is None:
            self.created_at = datetime.utcnow()
