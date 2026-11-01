"""Reglas del libro de direcciones (RF-P11-09, C2): max 5, exactly-one-default."""
import datetime

import pytest

from domain.customer_address import (
    MAX_ADDRESSES_PER_CUSTOMER,
    AddressLimitExceeded,
    CannotRemoveOnlyAddress,
    CannotUnsetDefault,
    CustomerAddress,
    add_address,
    apply_changes,
    default_to_demote,
    remove_address,
)


def _addr(street="Calle 1", default=False, minutes=0, **kw):
    ts = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC) + datetime.timedelta(
        minutes=minutes
    )
    return CustomerAddress(
        street_line_1=street, is_default=default, created_at=ts, **kw
    )


def test_first_address_becomes_default():
    assert add_address([], _addr()).is_default is True


def test_next_address_is_not_default():
    assert add_address([_addr(default=True)], _addr("Otra")).is_default is False


def test_sixth_address_rejected():
    existing = [_addr(f"C{i}", default=i == 0) for i in range(MAX_ADDRESSES_PER_CUSTOMER)]
    with pytest.raises(AddressLimitExceeded):
        add_address(existing, _addr("Sexta"))


def test_fifth_address_allowed():
    existing = [_addr(f"C{i}", default=i == 0) for i in range(MAX_ADDRESSES_PER_CUSTOMER - 1)]
    assert add_address(existing, _addr("Quinta")).street_line_1 == "Quinta"


def test_unset_default_on_current_default_rejected():
    with pytest.raises(CannotUnsetDefault):
        apply_changes(_addr(default=True), {}, set_default=False)


def test_unset_default_on_non_default_is_noop():
    assert apply_changes(_addr(), {}, set_default=False).is_default is False


def test_set_default_true_promotes():
    assert apply_changes(_addr(), {}, set_default=True).is_default is True


def test_changes_none_clears_optional_field():
    updated = apply_changes(_addr(phone="123"), {"phone": None})
    assert updated.phone is None


def test_changes_validate_fields():
    with pytest.raises(ValueError):
        apply_changes(_addr(), {"street_line_1": " "})


def test_default_to_demote_excludes_promoted():
    a, b = _addr("A", default=True), _addr("B")
    assert default_to_demote([a, b], b.id) == [a.id]
    assert default_to_demote([a, b], a.id) == []


def test_remove_only_address_rejected():
    only = _addr(default=True)
    with pytest.raises(CannotRemoveOnlyAddress):
        remove_address([only], only.id)


def test_remove_non_default_promotes_nobody():
    a, b = _addr("A", default=True), _addr("B", minutes=1)
    assert remove_address([a, b], b.id) is None


def test_remove_default_promotes_oldest_remaining():
    a = _addr("A", default=True)
    b, c = _addr("B", minutes=1), _addr("C", minutes=2)
    assert remove_address([a, b, c], a.id) == b.id
