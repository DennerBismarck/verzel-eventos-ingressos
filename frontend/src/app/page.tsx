"use client";

/**
 * Vitrine.
 *
 * Componente de cliente porque a busca e os filtros são interativos e a API
 * está em outro domínio. Renderizar no servidor daria SEO melhor, mas exigiria
 * o backend acordado a cada request — e a Render no plano free hiberna, o que
 * transformaria a home num cold start de 50s.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { EventCard, EventCardSkeleton } from "@/components/event-card";
import { Alert, Button, EmptyState } from "@/components/ui";
import { api } from "@/lib/api";
import { dateParts, preco } from "@/lib/format";
import type { EventKind, Page, PublicEvent } from "@/lib/types";

const FILTROS: { valor: EventKind | ""; rotulo: string }[] = [
  { valor: "", rotulo: "Tudo" },
  { valor: "GA", rotulo: "Pista" },
  { valor: "SEATED", rotulo: "Lugar marcado" },
];

export default function Home() {
  // useSearchParams obriga a fronteira de Suspense: a query string só existe em
  // tempo de request, então o Next precisa saber o que desenhar enquanto isso.
  return (
    <Suspense fallback={<VitrineCarregando />}>
      <Vitrine />
    </Suspense>
  );
}

function VitrineCarregando() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <Grade>
        {Array.from({ length: 10 }).map((_, i) => (
          <EventCardSkeleton key={i} />
        ))}
      </Grade>
    </div>
  );
}

function Vitrine() {
  const params = useSearchParams();
  const q = params.get("q") ?? "";

  const [kind, setKind] = useState<EventKind | "">("");
  const [dados, setDados] = useState<Page<PublicEvent> | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  /**
   * Número do pedido em curso.
   *
   * Sem isto, duas buscas no ar ao mesmo tempo entram numa corrida e QUEM
   * RESPONDE POR ÚLTIMO vence — mesmo sendo a mais antiga. Foi visto no log do
   * servidor: o pedido sem filtro voltou depois do `?kind=SEATED` e reescreveu
   * a lista, deixando a tela com todos os eventos e o chip "Lugar marcado"
   * marcado. Acontece sempre que se troca o filtro antes de a lista anterior
   * chegar — trivial numa conexão de celular.
   *
   * useRef e não useState: mudar o número não pode disparar render, e o valor
   * precisa ser lido DEPOIS do await, já com o valor mais recente.
   */
  const pedidoAtual = useRef(0);

  const carregar = useCallback(async () => {
    const meuPedido = ++pedidoAtual.current;
    setCarregando(true);
    setErro(null);
    try {
      const busca = new URLSearchParams();
      if (q) busca.set("q", q);
      if (kind) busca.set("kind", kind);
      const resposta = await api<Page<PublicEvent>>(`/api/events?${busca}`);
      // Chegou tarde: outro pedido já saiu depois deste. Descartar é o certo —
      // esta resposta descreve um filtro que não está mais na tela.
      if (meuPedido !== pedidoAtual.current) return;
      setDados(resposta);
    } catch {
      if (meuPedido !== pedidoAtual.current) return;
      setErro(
        "Não conseguimos carregar os eventos. A API pode estar hibernando — " +
          "no plano gratuito, a primeira chamada leva até 50 segundos.",
      );
    } finally {
      // Só o pedido mais recente desliga o esqueleto. Senão, um pedido antigo
      // que termina primeiro apagaria o "carregando" do que ainda está no ar.
      if (meuPedido === pedidoAtual.current) setCarregando(false);
    }
  }, [q, kind]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const eventos = dados?.results ?? [];
  const destaque = !q && !kind ? eventos[0] : undefined;
  const grade = destaque ? eventos.slice(1) : eventos;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      {destaque && !carregando && <Destaque event={destaque} />}

      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-ink">
            {q ? `Resultados para "${q}"` : "Em cartaz"}
          </h1>
          {dados && (
            <p className="mt-0.5 text-sm text-muted">
              {dados.count} {dados.count === 1 ? "evento" : "eventos"}
              {q ? " encontrados" : " disponíveis"}
            </p>
          )}
        </div>

        {/* Chips de filtro — padrão Sympla. */}
        <div className="flex gap-1.5" role="group" aria-label="Filtrar por tipo">
          {FILTROS.map((f) => (
            <button
              key={f.valor}
              onClick={() => setKind(f.valor)}
              aria-pressed={kind === f.valor}
              className={`h-8 rounded-full border px-3 text-[13px] font-medium transition-colors
                ${
                  kind === f.valor
                    ? "border-brand bg-brand text-white"
                    : "border-line-strong bg-white text-body hover:border-brand/40"
                }`}
            >
              {f.rotulo}
            </button>
          ))}
        </div>
      </div>

      {erro && (
        <div className="space-y-3">
          <Alert tone="danger" title="Falha ao carregar">
            {erro}
          </Alert>
          <Button variant="secondary" onClick={() => void carregar()}>
            Tentar de novo
          </Button>
        </div>
      )}

      {carregando && (
        <Grade>
          {Array.from({ length: 10 }).map((_, i) => (
            <EventCardSkeleton key={i} />
          ))}
        </Grade>
      )}

      {!carregando && !erro && grade.length === 0 && !destaque && (
        <EmptyState
          title={q ? "Nenhum evento encontrado" : "Ainda não há eventos publicados"}
          action={
            q ? (
              <Button variant="secondary" onClick={() => (window.location.href = "/")}>
                Limpar busca
              </Button>
            ) : undefined
          }
        >
          {q
            ? "Tente outro termo, ou procure pelo nome do local."
            : "Assim que um organizador publicar um evento, ele aparece aqui."}
        </EmptyState>
      )}

      {/* Sem `erro`: quando o recarregamento falha, mostrar a lista ANTERIOR
          embaixo de "Falha ao carregar" é contradição pura — a tela exibe 12
          eventos e diz que não conseguiu carregar. Pior: depois de trocar o
          filtro, os cards visíveis são do filtro antigo. */}
      {!carregando && !erro && grade.length > 0 && (
        <Grade>
          {grade.map((e) => (
            <EventCard key={e.id} event={e} />
          ))}
        </Grade>
      )}
    </div>
  );
}

function Grade({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
      {children}
    </div>
  );
}

/** Faixa horizontal do primeiro evento — quebra a monotonia da grade. */
function Destaque({ event }: { event: PublicEvent }) {
  const { dia, mes, hora } = dateParts(event.starts_at);

  return (
    <section className="mb-8 overflow-hidden rounded-card border border-line bg-white">
      {/* Antes o pôster esticava para preencher a altura do texto (aspect-auto)
          e o object-cover cortava o rosto; sobrava um vazio grande à direita.
          Agora a imagem mantém 2:3 como no resto da vitrine, e a coluna de
          texto tem largura máxima para o parágrafo não atravessar a tela. */}
      <div className="grid gap-0 sm:grid-cols-[176px_1fr] md:grid-cols-[208px_1fr]">
        <div className="relative aspect-[2/3] bg-canvas">
          {event.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={event.image_url}
              alt=""
              className="size-full object-cover object-top"
            />
          ) : (
            <div className="grid size-full place-items-center bg-brand/5" />
          )}
        </div>

        <div className="flex max-w-2xl flex-col justify-center gap-3 p-5 md:p-6">
          <div className="flex items-center gap-3">
            <div className="rounded border border-line bg-canvas px-2.5 py-1.5 text-center leading-none">
              <span className="block text-lg font-bold text-ink">{dia}</span>
              <span className="block text-[10px] font-semibold tracking-wider text-muted">
                {mes}
              </span>
            </div>
            <div className="text-sm text-muted">
              <p className="font-medium text-body">{event.venue}</p>
              <p>às {hora}</p>
            </div>
          </div>

          <h2 className="text-xl font-bold leading-tight text-ink md:text-2xl">
            {event.title}
          </h2>

          {event.description && (
            <p className="line-clamp-3 text-sm leading-relaxed text-muted">
              {event.description}
            </p>
          )}

          <div className="mt-1 flex flex-wrap items-center gap-4">
            <Link
              href={`/eventos/${event.id}`}
              className="inline-flex h-11 items-center rounded bg-accent px-6 text-[15px]
                font-semibold text-white hover:bg-accent-dark"
            >
              Ver ingressos
            </Link>
            <p className="text-sm text-muted">
              a partir de{" "}
              <strong className="text-base font-bold text-ink">{preco(event.price_from)}</strong>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
