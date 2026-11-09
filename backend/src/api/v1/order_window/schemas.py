
from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrderWindowResponse(BaseModel):

    model_config = ConfigDict(extra="forbid")

    open: bool
    reopens_at: Optional[dt.datetime]
    message: str


class OrderWindowUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    open: bool
    reopens_at: Optional[dt.datetime] = None
    message: str = Field(default="", max_length=200)
