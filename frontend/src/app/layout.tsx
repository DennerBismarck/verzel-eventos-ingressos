import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Eventos e Ingressos",
  description:
    "Compre ingressos para shows e filmes em cartaz, com validação na portaria por QR.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // lang correto importa pra leitor de tela e pra hifenização do browser.
    <html
      lang="pt-BR"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
