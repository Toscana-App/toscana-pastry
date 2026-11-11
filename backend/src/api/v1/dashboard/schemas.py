import datetime

from pydantic import BaseModel

from api.v1.money import Money
from domain.dashboard import Granularity


class SummaryResponse(BaseModel):

    date_from: datetime.date
    date_to: datetime.date
    revenue: Money
    orders_count: int
    average_ticket: Money
    paid_revenue: Money
    pending_revenue: Money
    cancelled_count: int


class SalesPointResponse(BaseModel):

    bucket: datetime.date
    revenue: Money
    orders_count: int


class SalesSeriesResponse(BaseModel):

    date_from: datetime.date
    date_to: datetime.date
    granularity: Granularity
    points: list[SalesPointResponse]


class StatusCountResponse(BaseModel):

    status: str
    orders_count: int


class OrdersByStatusResponse(BaseModel):

    date_from: datetime.date
    date_to: datetime.date
    items: list[StatusCountResponse]


class TopProductResponse(BaseModel):

    product_id: str
    product_name: str
    quantity: int
    revenue: Money


class TopProductsResponse(BaseModel):

    date_from: datetime.date
    date_to: datetime.date
    items: list[TopProductResponse]


class PaymentSplitResponse(BaseModel):

    payment_method: str
    orders_count: int
    revenue: Money


class PaymentMethodsResponse(BaseModel):

    date_from: datetime.date
    date_to: datetime.date
    items: list[PaymentSplitResponse]
