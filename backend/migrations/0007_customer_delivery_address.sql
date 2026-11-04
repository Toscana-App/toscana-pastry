-- 0007: delivery_address (RF-P7-06/07).
-- DBs nuevas la reciben de Base.metadata.create_all; este script es
-- para las existentes (aplicar en el orden 0001..0007).

ALTER TABLE customers ADD COLUMN delivery_address VARCHAR(500);
ALTER TABLE budgets ADD COLUMN delivery_address VARCHAR(500);
