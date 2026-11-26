import datetime
import uuid

import pytest

from domain.delivery import (
    DeliveryLink,
    DeliveryLinkNotFoundError,
    DeliveryLinkState,
    OrderNotDeliverableError,
)
from domain.use_cases.issue_delivery_link import IssueDeliveryLink
from domain.use_cases.resolve_delivery_link import ResolveDeliveryLink


class _Item:
    def __init__(self, name: str, qty: int):
        self.product_name = name
        self.qty = qty


class _Order:
    def __init__(self, status="confirmed", order_id="o1", items=()):
        self.status = status
        self.id = order_id
        self.items = list(items)


class FakeOrders:
    def __init__(self, orders):
        self._orders = {o.id: o for o in orders}

    async def get_full(self, order_id):
        return self._orders.get(order_id)


class FakeLinks:
    def __init__(self, order_code="#00001", order_status="confirmed"):
        self.order_code = order_code
        self.order_status = order_status
        self.stored: dict[str, DeliveryLink] = {}
        self.conflict = False
        self.created_tokens = []

    def _link(self, order_id, token):
        return DeliveryLink(
            token=token,
            order_id=order_id,
            order_code=self.order_code,
            order_status=self.order_status,
            created_at=datetime.datetime.now(datetime.UTC),
        )

    async def active_for_order(self, order_id):
        for link in self.stored.values():
            if link.order_id == order_id:
                return link
        return None

    async def find_by_token(self, token):
        return self.stored.get(token)

    async def create(self, order_id, token):
        self.created_tokens.append((order_id, token))
        if self.conflict:
            self.stored[token] = self._link(order_id, token)
            return False
        self.stored[token] = self._link(order_id, token)
        return True

    async def revoke_active(self, order_id, reason):
        for token, link in list(self.stored.items()):
            if link.order_id == order_id:
                self.stored[token] = DeliveryLink(
                    **{
                        **link.__dict__,
                        "revoked_at": datetime.datetime.now(datetime.UTC),
                        "revoked_reason": reason,
                    }
                )
                return 1
        return 0


async def test_issue_creates_a_uuid4_token_once():
    links = FakeLinks()
    link = await IssueDeliveryLink(FakeOrders([_Order()]), links).execute("o1")

    assert uuid.UUID(link.token).version == 4
    assert link.order_id == "o1"
    assert len(links.created_tokens) == 1


async def test_issue_is_idempotent():
    links = FakeLinks()
    use_case = IssueDeliveryLink(FakeOrders([_Order()]), links)

    first = await use_case.execute("o1")
    second = await use_case.execute("o1")

    assert first.token == second.token
    assert len(links.created_tokens) == 1


async def test_issue_rejects_terminal_order():
    links = FakeLinks()
    with pytest.raises(OrderNotDeliverableError):
        await IssueDeliveryLink(
            FakeOrders([_Order(status="delivered")]), links
        ).execute("o1")
    assert links.created_tokens == []


async def test_issue_rejects_cancelled_order():
    links = FakeLinks()
    with pytest.raises(OrderNotDeliverableError):
        await IssueDeliveryLink(
            FakeOrders([_Order(status="cancelled")]), links
        ).execute("o1")


async def test_issue_missing_order_is_not_found():
    with pytest.raises(DeliveryLinkNotFoundError):
        await IssueDeliveryLink(FakeOrders([]), FakeLinks()).execute("nope")


async def test_issue_concurrent_conflict_returns_the_winner_link():
    links = FakeLinks()
    links.conflict = True

    link = await IssueDeliveryLink(FakeOrders([_Order()]), links).execute("o1")

    assert link.token in links.stored


async def test_resolve_invalid_token_is_not_found():
    with pytest.raises(DeliveryLinkNotFoundError):
        await ResolveDeliveryLink(FakeLinks()).execute("no-es-uuid")


async def test_resolve_unknown_token_is_not_found():
    token = str(uuid.uuid4())
    with pytest.raises(DeliveryLinkNotFoundError):
        await ResolveDeliveryLink(FakeLinks()).execute(token)


async def test_resolve_active_link():
    links = FakeLinks(order_status="pending_delivery")
    token = str(uuid.uuid4())
    await links.create("o1", token)

    view = await ResolveDeliveryLink(links).execute(token)

    assert view.state is DeliveryLinkState.ACTIVE
    assert view.order_code == "#00001"


async def test_resolve_delivered_link_never_exposes_in_progress_data():
    links = FakeLinks(order_status="delivered")
    token = str(uuid.uuid4())
    await links.create("o1", token)

    view = await ResolveDeliveryLink(links).execute(token)

    assert view.state is DeliveryLinkState.DELIVERED
    assert view.message == "Su pedido ha sido entregado"
    assert view.status == "delivered"


async def test_resolve_uppercase_token_is_normalized():
    links = FakeLinks()
    token = str(uuid.uuid4())
    await links.create("o1", token)

    view = await ResolveDeliveryLink(links).execute(token.upper())

    assert view.state is DeliveryLinkState.ACTIVE


async def test_resolve_exposes_order_item_descriptions():
    links = FakeLinks(order_status="pending_delivery")
    orders = FakeOrders(
        [
            _Order(
                items=[_Item("Cheesecake", 2), _Item("Brownie de nuez", 1)]
            )
        ]
    )
    token = str(uuid.uuid4())
    await links.create("o1", token)

    view = await ResolveDeliveryLink(links, orders).execute(token)

    assert [(i.name, i.quantity) for i in view.items] == [
        ("Cheesecake", 2),
        ("Brownie de nuez", 1),
    ]


async def test_resolve_delivered_link_still_exposes_item_descriptions():
    links = FakeLinks(order_status="delivered")
    orders = FakeOrders([_Order(status="delivered", items=[_Item("Cheesecake", 2)])])
    token = str(uuid.uuid4())
    await links.create("o1", token)

    view = await ResolveDeliveryLink(links, orders).execute(token)

    assert view.state is DeliveryLinkState.DELIVERED
    assert [i.name for i in view.items] == ["Cheesecake"]


async def test_resolve_exposes_no_items_without_an_order_repository():
    links = FakeLinks()
    token = str(uuid.uuid4())
    await links.create("o1", token)

    view = await ResolveDeliveryLink(links).execute(token)

    assert view.items == ()
