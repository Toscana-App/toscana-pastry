"""Money contract at the API edge: integer cents only (str/float/bool -> 422)."""
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from api.v1.money import Money


class _Model(BaseModel):
    amount: Money


def test_int_cents_are_accepted():
    assert _Model(amount=310050).amount == 310050


def test_domain_decimal_is_converted_to_cents():
    assert _Model(amount=Decimal("3100.50")).amount == 310050


@pytest.mark.parametrize("bad", ["3100.50", "310050", 3100.5, 1.0, True, False, None])
def test_non_int_input_is_a_validation_error(bad):
    # ValidationError (not TypeError) is what FastAPI turns into a 422.
    with pytest.raises(ValidationError):
        _Model(amount=bad)
