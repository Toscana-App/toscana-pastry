"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { fetchCart } from "@/services/cartService";

/**
 * Total de unidades del carrito del usuario (badge de la navbar).
 *
 * El carrito vive en el backend (RF-P11-03); no hay contexto global, así
 * este hook lee `GET /cart` al montar y re-filtra cuando el carrito cambia
 * (evento `cart:changed`, despachado por cartService tras add/remove/coupon).
 */
export function useCartCount(): number {
  const { isAuthenticated } = useAuth();
  const [count, setCount] = useState(0);

  // Al salir de sesión el badge vuelve a 0, ajustado durante el render
  // (patrón que React recomienda al cambiar un prop); el effect de abajo
  // solo maneja el sistema externo (fetch + evento cart:changed).
  const [lastAuth, setLastAuth] = useState(isAuthenticated);
  if (isAuthenticated !== lastAuth) {
    setLastAuth(isAuthenticated);
    if (!isAuthenticated) setCount(0);
  }

  useEffect(() => {
    if (!isAuthenticated) return;
    let active = true;
    const load = () => {
      fetchCart()
        .then((cart) => {
          if (!active) return;
          setCount(cart.items.reduce((sum, item) => sum + item.qty, 0));
        })
        .catch(() => {
          /* sin sesión activa o API caído: el badge queda en 0 */
        });
    };
    load();
    window.addEventListener("cart:changed", load);
    return () => {
      active = false;
      window.removeEventListener("cart:changed", load);
    };
  }, [isAuthenticated]);

  return count;
}
