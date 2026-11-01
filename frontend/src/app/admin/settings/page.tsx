import type { Metadata } from "next";
import { SettingsPage } from "@/modules/settings/components/SettingsPage";

export const metadata: Metadata = {
  title: "Configuración",
};

export default function AdminSettingsRoute() {
  return <SettingsPage />;
}
