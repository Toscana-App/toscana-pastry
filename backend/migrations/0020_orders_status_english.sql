-- 0020_orders_status_english: estados de pedido en inglés (O1 — 6 estados).
-- Las filas existentes guardan los valores en español legado; este script los
-- mapea a los valores de la maquina de estados (domain/order_states.py):
--   nuevo -> new · confirmado -> confirmed · entregado -> delivered ·
--   cancelado -> cancelled
-- Mapa puro, idempotente, sin logica de negocio. La columna no tiene CHECK
-- constraint, por lo que no hay restricciones que actualizar.
-- Fresh databases ya nacen con los valores en inglés (default "new" en
-- OrderORM); aplicar este script a bases creadas antes del cutover.

-- === upgrade (portable) ===
UPDATE orders SET status = 'new' WHERE status = 'nuevo';
UPDATE orders SET status = 'confirmed' WHERE status = 'confirmado';
UPDATE orders SET status = 'delivered' WHERE status = 'entregado';
UPDATE orders SET status = 'cancelled' WHERE status = 'cancelado';

-- === downgrade (parcial y LOSSY — ver nota) ===
-- Los valores 'preparing' y 'pending_delivery' no existen en el modelo
-- anterior: un downgrade solo es seguro sobre bases que nunca llegaron a
-- esos estados. En ese caso, el reverso exacto es:
-- UPDATE orders SET status = 'nuevo' WHERE status = 'new';
-- UPDATE orders SET status = 'confirmado' WHERE status = 'confirmed';
-- UPDATE orders SET status = 'entregado' WHERE status = 'delivered';
-- UPDATE orders SET status = 'cancelado' WHERE status = 'cancelled';
