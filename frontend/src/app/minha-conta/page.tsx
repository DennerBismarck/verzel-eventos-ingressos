"use client";

/**
 * Carteira do cliente: ingressos emitidos + histórico de reservas.
 *
 * O QR desenha `qr_payload` — que é `codigo.assinatura`, exatamente o que a
 * portaria confere. O QR nunca é imagem vinda do servidor: é gerado aqui a
 * partir do texto, então funciona offline depois de carregado.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";

import { Alert, Badge, Button, EmptyState, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fullDate, money, shortDate } from "@/lib/format";
import type { Page, Reservation, ReservationStatus, Ticket } from "@/lib/types";

export default function MinhaContaPage() {
  const { user, token, ready } = useAuth();
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [reservas, setReservas] = useState<Reservation[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aberto, setAberto] = useState<Ticket | null>(null);

  const carregar = useCallback(async () => {
    if (!token) return;
    try {
      const [t, r] = await Promise.all([
        api<Page<Ticket>>("/api/tickets", { token }),
        api<Page<Reservation>>("/api/reservations", { token }),
      ]);
      setTickets(t.results);
      setReservas(r.results);
    } catch {
      setErro("Não conseguimos carregar seus ingressos.");
    }
  }, [token]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  if (!ready) return <Carregando />;

  if (!user) {
    return (
      <Aviso titulo="Entre para ver seus ingressos">
        <Link href="/entrar" className="font-semibold text-brand hover:underline">
          Ir para o login
        </Link>
      </Aviso>
    );
  }

  if (user.role !== "CUSTOMER") {
    return (
      <Aviso titulo="Esta área é dos clientes">
        Sua conta é de {user.role === "ORGANIZER" ? "organizador" : "portaria"}. Ingressos
        ficam em contas de cliente.
      </Aviso>
    );
  }

  const validos = tickets?.filter((t) => t.status === "VALID") ?? [];
  const usados = tickets?.filter((t) => t.status === "USED") ?? [];

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="text-2xl font-bold text-ink">Meus ingressos</h1>
      <p className="mt-1 text-sm text-muted">
        Apresente o QR na entrada. Cada ingresso vale uma única passagem.
      </p>

      {erro && (
        <div className="mt-6">
          <Alert tone="danger">{erro}</Alert>
        </div>
      )}

      {!tickets && !erro && (
        <div className="mt-6 space-y-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      )}

      {tickets && tickets.length === 0 && (
        <div className="mt-6">
          <EmptyState
            title="Você ainda não tem ingressos"
            action={
              <Link
                href="/"
                className="inline-flex h-10 items-center rounded bg-accent px-5
                  text-sm font-semibold text-white hover:bg-accent-dark"
              >
                Ver eventos
              </Link>
            }
          >
            Escolha um evento na vitrine e finalize a compra para receber seu QR.
          </EmptyState>
        </div>
      )}

      {validos.length > 0 && (
        <section className="mt-6 space-y-3">
          {validos.map((t) => (
            <TicketStub key={t.id} ticket={t} onAbrir={() => setAberto(t)} />
          ))}
        </section>
      )}

      {usados.length > 0 && (
        <section className="mt-10">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
            Já utilizados
          </h2>
          <div className="space-y-3">
            {usados.map((t) => (
              <TicketStub key={t.id} ticket={t} onAbrir={() => setAberto(t)} />
            ))}
          </div>
        </section>
      )}

      {reservas && reservas.length > 0 && (
        <section className="mt-12">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
            Histórico de reservas
          </h2>
          <div className="overflow-hidden rounded-card border border-line bg-white">
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-canvas text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">Evento</th>
                  <th className="px-4 py-2.5 font-semibold">Data</th>
                  <th className="px-4 py-2.5 text-center font-semibold">Qtd</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Total</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Situação</th>
                </tr>
              </thead>
              <tbody>
                {reservas.map((r) => (
                  <tr key={r.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3 font-medium text-ink">{r.event_title}</td>
                    <td className="px-4 py-3 text-muted">{shortDate(r.created_at)}</td>
                    <td className="px-4 py-3 text-center">{r.quantity}</td>
                    <td className="px-4 py-3 text-right font-medium text-ink">
                      {money(r.total_price)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <StatusReserva status={r.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {aberto && <ModalQR ticket={aberto} onFechar={() => setAberto(null)} />}
    </div>
  );
}

/**
 * Canhoto de ingresso. O recorte com o círculo entalhado imita a picotagem
 * de um ingresso físico — é o que faz a tela parecer um produto de bilheteria
 * e não uma lista genérica de cards.
 */
function TicketStub({ ticket, onAbrir }: { ticket: Ticket; onAbrir: () => void }) {
  const usado = ticket.status === "USED";

  return (
    <article
      className={`flex overflow-hidden rounded-card border border-line bg-white
        ${usado ? "opacity-70" : ""}`}
    >
      <div
        aria-hidden="true"
        className={`w-2 shrink-0 ${usado ? "bg-line-strong" : "bg-accent"}`}
      />

      <div className="flex min-w-0 flex-1 flex-col gap-1 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate font-semibold text-ink">{ticket.event_title}</h3>
          {usado ? <Badge tone="neutral">Utilizado</Badge> : <Badge tone="ok">Válido</Badge>}
        </div>
        <p className="text-sm text-muted">{ticket.venue}</p>
        {/* first-letter e não capitalize: `capitalize` põe maiúscula em TODA
            palavra ("Sábado, 15 De Agosto De 2026"). */}
        <p className="text-sm text-muted first-letter:uppercase">
          {fullDate(ticket.event_starts_at)}
        </p>
        {ticket.seat_label && (
          <p className="text-sm font-medium text-ink">Lugar {ticket.seat_label}</p>
        )}
        {usado && ticket.used_at && (
          <p className="mt-1 text-xs text-muted">Entrada registrada em {shortDate(ticket.used_at)}</p>
        )}
      </div>

      {/* Divisor picotado */}
      <div className="relative w-px shrink-0 self-stretch bg-line">
        <span
          aria-hidden="true"
          className="absolute -top-2 left-1/2 size-4 -translate-x-1/2 rounded-full bg-canvas"
        />
        <span
          aria-hidden="true"
          className="absolute -bottom-2 left-1/2 size-4 -translate-x-1/2 rounded-full bg-canvas"
        />
      </div>

      <button
        onClick={onAbrir}
        className="flex w-28 shrink-0 flex-col items-center justify-center gap-1.5
          p-3 text-center hover:bg-canvas sm:w-32"
      >
        <span className="rounded border border-line bg-white p-1">
          <QRCodeSVG value={ticket.qr_payload} size={56} level="M" />
        </span>
        <span className="text-[11px] font-semibold text-brand">Ampliar</span>
      </button>
    </article>
  );
}

function ModalQR({ ticket, onFechar }: { ticket: Ticket; onFechar: () => void }) {
  const [copiado, setCopiado] = useState(false);
  const linkPublico = `${typeof window !== "undefined" ? window.location.origin : ""}/ingresso/${ticket.share_token}`;

  // Esc fecha — expectativa básica de qualquer diálogo.
  useEffect(() => {
    const fn = (e: KeyboardEvent) => e.key === "Escape" && onFechar();
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [onFechar]);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(linkPublico);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      /* clipboard bloqueado: o campo abaixo permite copiar na mão */
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Ingresso para ${ticket.event_title}`}
      className="fixed inset-0 z-50 grid place-items-center bg-ink/60 p-4"
      onClick={onFechar}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-card border border-line bg-white p-6 text-center"
      >
        <h2 className="text-lg font-bold text-ink">{ticket.event_title}</h2>
        <p className="mt-0.5 text-sm text-muted">{ticket.venue}</p>

        <div className="my-5 inline-block rounded border border-line bg-white p-3">
          <QRCodeSVG value={ticket.qr_payload} size={200} level="M" />
        </div>

        <p className="font-mono text-[11px] text-muted">{ticket.code}</p>
        <p className="mt-1 text-xs text-muted">
          Código para digitação manual, se a câmera falhar.
        </p>

        <div className="mt-5 border-t border-line pt-4 text-left">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            Compartilhar
          </p>
          <p className="mt-1 text-xs text-muted">
            Quem abrir o link vê o ingresso, mas <strong>não</strong> recebe o código de
            entrada.
          </p>
          <div className="mt-2 flex gap-1.5">
            <input
              readOnly
              value={linkPublico}
              onFocus={(e) => e.currentTarget.select()}
              aria-label="Link do ingresso"
              className="h-9 min-w-0 flex-1 rounded border border-line-strong bg-canvas
                px-2 font-mono text-[11px] text-body"
            />
            <Button size="sm" variant="secondary" onClick={() => void copiar()}>
              {copiado ? "Copiado" : "Copiar"}
            </Button>
          </div>
        </div>

        <Button variant="ghost" className="mt-4 w-full" onClick={onFechar}>
          Fechar
        </Button>
      </div>
    </div>
  );
}

function StatusReserva({ status }: { status: ReservationStatus }) {
  const mapa = {
    PAID: { tone: "ok", texto: "Paga" },
    PENDING: { tone: "warn", texto: "Aguardando" },
    REFUSED: { tone: "danger", texto: "Recusada" },
    CANCELLED: { tone: "neutral", texto: "Cancelada" },
  } as const;
  const { tone, texto } = mapa[status];
  return <Badge tone={tone}>{texto}</Badge>;
}

function Carregando() {
  return (
    <div className="mx-auto max-w-4xl space-y-3 px-4 py-8">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

function Aviso({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center">
      <h1 className="text-xl font-bold text-ink">{titulo}</h1>
      <div className="mt-2 text-sm text-muted">{children}</div>
    </div>
  );
}
