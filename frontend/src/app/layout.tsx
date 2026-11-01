import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Provider } from "@/providers/ChakraProvider"
import { AuthProvider } from "@/contexts/AuthContext"
import { Navbar } from "@/components/layout/Navbar"
import { Toaster } from "@/lib/toaster"
import { AppGooeyToaster } from "@/components/ui/GoeyToasterClient"
import "goey-toast/styles.css"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
    <html lang="es" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="min-h-screen bg-white antialiased">
        <Provider>
          <AuthProvider>
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
