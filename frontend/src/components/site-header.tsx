"use client";

/**
 * Cabeçalho do site.
 *
 * Barra escura, marca à esquerda, busca no centro, conta à direita — a
 * estrutura que Sympla e Eventim usam. Nada de hero centralizado.
 *
 * Os links por papel são só NAVEGAÇÃO. Um cliente que digitar /organizador na
 * barra de endereços chega na tela — e recebe 403 da API, porque a autorização
 * está no backend.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { NOME_DO_PAPEL, useAuth } from "@/lib/auth";

export function SiteHeader() {
  const { user, ready, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [busca, setBusca] = useState("");
  const [menuAberto, setMenuAberto] = useState(false);

  // Lê o ?q= do endereço DEPOIS da hidratação, e não com useSearchParams().
  //
  // Motivo: um componente de cliente que chama useSearchParams() dentro de um
  // <Suspense> é renderizado pelo servidor por inteiro nas rotas dinâmicas, mas
  // o cliente começa pelo fallback do Suspense — servidor e cliente divergem e
  // o React aborta a hidratação (erro #418). Lendo no efeito, o primeiro render
  // é idêntico dos dois lados e o campo se preenche logo em seguida.
  useEffect(() => {
    if (pathname !== "/") return;
    setBusca(new URLSearchParams(window.location.search).get("q") ?? "");
  }, [pathname]);

  function buscar(e: React.FormEvent) {
    e.preventDefault();
    const termo = busca.trim();
    router.push(termo ? `/?q=${encodeURIComponent(termo)}` : "/");
  }

  // A portaria não procura evento: ela já escolheu a sessão e fica ali. Uma
  // busca de vitrine no topo dessa tela é ruído — e ocupa o espaço que numa
  // mão só, em pé, é o mais caro que existe.
  const naPortaria = pathname.startsWith("/portaria");

  return (
    <header className="sticky top-0 z-40 border-b border-brand-dark bg-brand text-white">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
        <Link
          href="/"
          className="shrink-0 text-[15px] font-bold tracking-tight text-white"
        >
          ingressa
          <span className="text-accent">.</span>
        </Link>

        {naPortaria && (
          <span className="text-sm font-semibold text-white/80">Portaria</span>
        )}

        {/* Não renderiza na portaria, em vez de esconder por CSS: o campo
            some do DOM e da árvore de acessibilidade, sem input órfão. */}
        {!naPortaria && (
        <form
          onSubmit={buscar}
          role="search"
          className="hidden min-w-0 flex-1 items-center sm:flex"
        >
          <label htmlFor="busca-topo" className="sr-only">
            Buscar eventos
          </label>
          <input
            id="busca-topo"
            type="search"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Busque por evento, filme, show ou local"
            className="h-9 w-full rounded-l border border-r-0 border-brand-dark bg-white
              px-3 text-sm text-ink placeholder:text-muted"
          />
          <button
            type="submit"
            className="h-9 shrink-0 rounded-r bg-accent px-4 text-sm font-semibold
              text-white hover:bg-accent-dark"
          >
            Buscar
          </button>
        </form>
        )}

        <nav className="ml-auto flex items-center gap-1 text-sm">
          {!ready ? (
            <span className="h-5 w-24 animate-pulse rounded bg-white/20" />
          ) : user ? (
            <>
              {user.role === "ORGANIZER" && (
                <HeaderLink href="/organizador">Meus eventos</HeaderLink>
              )}
              {user.role === "CUSTOMER" && (
                <HeaderLink href="/minha-conta">Meus ingressos</HeaderLink>
              )}
              {/* Sem link para a tela em que já se está: na portaria o rótulo
                  ao lado da marca já diz onde estamos. */}
              {user.role === "GATE" && !naPortaria && (
                <HeaderLink href="/portaria">Portaria</HeaderLink>
              )}

              <div className="relative">
                <button
                  onClick={() => setMenuAberto((v) => !v)}
                  aria-expanded={menuAberto}
                  aria-haspopup="menu"
                  className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-white/10"
                >
                  <span
                    aria-hidden="true"
                    className="grid size-7 place-items-center rounded-full bg-accent
                      text-xs font-bold text-white"
                  >
                    {user.full_name.charAt(0).toUpperCase()}
                  </span>
                  <span className="hidden max-w-28 truncate md:inline">
                    {user.full_name.split(" ")[0]}
                  </span>
                </button>

                {menuAberto && (
                  <>
                    {/* Camada invisível: clicar fora fecha o menu. */}
                    <button
                      aria-hidden="true"
                      tabIndex={-1}
                      onClick={() => setMenuAberto(false)}
                      className="fixed inset-0 z-10 cursor-default"
                    />
                    <div
                      role="menu"
                      className="absolute right-0 z-20 mt-1 w-56 rounded-card border
                        border-line bg-white py-1 text-body shadow-lg"
                    >
                      <div className="border-b border-line px-3 pb-2 pt-1">
                        <p className="truncate text-sm font-semibold text-ink">
                          {user.full_name}
                        </p>
                        <p className="truncate text-xs text-muted">{user.email}</p>
                        <p className="mt-1 text-xs font-medium text-brand">
                          {NOME_DO_PAPEL[user.role]}
                        </p>
                      </div>
                      <button
                        role="menuitem"
                        onClick={() => {
                          setMenuAberto(false);
                          logout();
                          router.push("/");
                        }}
                        className="w-full px-3 py-2 text-left text-sm hover:bg-canvas"
                      >
                        Sair
                      </button>
                    </div>
                  </>
                )}
              </div>
            </>
          ) : (
            <>
              <HeaderLink href="/entrar">Entrar</HeaderLink>
              <Link
                href="/criar-conta"
                className="rounded bg-accent px-3 py-1.5 font-semibold
                  text-white hover:bg-accent-dark"
              >
                Criar conta
              </Link>
            </>
          )}
        </nav>
      </div>

      {/* A busca some no topo em telas pequenas e reaparece numa linha própria.
          Na portaria ela não existe. */}
      {!naPortaria && (
      <div className="border-t border-brand-dark px-4 py-2 sm:hidden">
        <form onSubmit={buscar} role="search" className="flex">
          <label htmlFor="busca-mobile" className="sr-only">
            Buscar eventos
          </label>
          <input
            id="busca-mobile"
            type="search"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Busque por evento ou local"
            className="h-9 w-full rounded-l border border-r-0 border-brand-dark bg-white
              px-3 text-sm text-ink placeholder:text-muted"
          />
          <button
            type="submit"
            className="h-9 shrink-0 rounded-r bg-accent px-4 text-sm font-semibold text-white"
          >
            Buscar
          </button>
        </form>
      </div>
      )}
    </header>
  );
}

function HeaderLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="rounded px-3 py-1.5 hover:bg-white/10">
      {children}
    </Link>
  );
}
