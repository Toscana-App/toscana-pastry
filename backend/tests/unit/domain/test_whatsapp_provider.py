
import pytest

from domain.whatsapp_provider import (
    MockBusinessApiProvider,
    WaMeProvider,
    normalize_e164,
    wa_me_url,
)

PHONE_MESSAGE = "Hola Ana: torta $5000, sin gluten. Total: $15000"




@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+5491122334455", "+5491122334455"),
        ("5491122334455", "+5491122334455"),
        ("91122334455", "+5491122334455"),
        ("1122334455", "+541122334455"),
        ("005491122334455", "+5491122334455"),
        ("+54 9 11 2233-4455", "+5491122334455"),
    ],
)
def test_normalize_e164_valid(raw, expected):
    assert normalize_e164(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "123",
        "911223344551234567890",
        "abc",
    ],
)
def test_normalize_e164_invalid(raw):
    with pytest.raises(ValueError):
        normalize_e164(raw)




def test_wa_me_url_uses_normalized_phone_without_plus():
    url = wa_me_url("+5491122334455", "hola")
    assert url.startswith("https://wa.me/5491122334455?text=")


def test_wa_me_url_encodes_accents_and_symbols():
    url = wa_me_url("91122334455", PHONE_MESSAGE)
    assert "$" not in url.split("text=")[1]
    assert "%" in url.split("text=")[1]
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert query["text"] == [PHONE_MESSAGE]


def test_wa_me_url_rejects_invalid_phone():
    with pytest.raises(ValueError):
        wa_me_url("no-tel", "hola")




@pytest.mark.asyncio
async def test_wa_me_provider_returns_sent_with_url():
    provider = WaMeProvider()
    result = await provider.send("91122334455", "hola")
    assert result.provider == "wa_me"
    assert result.status == "sent"
    assert result.message_id is None
    assert result.url is not None
    assert result.url.startswith("https://wa.me/5491122334455")




@pytest.mark.asyncio
async def test_mock_business_provider_deterministic_message_id():
    provider = MockBusinessApiProvider()
    first = await provider.send("+5491122334455", "hola")
    second = await provider.send("+5491122334455", "hola")
    assert first.message_id is not None
    assert first.message_id == second.message_id
    assert first.provider == "business_api"
    assert first.status == "sent"
    assert first.url is None


@pytest.mark.asyncio
async def test_mock_business_provider_different_message_different_id():
    provider = MockBusinessApiProvider()
    a = await provider.send("+5491122334455", "hola")
    b = await provider.send("+5491122334455", "adios")
    assert a.message_id != b.message_id
