from data.models import Base, CustomerORM, OrderORM


def test_order_customer_id_property_declares_foreign_key_to_customers_id():
    foreign_keys = OrderORM.customer_id.property.columns[0].foreign_keys
    assert len(foreign_keys) == 1
    target = next(iter(foreign_keys))
    assert target.column.table is CustomerORM.__table__
    assert target.column.table is Base.metadata.tables["customers"]
    assert target.column.name == "id"


def test_orders_and_customers_tables_are_in_metadata():
    assert "orders" in Base.metadata.tables
    assert "customers" in Base.metadata.tables
