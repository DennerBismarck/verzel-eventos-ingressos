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
            <div className="mx-auto max-w-6xl px-4 py-8">
              <div className="flex flex-col gap-2 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
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

              {/*
                Atribuição EXIGIDA pelos termos de uso da API do TMDb: o aviso
                com esta redação e o logo. Não é cortesia — é condição para usar
                o catálogo deles.
              */}
              <div className="mt-6 flex flex-col gap-3 border-t border-line pt-6 sm:flex-row sm:items-center">
                <a
                  href="https://www.themoviedb.org/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src="/tmdb.svg"
                    alt="The Movie Database (TMDB)"
                    width={128}
                    height={17}
                    className="h-4 w-auto"
                  />
                </a>
                <p className="text-xs text-muted">
                  Este produto usa a API do TMDB, mas não é endossado nem certificado
                  pelo TMDB. Dados de shows fornecidos pela{" "}
                  <a
                    href="https://developer.ticketmaster.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline hover:text-brand"
                  >
                    Ticketmaster Discovery API
                  </a>
                  .
                </p>
              </div>
            </div>
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
