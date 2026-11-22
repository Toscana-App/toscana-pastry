import type { Metadata } from "next";
import { Suspense } from "react";
import { SN_Pro } from "next/font/google";
import "./globals.css";
import { Link } from "@chakra-ui/react"
import { Provider } from "@/providers/ChakraProvider"
import { AuthProvider } from "@/contexts/AuthContext"
import { Navbar } from "@/components/layout/Navbar"
import { IconSprite } from "@/components/icons/sprite"
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
            <Link
              href="#main-content"
              position="absolute"
              left={4}
              top={4}
              zIndex="skipLink"
              px={4}
              py={2}
              rounded="md"
              bg="bg.panel"
              color="fg"
              fontWeight="semibold"
              transform="translateY(-200%)"
              _focusVisible={{ transform: "translateY(0)" }}
            >
              Saltar al contenido
            </Link>
            <Suspense fallback={null}>
              <Navbar />
            </Suspense>
            <main id="main-content">{children}</main>
            <AppGooeyToaster />
          </AuthProvider>
        </Provider>
      </body>
    </html>
  );
}
