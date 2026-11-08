
import datetime

DEFAULT_WINDOW_MESSAGE = ""
MAX_WINDOW_MESSAGE = 200


class OrderWindow:

    MAX_WINDOW_MESSAGE = 200

    def __init__(
        self,
        *,
        open: bool = True,
        reopens_at: datetime.datetime | None = None,
        message: str = DEFAULT_WINDOW_MESSAGE,
    ) -> None:
        if not open and reopens_at is None:
            raise ValueError(
                "order_window closed requires reopens_at"
            )
        if len(message) > self.MAX_WINDOW_MESSAGE:
            raise ValueError(
                f"message must be <= {self.MAX_WINDOW_MESSAGE} chars"
            )
        if reopens_at is not None and reopens_at.tzinfo is not None:
            reopens_at = reopens_at.replace(tzinfo=None)
        self.open = open
        self.reopens_at = reopens_at
        self.message = message

    def __repr__(self) -> str:
        return (
            f"OrderWindow(open={self.open}, "
            f"reopens_at={self.reopens_at}, "
            f"message={self.message!r})"
        )
