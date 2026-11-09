
import pytest

from domain.lead import (
    ALLOWED_CUSTOMER_TYPES,
    Lead,
)


class TestLeadCreation:
    def test_default_read_is_false(self):
        lead = self._make()
        assert lead.read is False

    def test_all_required_fields_valid(self):
        lead = self._make(
            name="Juan Perez",
            email="juan@example.com",
            customer_type="consumer",
            message="Hola, quiero info",
        )
        assert lead.name == "Juan Perez"
        assert lead.email == "juan@example.com"
        assert lead.customer_type == "consumer"
        assert lead.message == "Hola, quiero info"

    def test_business_requires_business_name(self):
        with pytest.raises(ValueError, match="business_name"):
            Lead(
                name="Empresa SA",
                email="empresa@example.com",
                customer_type="business",
                message="Consulta",
            )

    def test_business_with_business_name_is_valid(self):
        lead = Lead(
            name="Empresa SA",
            email="empresa@example.com",
            customer_type="business",
            business_name="Empresa SA",
            message="Consulta",
        )
        assert lead.business_name == "Empresa SA"

    def test_phone_is_optional(self):
        lead = self._make(phone=None)
        assert lead.phone is None

    def test_location_is_optional(self):
        lead = self._make(location=None)
        assert lead.location is None

    def test_ids_are_unique(self):
        ids = {self._make().id for _ in range(50)}
        assert len(ids) == 50

    @staticmethod
    def _make(**overrides):
        base = {
            "name": "Test User",
            "email": "test@example.com",
            "customer_type": "consumer",
            "message": "Hello",
        }
        base.update(overrides)
        return Lead(**base)


class TestLeadValidation:
    def test_blank_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            Lead(
                name="",
                email="a@b.com",
                customer_type="consumer",
                message="Hello",
            )

    def test_whitespace_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            Lead(
                name="   ",
                email="a@b.com",
                customer_type="consumer",
                message="Hello",
            )

    def test_blank_email_raises(self):
        with pytest.raises(ValueError, match="email"):
            Lead(
                name="User",
                email="",
                customer_type="consumer",
                message="Hello",
            )

    def test_invalid_customer_type_raises(self):
        with pytest.raises(ValueError, match="customer_type"):
            Lead(
                name="User",
                email="a@b.com",
                customer_type="invalid",
                message="Hello",
            )

    def test_blank_message_raises(self):
        with pytest.raises(ValueError, match="message"):
            Lead(
                name="User",
                email="a@b.com",
                customer_type="consumer",
                message="",
            )

    def test_stripped_name_is_persisted(self):
        lead = Lead(
            name="  Trimmed  ",
            email="a@b.com",
            customer_type="consumer",
            message="Hello",
        )
        assert lead.name == "Trimmed"


class TestAllowedCustomerTypes:
    def test_contains_consumer_and_business(self):
        assert "consumer" in ALLOWED_CUSTOMER_TYPES
        assert "business" in ALLOWED_CUSTOMER_TYPES
