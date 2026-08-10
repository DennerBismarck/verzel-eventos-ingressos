"use client";

/**
 * Painel do organizador: lista dos próprios eventos e publicação.
 *
 * A API já devolve só os eventos deste organizador (filtro no get_queryset do
 * Django). Não existe filtro por dono aqui no front — se existisse, seria
 * decoração: a lista viria completa e bastaria abrir o DevTools.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Alert, Badge, Button, EmptyState, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { preco, shortDate } from "@/lib/format";
import type { OrganizerEvent, Page } from "@/lib/types";

export default function OrganizadorPage() {
  const { user, token, ready } = useAuth();
  const [eventos, setEventos] = useState<OrganizerEvent[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<number | null>(null);

  const carregar = useCallback(async () => {
    if (!token) return;
    try {
      const r = await api<Page<OrganizerEvent>>("/api/organizer/events", { token });
      setEventos(r.results);
    } catch {
      setErro("Não conseguimos carregar seus eventos.");
    }
  }, [token]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function alternarPublicacao(ev: OrganizerEvent) {
    setOcupado(ev.id);
    setErro(null);
    try {
      await api(`/api/organizer/events/${ev.id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify({
          status: ev.status === "PUBLISHED" ? "DRAFT" : "PUBLISHED",
        }),
      });
      await carregar();
    } catch (e) {
      const dados = (e as { data?: Record<string, string[]> }).data;
      const primeira = dados ? Object.values(dados)[0]?.[0] : null;
      setErro(primeira ?? "Não foi possível alterar a publicação.");
    } finally {
      setOcupado(null);
    }
  }

  if (!ready) return <Skeleton className="mx-auto mt-8 h-64 max-w-4xl" />;

  if (!user || user.role !== "ORGANIZER") {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="text-xl font-bold text-ink">Área do organizador</h1>
        <p className="mt-2 text-sm text-muted">
          {user
            ? "Sua conta não é de organizador."
            : "Entre com uma conta de organizador para gerenciar eventos."}
        </p>
        {!user && (
          <Link
            href="/entrar"
            className="mt-4 inline-flex h-10 items-center rounded bg-accent px-5
              text-sm font-semibold text-white hover:bg-accent-dark"
          >
            Entrar
          </Link>
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Meus eventos</h1>
          <p className="mt-1 text-sm text-muted">
            Publique um evento a partir do catálogo e acompanhe as vendas.
          </p>
        </div>
        <Link
          href="/organizador/novo"
          className="inline-flex h-10 items-center rounded bg-accent px-5 text-sm
            font-semibold text-white hover:bg-accent-dark"
        >
          Novo evento
        </Link>
      </div>

      {erro && (
        <div className="mb-4">
          <Alert tone="danger">{erro}</Alert>
        </div>
      )}

      {!eventos && <Skeleton className="h-48 w-full" />}

      {eventos && eventos.length === 0 && (
        <EmptyState
          title="Você ainda não criou nenhum evento"
          action={
            <Link
              href="/organizador/novo"
              className="inline-flex h-10 items-center rounded bg-accent px-5
                text-sm font-semibold text-white hover:bg-accent-dark"
            >
              Criar o primeiro
            </Link>
          }
        >
          Busque um filme ou show no catálogo, defina local, data e preço, e publique.
        </EmptyState>
      )}

      {eventos && eventos.length > 0 && (
        <div className="space-y-3">
          {eventos.map((ev) => {
            const vendidoPct = ev.capacity ? Math.round((ev.sold_count / ev.capacity) * 100) : 0;
            return (
              <article
                key={ev.id}
                className="flex flex-wrap items-center gap-4 rounded-card border
                  border-line bg-white p-4"
              >
                <div className="h-20 w-14 shrink-0 overflow-hidden rounded border border-line bg-canvas">
                  {ev.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={ev.image_url} alt="" className="size-full object-cover" />
                  ) : null}
                </div>

                <div className="min-w-40 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-semibold text-ink">{ev.title}</h2>
                    {ev.status === "PUBLISHED" ? (
                      <Badge tone="ok">Publicado</Badge>
                    ) : (
                      <Badge tone="warn">Rascunho</Badge>
                    )}
                  </div>
                  <p className="mt-0.5 text-sm text-muted">
                    {ev.venue} · {shortDate(ev.starts_at)}
                  </p>
                  <p className="mt-0.5 text-sm text-muted">
                    {preco(ev.price_from)} · {ev.kind === "GA" ? "Pista" : "Lugar marcado"}
                  </p>
                </div>

                <div className="w-40">
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-muted">Vendidos</span>
                    <span className="font-semibold text-ink">
                      {ev.sold_count}/{ev.capacity}
                    </span>
                  </div>
                  <div
                    className="h-1.5 overflow-hidden rounded-full bg-line"
                    role="progressbar"
                    aria-valuenow={vendidoPct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${vendidoPct}% vendido`}
                  >
                    <div
                      className={`h-full ${vendidoPct >= 100 ? "bg-danger" : "bg-ok"}`}
                      style={{ width: `${Math.min(vendidoPct, 100)}%` }}
                    />
                  </div>
                </div>

                <div className="flex gap-2">
                  <Link
                    href={`/organizador/vendas/${ev.id}`}
                    className="inline-flex h-8 items-center rounded border
                      border-line-strong px-3 text-[13px] font-semibold text-ink
                      hover:bg-canvas"
                  >
                    Vendas
                  </Link>
                  {ev.status === "PUBLISHED" && (
                    <Link
                      href={`/eventos/${ev.id}`}
                      className="inline-flex h-8 items-center rounded border
                        border-line-strong px-3 text-[13px] font-semibold text-ink
                        hover:bg-canvas"
                    >
                      Ver página
                    </Link>
                  )}
                  <Button
                    size="sm"
                    variant={ev.status === "PUBLISHED" ? "secondary" : "primary"}
                    loading={ocupado === ev.id}
                    onClick={() => void alternarPublicacao(ev)}
                  >
                    {ev.status === "PUBLISHED" ? "Despublicar" : "Publicar"}
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
