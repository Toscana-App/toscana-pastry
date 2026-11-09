"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { fetchCart } from "@/services/cartService";

export function useCartCount(): number {
  const { isAuthenticated } = useAuth();
  const [count, setCount] = useState(0);

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
