import type { Metadata } from "next";
import { SN_Pro } from "next/font/google";
import "./globals.css";
import { Provider } from "@/providers/ChakraProvider"
import { AuthProvider } from "@/contexts/AuthContext"
import { Navbar } from "@/components/layout/Navbar"
import { IconSprite } from "@/components/icons/sprite"
import { Toaster } from "@/lib/toaster"
import { AppGooeyToaster } from "@/components/ui/GoeyToasterClient"
import "goey-toast/styles.css"

const snPro = SN_Pro({
  variable: "--font-sn-pro",
  subsets: ["latin", "latin-ext"],
});

export const metadata: Metadata = {
  title: "Toscana Pastry",
  description: "Toscana Pastry — calculá costos, gestioná pedidos y enviá tus listas de precios.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className={snPro.variable} suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <Provider>
          <AuthProvider>
            <IconSprite />
            <Navbar />
            <main>{children}</main>
            <Toaster />
            <AppGooeyToaster />
          </AuthProvider>
        </Provider>
      </body>
    </html>
  );
}
