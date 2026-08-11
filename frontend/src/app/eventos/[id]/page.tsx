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

import { EventCard } from "@/components/event-card";
import { SeatMap } from "@/components/seat-map";
import { Alert, Badge, Button, ContagemRegressiva, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateParts, fullDate, money, preco } from "@/lib/format";
import type {
  PayResponse,
  PublicEvent,
  RelatedEvents,
  Reservation,
  Seat,
} from "@/lib/types";

const MAX_POR_COMPRA = 8;

export default function EventoPage() {
  const { id } = useParams<{ id: string }>();
  const [evento, setEvento] = useState<PublicEvent | null>(null);
  const [assentos, setAssentos] = useState<Seat[]>([]);
  const [relacionados, setRelacionados] = useState<RelatedEvents | null>(null);
  const [escolhidos, setEscolhidos] = useState<Set<number>>(new Set());
  const [erro, setErro] = useState<string | null>(null);

  // O relógio é lido UMA vez, na montagem, e não a cada render. Ler Date.now()
  // durante o render torna o componente impuro: duas renderizações com o mesmo
  // estado poderiam produzir telas diferentes, e o compilador do React conta
  // com essa pureza para reaproveitar trabalho.
  const [aberturaDaPagina] = useState(() => Date.now());

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

  // Busca própria, depois da principal e sem bloquear nada: as sugestões vivem
  // abaixo da dobra, e uma falha ali não pode impedir a compra desta sessão.
  const carregarRelacionados = useCallback(async () => {
    try {
      setRelacionados(await api<RelatedEvents>(`/api/events/${id}/related`));
    } catch {
      setRelacionados(null);
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
    void carregarRelacionados();
  }, [carregar, carregarRelacionados]);

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

  // A sessão já passou. A página continua existindo — quem foi ao evento tem o
  // link em "Meus ingressos" e o cartaz é a lembrança da sessão —, mas tudo o
  // que leva a comprar sai do caminho. O backend recusaria a reserva de
  // qualquer jeito ("Este evento já começou"); deixar o botão na tela só
  // convidaria o cliente a percorrer o fluxo inteiro até levar um erro.
  const encerrado = new Date(evento.starts_at).getTime() <= aberturaDaPagina;

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

          <ComoChegar venue={evento.venue} />

          {evento.kind === "SEATED" && !encerrado && (
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
            {encerrado ? (
              <div className="rounded-card border border-line bg-white p-5">
                <Alert tone="info" title="Este evento já aconteceu">
                  A sessão foi em <span className="lowercase">{fullDate(evento.starts_at)}</span>.
                  Não é mais possível comprar ingressos.
                </Alert>
                <Link
                  href="/"
                  className="mt-4 inline-block text-sm font-semibold text-brand hover:underline"
                >
                  Ver o que está em cartaz →
                </Link>
              </div>
            ) : (
              <PainelCompra
                evento={evento}
                assentos={assentos}
                escolhidos={escolhidos}
                aoLimparEscolha={() => setEscolhidos(new Set())}
                aoComprar={carregar}
              />
            )}

            <OutrosHorarios eventos={relacionados?.same_title ?? []} />
          </div>
        </div>
      </div>

      <Relacionados eventos={relacionados?.others ?? []} />
    </div>
  );
}

/**
 * "Como chegar".
 *
 * Link para o mapa, e não um mapa embutido. Um iframe do Google Maps carrega
 * scripts e cookies de terceiro em TODA visita à página, inclusive de quem só
 * queria ver o preço — e o local aqui é texto livre digitado pelo organizador,
 * então o pino cairia no lugar errado com frequência. O link resolve o mesmo
 * problema real (chegar lá), sem chave de API, sem custo por carregamento e
 * sem entregar o passo do visitante a um terceiro antes de ele pedir.
 */
function ComoChegar({ venue }: { venue: string }) {
  const busca = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue)}`;

  return (
    <div className="mt-8">
      <h2 className="mb-2 text-base font-semibold text-ink">Como chegar</h2>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-card
        border border-line bg-white p-4">
        <p className="text-sm font-medium text-body">{venue}</p>
        <a
          href={busca}
          target="_blank"
          // noopener: sem isto a aba aberta recebe window.opener e pode
          // reescrever o endereço desta. noreferrer não manda de onde veio.
          rel="noopener noreferrer"
          className="inline-flex h-9 shrink-0 items-center rounded border
            border-line-strong px-3 text-[13px] font-semibold text-ink hover:bg-canvas"
        >
          Ver no mapa
        </a>
      </div>
    </div>
  );
}

/**
 * Outras sessões do MESMO filme, ao lado da compra.
 *
 * Lista compacta, e não cards com pôster: é o mesmo filme, então a arte seria
 * a mesma repetida — dois cartazes idênticos lado a lado parecem defeito de
 * renderização, e o que diferencia as sessões é justamente o que o pôster não
 * mostra (dia, cinema, preço).
 *
 * Fica junto do painel de compra, e não lá embaixo, porque é aqui que a
 * pergunta nasce: quem vê "esgotado" ou um horário ruim quer a alternativa no
 * mesmo lance de olhos, não depois de rolar a página inteira.
 */
function OutrosHorarios({ eventos }: { eventos: PublicEvent[] }) {
  if (eventos.length === 0) return null;

  return (
    <section className="mt-4 overflow-hidden rounded-card border border-line bg-white">
      <h2 className="border-b border-line px-4 py-2.5 text-sm font-semibold text-ink">
        Outros horários deste filme
      </h2>
      <ul>
        {eventos.map((e) => {
          const { dia, mes, hora } = dateParts(e.starts_at);
          return (
            <li key={e.id} className="border-b border-line last:border-b-0">
              <Link
                href={`/eventos/${e.id}`}
                className="flex items-center gap-3 px-4 py-3 hover:bg-canvas"
              >
                <span className="shrink-0 rounded border border-line bg-canvas px-2 py-1
                  text-center leading-none">
                  <span className="block text-sm font-bold text-ink">{dia}</span>
                  <span className="block text-[9px] font-semibold tracking-wider text-muted">
                    {mes}
                  </span>
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-body">
                    {e.venue}
                  </span>
                  <span className="block text-xs text-muted">
                    às {hora} · {e.available > 0 ? preco(e.price_from) : "Esgotado"}
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * A metade de baixo da página, que antes acabava no meio do nada.
 *
 * Não renderiza esqueleto: é conteúdo abaixo da dobra, e um bloco cinza
 * piscando no rodapé chama mais atenção do que a informação que ele substitui.
 */
function Relacionados({ eventos }: { eventos: PublicEvent[] }) {
  if (eventos.length === 0) return null;

  return (
    <section className="mt-12 border-t border-line pt-8">
      <h2 className="mb-3 text-lg font-bold text-ink">Também em cartaz</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {eventos.map((e) => (
          <EventCard key={e.id} event={e} />
        ))}
      </div>
    </section>
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
