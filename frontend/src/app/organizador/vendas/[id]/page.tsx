"use client";

/**
 * Vendas de um evento.
 *
 * A tela existe para responder três perguntas que o painel não respondia:
 * quanto entrou, quem comprou, e quantos já entraram no evento.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Alert, Badge, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { money, shortDate } from "@/lib/format";
import type { ReservationStatus, SalesResponse } from "@/lib/types";

export default function VendasPage() {
  const { id } = useParams<{ id: string }>();
  const { user, ready } = useAuth();
  const [dados, setDados] = useState<SalesResponse | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      setDados(await api<SalesResponse>(`/api/organizer/events/${id}/sales`));
    } catch (e) {
      setErro(
        e instanceof ApiError && e.status === 404
          ? "Este evento não existe ou não é seu."
          : "Não conseguimos carregar as vendas.",
      );
    }
  }, [id]);

  useEffect(() => {
    if (ready && user?.role === "ORGANIZER") void carregar();
  }, [ready, user, carregar]);

  if (!ready) return <Skeleton className="mx-auto mt-8 h-64 max-w-4xl" />;

  if (!user || user.role !== "ORGANIZER") {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="text-xl font-bold text-ink">Área do organizador</h1>
        <p className="mt-2 text-sm text-muted">
          Entre com uma conta de organizador para ver as vendas.
        </p>
      </div>
    );
  }

  if (erro) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <Alert tone="danger">{erro}</Alert>
        <Link href="/organizador" className="mt-4 inline-block text-sm font-semibold text-brand">
          ← Meus eventos
        </Link>
      </div>
    );
  }

  if (!dados) {
    return (
      <div className="mx-auto max-w-5xl space-y-3 px-4 py-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const { summary: resumo, sales: vendas } = dados;
  const ocupacao = resumo.capacity
    ? Math.round((resumo.sold_count / resumo.capacity) * 100)
    : 0;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <nav aria-label="Trilha" className="mb-4 text-xs text-muted">
        <Link href="/organizador" className="hover:text-brand">
          Meus eventos
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-body">Vendas</span>
      </nav>

      <h1 className="text-2xl font-bold text-ink">{resumo.event_title}</h1>
      <p className="mt-1 text-sm text-muted">
        {vendas.length} {vendas.length === 1 ? "reserva" : "reservas"} registradas
      </p>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Cartao rotulo="Receita" valor={money(resumo.revenue)} destaque>
          {resumo.paid_reservations} {resumo.paid_reservations === 1 ? "compra paga" : "compras pagas"}
        </Cartao>
        <Cartao rotulo="Ocupação" valor={`${ocupacao}%`}>
          {resumo.sold_count} de {resumo.capacity} · {resumo.available} livres
        </Cartao>
        <Cartao rotulo="Ingressos emitidos" valor={String(resumo.tickets_issued)}>
          um por lugar vendido
        </Cartao>
        <Cartao rotulo="Já entraram" valor={String(resumo.tickets_used)}>
          validados na portaria
        </Cartao>
      </div>

      <h2 className="mb-3 mt-10 text-sm font-semibold uppercase tracking-wide text-muted">
        Compradores
      </h2>

      {vendas.length === 0 ? (
        <div className="rounded-card border border-dashed border-line-strong bg-white px-6 py-12 text-center">
          <p className="font-semibold text-ink">Nenhuma venda ainda</p>
          <p className="mt-1 text-sm text-muted">
            As reservas aparecem aqui assim que alguém comprar.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-card border border-line bg-white">
          <table className="w-full min-w-[42rem] text-sm">
            <thead className="border-b border-line bg-canvas text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-2.5 font-semibold">Comprador</th>
                <th className="px-4 py-2.5 font-semibold">Data</th>
                <th className="px-4 py-2.5 text-center font-semibold">Qtd</th>
                <th className="px-4 py-2.5 text-center font-semibold">Entradas</th>
                <th className="px-4 py-2.5 text-right font-semibold">Total</th>
                <th className="px-4 py-2.5 text-right font-semibold">Situação</th>
              </tr>
            </thead>
            <tbody>
              {vendas.map((v) => (
                <tr key={v.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-3">
                    <span className="block font-medium text-ink">{v.customer_name}</span>
                    <span className="block text-xs text-muted">{v.customer_email}</span>
                    {v.seats.length > 0 && (
                      <span className="mt-0.5 block text-xs text-muted">
                        {v.seats.join(", ")}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted">{shortDate(v.created_at)}</td>
                  <td className="px-4 py-3 text-center">{v.quantity}</td>
                  <td className="px-4 py-3 text-center">
                    {v.tickets_total === 0 ? (
                      <span className="text-muted">—</span>
                    ) : (
                      <span
                        className={
                          v.tickets_used === v.tickets_total ? "font-semibold text-ok" : ""
                        }
                      >
                        {v.tickets_used}/{v.tickets_total}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-ink">
                    {money(v.total_price)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <SituacaoDaVenda status={v.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Cartao({
  rotulo,
  valor,
  destaque = false,
  children,
}: {
  rotulo: string;
  valor: string;
  destaque?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-card border border-line bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{rotulo}</p>
      <p className={`mt-1 font-bold text-ink ${destaque ? "text-2xl" : "text-xl"}`}>{valor}</p>
      <p className="mt-0.5 text-xs text-muted">{children}</p>
    </div>
  );
}

function SituacaoDaVenda({ status }: { status: ReservationStatus }) {
  const mapa = {
    PAID: { tone: "ok", texto: "Paga" },
    PENDING: { tone: "warn", texto: "Aguardando" },
    REFUSED: { tone: "danger", texto: "Recusada" },
    CANCELLED: { tone: "neutral", texto: "Cancelada" },
  } as const;
  const { tone, texto } = mapa[status];
  return <Badge tone={tone}>{texto}</Badge>;
}
