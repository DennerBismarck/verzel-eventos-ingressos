import type { Metadata } from "next";
import Link from "next/link";

import { SiteHeader } from "@/components/site-header";
import { AuthProvider } from "@/lib/auth";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ingressa — eventos, shows e filmes em cartaz",
    template: "%s · ingressa",
  },
  description:
    "Compre ingressos para shows e filmes em cartaz, com entrada por QR validado na portaria.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // lang correto importa pra leitor de tela e pra hifenização do browser.
    <html lang="pt-BR" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <AuthProvider>
          {/* Pular para o conteúdo: primeiro foco do teclado, some no mouse. */}
          <a
            href="#conteudo"
            className="sr-only rounded bg-ink px-4 py-2 text-white focus:not-sr-only
              focus:absolute focus:left-3 focus:top-3 focus:z-50"
          >
            Pular para o conteúdo
          </a>

          <SiteHeader />

          <main id="conteudo" className="flex-1">
            {children}
          </main>

          <footer className="mt-16 border-t border-line bg-white">
            <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
              <p>
                <strong className="font-semibold text-ink">ingressa</strong> — projeto
                de demonstração. Nenhuma cobrança é real.
              </p>
              <p className="flex gap-4">
                <Link href="/portaria" className="hover:text-brand">
                  Portaria
                </Link>
                <Link href="/organizador" className="hover:text-brand">
                  Organizadores
                </Link>
              </p>
            </div>
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
