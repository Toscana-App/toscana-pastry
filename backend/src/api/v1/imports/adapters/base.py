from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession


class ImportAdapter(ABC):
    entity: str = ""

    inserts_on_confirm: bool = True

    confirm_message: str = ""

    example_rows: Sequence[dict[str, str]] = ()

    @property
    @abstractmethod
    def columns(self) -> list[str]:
        pass

    def template(self) -> str:
        header = ";".join(self.columns)
        lines = [header]
        for example in self.example_rows:
            lines.append(";".join(str(example.get(col, "")) for col in self.columns))
        return "\n".join(lines) + "\n"

    @abstractmethod
    def validate_row(self, row: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
        pass

    @abstractmethod
    async def find_duplicate(
        self, session: AsyncSession, data: dict[str, Any]
    ) -> str | None:
        pass

    @abstractmethod
    async def insert(self, session: AsyncSession, data: dict[str, Any]) -> None:
        pass
