"use client";

/**
 * Ingresso compartilhado — página pública, somente leitura.
 *
 * O que ESTA tela deliberadamente não mostra: o código do ingresso e o QR.
 * O backend nem os envia neste endpoint. Compartilhar a visualização não é
 * ceder a entrada — quem recebeu o link vê que o ingresso é real, para qual
 * evento, e se já foi usado.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, Badge, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { fullDate } from "@/lib/format";
import type { SharedTicket } from "@/lib/types";

export default function IngressoCompartilhadoPage() {
  const { token } = useParams<{ token: string }>();
  const [ticket, setTicket] = useState<SharedTicket | null>(null);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    api<SharedTicket>(`/api/shared/${token}`)
      .then(setTicket)
      .catch(() => setErro(true));
  }, [token]);

  if (erro) {
    return (
      <div className="mx-auto max-w-md px-4 py-16">
        <Alert tone="danger" title="Ingresso não encontrado">
          Este link não corresponde a nenhum ingresso. Verifique se ele foi copiado por
          inteiro.
        </Alert>
        <Link href="/" className="mt-4 inline-block text-sm font-semibold text-brand">
          ← Ir para a vitrine
        </Link>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="mx-auto max-w-md px-4 py-16">
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const usado = ticket.status === "USED";

  return (
    <div className="mx-auto max-w-md px-4 py-12">
      <article className="overflow-hidden rounded-card border border-line bg-white">
        <div className={`h-1.5 ${usado ? "bg-line-strong" : "bg-accent"}`} aria-hidden="true" />

        <div className="p-6">
          <div className="mb-4 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted">
              Ingresso
            </span>
            {usado ? <Badge tone="neutral">Utilizado</Badge> : <Badge tone="ok">Válido</Badge>}
          </div>

          <h1 className="text-xl font-bold leading-tight text-ink">{ticket.event_title}</h1>

          <dl className="mt-5 space-y-3 border-t border-line pt-5 text-sm">
            <div className="flex gap-3">
              <dt className="w-20 shrink-0 text-muted">Quando</dt>
              <dd className="font-medium text-ink first-letter:uppercase">
                {fullDate(ticket.event_starts_at)}
              </dd>
            </div>
            <div className="flex gap-3">
              <dt className="w-20 shrink-0 text-muted">Onde</dt>
              <dd className="font-medium text-ink">{ticket.venue}</dd>
            </div>
            <div className="flex gap-3">
              <dt className="w-20 shrink-0 text-muted">Titular</dt>
              <dd className="font-medium text-ink">{ticket.customer_name}</dd>
            </div>
            {ticket.seat_label && (
              <div className="flex gap-3">
                <dt className="w-20 shrink-0 text-muted">Lugar</dt>
                <dd className="font-medium text-ink">{ticket.seat_label}</dd>
              </div>
            )}
          </dl>
        </div>

        <p className="border-t border-line bg-canvas px-6 py-4 text-xs text-muted">
          Esta é uma visualização. O código de entrada fica apenas com o titular — este
          link não permite acessar o evento.
        </p>
      </article>

      <p className="mt-6 text-center text-sm text-muted">
        <Link href="/" className="font-semibold text-brand hover:underline">
          Conheça outros eventos
        </Link>
      </p>
    </div>
  );
}
