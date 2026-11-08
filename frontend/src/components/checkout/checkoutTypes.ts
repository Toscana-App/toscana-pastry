
import { DeliveryMode, PaymentMethod } from "@/types/orders";

export interface ContactData {
  name: string;
  phone: string;
  email: string;
}

export interface AddressSelection {
  addressId: string | null;
  line: string;
}

export interface DeliveryData {
  date: string;
  delivery_mode: DeliveryMode;
}

export interface PaymentData {
  payment_method: PaymentMethod;
}

export const STEP_TITLES = [
  "Contacto",
  "Dirección",
  "Entrega",
  "Pago",
  "Confirmar",
] as const;
