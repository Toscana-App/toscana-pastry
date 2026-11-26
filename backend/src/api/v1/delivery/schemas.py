from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel


class DeliveryLinkResponse(BaseModel):

    token: str
    url: str
    state: Literal["active", "delivered", "cancelled", "expired"]
    created_at: datetime.datetime | None = None


class PublicDeliveryResponse(BaseModel):

    state: Literal["active", "delivered", "cancelled", "expired"]
    order_code: str
    status: str
    status_label: str
    message: str
