"use client";

/**
 * Detalhe do evento + compra.
 *
 * A compra tem dois passos porque o backend tem dois passos: a reserva já
 * SEGURA o estoque (PENDING) e o pagamento vem depois. Espelhar isso na tela
 * é honesto — o usuário vê que o lugar ficou guardado antes de pagar.
 */

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { SeatMap } from "@/components/seat-map";
import { Alert, Badge, Button, ContagemRegressiva, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fullDate, money, preco } from "@/lib/format";
import type { PayResponse, PublicEvent, Reservation, Seat } from "@/lib/types";

const MAX_POR_COMPRA = 8;

export default function EventoPage() {
  const { id } = useParams<{ id: string }>();
  const [evento, setEvento] = useState<PublicEvent | null>(null);
  const [assentos, setAssentos] = useState<Seat[]>([]);
  const [escolhidos, setEscolhidos] = useState<Set<number>>(new Set());
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const e = await api<PublicEvent>(`/api/events/${id}`);
      setEvento(e);
      if (e.kind === "SEATED") {
        // Rota separada e sem paginação: o mapa é desenhado inteiro.
        setAssentos(await api<Seat[]>(`/api/events/${id}/seats`));
      }
    } catch (e) {
      setErro(
        e instanceof ApiError && e.status === 404
          ? "Este evento não existe ou não está mais publicado."
          : "Não conseguimos carregar este evento.",
      );
    }
  }, [id]);

  function alternarAssento(assento: Seat) {
    setEscolhidos((atual) => {
      const proximo = new Set(atual);
      if (proximo.has(assento.id)) proximo.delete(assento.id);
      else proximo.add(assento.id);
      return proximo;
    });
  }

  useEffect(() => {
    void carregar();
  }, [carregar]);

  if (erro) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <Alert tone="danger" title="Evento indisponível">
          {erro}
        </Alert>
        <Link href="/" className="mt-4 inline-block text-sm font-semibold text-brand">
          ← Voltar para a vitrine
        </Link>
      </div>
    );
  }

  if (!evento) {
    return (
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-6 md:grid-cols-[280px_1fr]">
        <Skeleton className="aspect-[2/3] w-full" />
        <div className="space-y-3">
          <Skeleton className="h-9 w-3/4" />
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <nav aria-label="Trilha" className="mb-4 text-xs text-muted">
        <Link href="/" className="hover:text-brand">
          Início
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-body">{evento.title}</span>
      </nav>

      <div className="grid gap-8 md:grid-cols-[280px_1fr] lg:grid-cols-[300px_1fr_320px]">
        <div className="mx-auto w-full max-w-[280px] md:mx-0">
          <div className="overflow-hidden rounded-card border border-line bg-canvas">
            {evento.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={evento.image_url}
                alt={`Cartaz de ${evento.title}`}
                className="aspect-[2/3] w-full object-cover"
              />
            ) : (
              <div className="grid aspect-[2/3] place-items-center bg-brand/5 p-4 text-center text-sm font-semibold text-brand/50">
                {evento.title}
              </div>
            )}
          </div>
        </div>

        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge tone="brand">
              {evento.kind === "GA" ? "Pista" : "Lugar marcado"}
            </Badge>
            <Badge>{evento.source === "TMDB" ? "Filme" : "Show"}</Badge>
          </div>

          <h1 className="text-2xl font-bold leading-tight text-ink md:text-3xl">
            {evento.title}
          </h1>

          <dl className="mt-5 space-y-3 border-y border-line py-5 text-sm">
            <Linha rotulo="Quando">
              <span className="first-letter:uppercase">{fullDate(evento.starts_at)}</span>
            </Linha>
            <Linha rotulo="Onde">{evento.venue}</Linha>
            <Linha rotulo="Organização">{evento.organizer_name}</Linha>
          </dl>

          {evento.description && (
            <div className="mt-6">
              <h2 className="mb-2 text-base font-semibold text-ink">Sobre</h2>
              <p className="whitespace-pre-line text-sm leading-relaxed text-body">
                {evento.description}
              </p>
            </div>
          )}

          {evento.kind === "SEATED" && (
            <div className="mt-8 rounded-card border border-line bg-white p-4 sm:p-6">
              <h2 className="mb-4 text-base font-semibold text-ink">Escolha seus lugares</h2>
              {assentos.length === 0 ? (
                <Alert tone="warn" title="Mapa ainda não publicado">
                  O organizador ainda não montou o mapa de assentos deste evento.
                </Alert>
              ) : (
                <SeatMap
                  seats={assentos}
                  selecionados={escolhidos}
                  onAlternar={alternarAssento}
                  limite={MAX_POR_COMPRA}
                />
              )}
            </div>
          )}
        </div>

        <div className="lg:row-span-2">
          <div className="lg:sticky lg:top-20">
            <PainelCompra
              evento={evento}
              assentos={assentos}
              escolhidos={escolhidos}
              aoLimparEscolha={() => setEscolhidos(new Set())}
              aoComprar={carregar}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function Linha({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <dt className="w-24 shrink-0 text-muted">{rotulo}</dt>
      <dd className="font-medium text-ink">{children}</dd>
    </div>
  );
}

type Etapa = "escolha" | "confirmar" | "pago" | "recusado";

function PainelCompra({
  evento,
  assentos,
  escolhidos,
  aoLimparEscolha,
  aoComprar,
}: {
  evento: PublicEvent;
  assentos: Seat[];
  escolhidos: Set<number>;
  aoLimparEscolha: () => void;
  aoComprar: () => Promise<void>;
}) {
  const { user, token, ready } = useAuth();
  const router = useRouter();

  const [qtd, setQtd] = useState(1);
  const [etapa, setEtapa] = useState<Etapa>("escolha");
  const [reserva, setReserva] = useState<Reservation | null>(null);
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const comLugarMarcado = evento.kind === "SEATED";
  const maximo = Math.min(MAX_POR_COMPRA, evento.available);
  const esgotado = evento.available <= 0;

  const selecionados = assentos.filter((a) => escolhidos.has(a.id));
  // Em lugar marcado o preço vem de cada poltrona (seções custam diferente);
  // na pista, do preço único do evento.
  const total = comLugarMarcado
    ? selecionados.reduce((soma, a) => soma + Number(a.price), 0)
    : Number(evento.price) * qtd;
  const podeReservar = comLugarMarcado ? selecionados.length > 0 : !esgotado;

  async function reservar() {
    if (!user) {
      // Guarda para onde voltar depois de entrar.
      router.push(`/entrar?next=${encodeURIComponent(`/eventos/${evento.id}`)}`);
      return;
    }
    setOcupado(true);
    setErro(null);
    try {
      const r = await api<Reservation>("/api/reservations", {
        method: "POST",
        token,
        body: JSON.stringify(
          comLugarMarcado
            ? { event: evento.id, seats: [...escolhidos] }
            : { event: evento.id, quantity: qtd },
        ),
      });
      setReserva(r);
      setEtapa("confirmar");
    } catch (e) {
      setErro(mensagemDeErro(e));
      // Recarrega o mapa: o motivo mais comum de falha aqui é alguém ter
      // levado a poltrona no intervalo entre carregar a tela e clicar.
      aoLimparEscolha();
      await aoComprar();
    } finally {
      setOcupado(false);
    }
  }

  async function pagar() {
    if (!reserva) return;
    setOcupado(true);
    setErro(null);
    try {
      const r = await api<PayResponse>(`/api/reservations/${reserva.id}/pay`, {
        method: "POST",
        token,
      });
      setEtapa(r.payment.status === "CONFIRMED" ? "pago" : "recusado");
      setMotivo(r.payment.reason);
    } catch (e) {
      // 402 é a recusa simulada — o cliente HTTP trata como erro, mas para o
      // usuário é um resultado esperado, não uma falha do sistema.
      if (e instanceof ApiError && e.status === 402) {
        const corpo = e.data as PayResponse | null;
        setEtapa("recusado");
        setMotivo(corpo?.payment?.reason ?? "Pagamento recusado.");
      } else {
        setErro(mensagemDeErro(e));
      }
    } finally {
      setOcupado(false);
      await aoComprar();
    }
  }

  async function cancelar() {
    if (!reserva) return;
    setOcupado(true);
    try {
      await api(`/api/reservations/${reserva.id}/cancel`, { method: "POST", token });
      setReserva(null);
      setEtapa("escolha");
      aoLimparEscolha();
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
      await aoComprar();
    }
  }

  return (
    <aside className="rounded-card border border-line bg-white p-5">
      {etapa === "escolha" && (
        <>
          <div className="mb-4 flex items-baseline justify-between border-b border-line pb-4">
            <span className="text-sm text-muted">
              {comLugarMarcado ? "Lugar marcado" : "Ingresso"}
            </span>
            <strong className="text-xl font-bold text-ink">
              {comLugarMarcado ? (
                <span className="text-base font-normal text-muted">
                  a partir de{" "}
                  <span className="text-xl font-bold text-ink">
                    {preco(evento.price_from)}
                  </span>
                </span>
              ) : (
                preco(evento.price_from)
              )}
            </strong>
          </div>

          {esgotado ? (
            <Alert tone="warn" title="Esgotado">
              Não há mais ingressos disponíveis para este evento.
            </Alert>
          ) : comLugarMarcado ? (
            <>
              <div className="mb-4">
                <span className="mb-2 block text-sm font-medium text-ink">
                  Selecionados
                </span>
                {selecionados.length === 0 ? (
                  <p className="text-sm text-muted">
                    Escolha as poltronas no mapa ao lado.
                  </p>
                ) : (
                  <ul className="space-y-1.5">
                    {selecionados.map((a) => (
                      <li
                        key={a.id}
                        className="flex items-center justify-between gap-2 text-sm"
                      >
                        <span className="text-body">
                          {a.section} · {a.row}
                          {a.number}
                        </span>
                        <span className="font-medium text-ink">{money(a.price)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="mb-4 flex items-baseline justify-between border-t border-line pt-4">
                <span className="text-sm font-medium text-ink">Total</span>
                <strong className="text-xl font-bold text-ink">{money(total)}</strong>
              </div>

              <Button
                size="lg"
                className="w-full"
                loading={ocupado}
                disabled={!ready || !podeReservar}
                onClick={() => void reservar()}
              >
                {!user
                  ? "Entrar para comprar"
                  : selecionados.length === 0
                    ? "Selecione um lugar"
                    : `Reservar ${selecionados.length} lugar${selecionados.length > 1 ? "es" : ""}`}
              </Button>

              {selecionados.length > 0 && (
                <Button variant="ghost" className="mt-2 w-full" onClick={aoLimparEscolha}>
                  Limpar seleção
                </Button>
              )}

              <p className="mt-3 text-center text-xs text-muted">
                A reserva segura seus lugares antes do pagamento.
              </p>
            </>
          ) : (
            <>
              <div className="mb-4">
                <span id="rotulo-qtd" className="mb-2 block text-sm font-medium text-ink">
                  Quantidade
                </span>
                <div
                  className="flex items-center gap-1"
                  role="group"
                  aria-labelledby="rotulo-qtd"
                >
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setQtd((q) => Math.max(1, q - 1))}
                    disabled={qtd <= 1}
                    aria-label="Diminuir quantidade"
                    className="!w-9 !px-0 text-base"
                  >
                    −
                  </Button>
                  <output
                    aria-live="polite"
                    className="w-12 text-center text-lg font-semibold text-ink"
                  >
                    {qtd}
                  </output>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setQtd((q) => Math.min(maximo, q + 1))}
                    disabled={qtd >= maximo}
                    aria-label="Aumentar quantidade"
                    className="!w-9 !px-0 text-base"
                  >
                    +
                  </Button>
                  <span className="ml-2 text-xs text-muted">
                    {evento.available} disponíve{evento.available === 1 ? "l" : "is"}
                  </span>
                </div>
              </div>

              <div className="mb-4 flex items-baseline justify-between border-t border-line pt-4">
                <span className="text-sm font-medium text-ink">Total</span>
                <strong className="text-xl font-bold text-ink">{money(total)}</strong>
              </div>

              <Button
                size="lg"
                className="w-full"
                loading={ocupado}
                disabled={!ready}
                onClick={() => void reservar()}
              >
                {user ? "Reservar ingressos" : "Entrar para comprar"}
              </Button>

              <p className="mt-3 text-center text-xs text-muted">
                A reserva segura seus lugares antes do pagamento.
              </p>

              {user && user.role !== "CUSTOMER" && (
                <p className="mt-3 text-center text-xs text-warn">
                  Você está logado como {user.role === "ORGANIZER" ? "organizador" : "portaria"}.
                  Só contas de cliente compram ingressos.
                </p>
              )}
            </>
          )}
        </>
      )}

      {etapa === "confirmar" && reserva && (
        <>
          <Badge tone="warn">Aguardando pagamento</Badge>
          <h2 className="mt-3 text-lg font-bold text-ink">Confirme sua compra</h2>
          <p className="mt-1 text-sm text-muted">
            Seus {reserva.quantity} ingresso{reserva.quantity > 1 ? "s estão" : " está"}{" "}
            reservado{reserva.quantity > 1 ? "s" : ""}. Confirme para emitir.
          </p>

          {/* O prazo existe no servidor de qualquer forma; mostrar o relógio é
              o que impede o cliente de perder o lugar sem entender por quê. */}
          <div className="mt-3 flex items-center justify-between rounded border border-line bg-canvas px-3 py-2 text-sm">
            <span className="text-muted">Seus lugares estão guardados por</span>
            <ContagemRegressiva
              ate={reserva.expires_at}
              aoZerar={() => {
                setEtapa("escolha");
                setReserva(null);
                aoLimparEscolha();
                void aoComprar();
              }}
            />
          </div>

          <dl className="my-4 space-y-2 border-y border-line py-4 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted">Quantidade</dt>
              <dd className="font-medium text-ink">{reserva.quantity}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">Total</dt>
              <dd className="text-lg font-bold text-ink">{money(reserva.total_price)}</dd>
            </div>
          </dl>

          <Button size="lg" className="w-full" loading={ocupado} onClick={() => void pagar()}>
            Pagar {money(reserva.total_price)}
          </Button>
          <Button
            variant="ghost"
            className="mt-2 w-full"
            disabled={ocupado}
            onClick={() => void cancelar()}
          >
            Cancelar reserva
          </Button>

          <p className="mt-3 text-center text-xs text-muted">
            Cobrança simulada — nenhum valor é debitado.
          </p>
        </>
      )}

      {etapa === "pago" && (
        <div className="text-center">
          <div className="mx-auto mb-3 grid size-12 place-items-center rounded-full bg-ok-soft">
            <svg viewBox="0 0 20 20" className="size-6 fill-ok" aria-hidden="true">
              <path d="M8.1 13.6 4.9 10.4l1.2-1.2 2 2 5-5 1.2 1.2z" />
            </svg>
          </div>
          <h2 className="text-lg font-bold text-ink">Compra confirmada</h2>
          <p className="mt-1 text-sm text-muted">
            Seus ingressos foram emitidos com QR para a entrada.
          </p>
          <Link
            href="/minha-conta"
            className="mt-4 inline-flex h-11 w-full items-center justify-center rounded
              bg-accent px-6 font-semibold text-white hover:bg-accent-dark"
          >
            Ver meus ingressos
          </Link>
        </div>
      )}

      {etapa === "recusado" && (
        <div>
          <Alert tone="danger" title="Pagamento recusado">
            {motivo}
          </Alert>
          <p className="mt-3 text-sm text-muted">
            Os lugares voltaram para o estoque. Você pode tentar com uma quantidade menor.
          </p>
          <Button
            variant="secondary"
            className="mt-4 w-full"
            onClick={() => {
              setEtapa("escolha");
              setReserva(null);
              setQtd(1);
            }}
          >
            Escolher outra quantidade
          </Button>
        </div>
      )}

      {erro && (
        <div className="mt-4">
          <Alert tone="danger">{erro}</Alert>
        </div>
      )}
    </aside>
  );
}

function mensagemDeErro(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.data as { detail?: string } | null;
    if (d?.detail) return d.detail;
    if (e.status === 403) return "Sua conta não tem permissão para esta ação.";
    if (e.status === 401) return "Sua sessão expirou. Entre novamente.";
  }
  return "Algo deu errado. Tente novamente.";
}
