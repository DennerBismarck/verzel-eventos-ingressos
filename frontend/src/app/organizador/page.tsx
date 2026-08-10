"use client";

/**
 * Painel do organizador: resumo das vendas, lista dos próprios eventos e
 * publicação.
 *
 * A API já devolve só os eventos deste organizador (filtro no get_queryset do
 * Django). Não existe filtro por dono aqui no front — se existisse, seria
 * decoração: a lista viria completa e bastaria abrir o DevTools.
 *
 * Filtro, ordenação e a separação futuro/passado também são do servidor. A
 * lista é paginada de 12 em 12: filtrar aqui só reordenaria a página atual e
 * esconderia o resto, sem avisar ninguém.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Alert, Badge, Button, EmptyState, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { money, preco, shortDate } from "@/lib/format";
import type {
  EventStatus,
  OrganizerEvent,
  OrganizerSummary,
  Page,
} from "@/lib/types";

type Aba = "upcoming" | "past";
type Ordem = "data" | "vendas" | "criacao";

const ORDENS: { valor: Ordem; rotulo: string; param: (aba: Aba) => string }[] = [
  {
    valor: "data",
    rotulo: "Data do evento",
    // A leitura natural muda com a aba: entre os futuros interessa o que vem
    // primeiro; entre os passados, o que acabou de acontecer.
    param: (aba) => (aba === "past" ? "-starts_at" : "starts_at"),
  },
  { valor: "vendas", rotulo: "Mais vendidos", param: () => "-sold_count" },
  { valor: "criacao", rotulo: "Criado recentemente", param: () => "-created_at" },
];

const STATUS: { valor: "" | EventStatus; rotulo: string }[] = [
  { valor: "", rotulo: "Todos" },
  { valor: "PUBLISHED", rotulo: "Publicados" },
  { valor: "DRAFT", rotulo: "Rascunhos" },
];

export default function OrganizadorPage() {
  const { user, token, ready } = useAuth();

  const [resumo, setResumo] = useState<OrganizerSummary | null>(null);
  const [eventos, setEventos] = useState<OrganizerEvent[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<number | null>(null);
  const [recarregando, setRecarregando] = useState(false);

  const [aba, setAba] = useState<Aba>("upcoming");
  const [status, setStatus] = useState<"" | EventStatus>("");
  const [ordem, setOrdem] = useState<Ordem>("data");

  const carregarResumo = useCallback(async () => {
    if (!token) return;
    try {
      setResumo(await api<OrganizerSummary>("/api/organizer/summary", { token }));
    } catch {
      // O resumo é acessório: se ele falhar, a lista ainda serve. Some da tela
      // em vez de bloquear o painel inteiro com um erro.
      setResumo(null);
    }
  }, [token]);

  const carregarLista = useCallback(async () => {
    if (!token) return;
    setRecarregando(true);
    try {
      const busca = new URLSearchParams({
        when: aba,
        ordering: ORDENS.find((o) => o.valor === ordem)!.param(aba),
      });
      if (status) busca.set("status", status);

      const r = await api<Page<OrganizerEvent>>(`/api/organizer/events?${busca}`, { token });
      setEventos(r.results);
      setErro(null);
    } catch {
      setErro("Não conseguimos carregar seus eventos.");
    } finally {
      setRecarregando(false);
    }
  }, [token, aba, status, ordem]);

  useEffect(() => {
    void carregarResumo();
  }, [carregarResumo]);

  useEffect(() => {
    void carregarLista();
  }, [carregarLista]);

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
      // O resumo também muda: despublicar tira o evento do "próximo evento".
      await Promise.all([carregarLista(), carregarResumo()]);
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

  const semNenhumEvento =
    resumo !== null && resumo.upcoming_count === 0 && resumo.past_count === 0;

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

      <Resumo dados={resumo} />

      {erro && (
        <div className="mb-4">
          <Alert tone="danger">{erro}</Alert>
        </div>
      )}

      {!semNenhumEvento && (
        <Controles
          aba={aba}
          setAba={setAba}
          status={status}
          setStatus={setStatus}
          ordem={ordem}
          setOrdem={setOrdem}
          resumo={resumo}
        />
      )}

      {!eventos && <Skeleton className="h-48 w-full" />}

      {eventos && eventos.length === 0 && (
        semNenhumEvento ? (
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
        ) : (
          <EmptyState title="Nenhum evento com esses filtros">
            {aba === "past"
              ? "Nenhum evento seu já aconteceu com esse status."
              : "Nenhum evento futuro com esse status. Veja a aba dos que já aconteceram."}
          </EmptyState>
        )
      )}

      {eventos && eventos.length > 0 && (
        <div className={`space-y-3 transition-opacity ${recarregando ? "opacity-50" : ""}`}>
          {eventos.map((ev) => (
            <LinhaDoEvento
              key={ev.id}
              ev={ev}
              passado={aba === "past"}
              ocupado={ocupado === ev.id}
              onPublicar={() => void alternarPublicacao(ev)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- resumo */

function Resumo({ dados }: { dados: OrganizerSummary | null }) {
  if (!dados) {
    return (
      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  const proximo = dados.next_event;

  return (
    <div className="mb-6 grid gap-3 sm:grid-cols-3">
      <Card titulo="Receita confirmada" rodape="só reservas pagas">
        <span className="text-2xl font-bold text-ink">{money(dados.revenue)}</span>
      </Card>

      {/* Conta INGRESSO, e não o "vendidos" das barras abaixo: aquele número
          sobe já na reserva, que ainda pode não ser paga. Aqui só entra o que
          virou ingresso — assim o total anda junto com a receita ao lado. */}
      <Card titulo="Ingressos vendidos" rodape="emitidos após o pagamento">
        <span className="text-2xl font-bold text-ink">{dados.tickets_sold}</span>
      </Card>

      <Card titulo="Próximo evento" rodape={proximo ? proximo.venue : undefined}>
        {proximo ? (
          <Link href={`/organizador/vendas/${proximo.id}`} className="block group">
            <span className="block text-xs font-semibold text-brand">
              {shortDate(proximo.starts_at)}
            </span>
            <span className="block truncate font-bold text-ink group-hover:underline">
              {proximo.title}
            </span>
            <span className="block text-xs text-muted">
              {proximo.sold_count}/{proximo.capacity} vendidos
            </span>
          </Link>
        ) : (
          <span className="text-sm text-muted">
            Nenhum evento publicado à frente.
          </span>
        )}
      </Card>
    </div>
  );
}

function Card({
  titulo,
  rodape,
  children,
}: {
  titulo: string;
  rodape?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-card border border-line bg-white p-4">
      <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
        {titulo}
      </h2>
      <div className="mt-1.5">{children}</div>
      {rodape && <p className="mt-1 truncate text-xs text-muted">{rodape}</p>}
    </section>
  );
}

/* -------------------------------------------------------------- controles */

function Controles({
  aba,
  setAba,
  status,
  setStatus,
  ordem,
  setOrdem,
  resumo,
}: {
  aba: Aba;
  setAba: (v: Aba) => void;
  status: "" | EventStatus;
  setStatus: (v: "" | EventStatus) => void;
  ordem: Ordem;
  setOrdem: (v: Ordem) => void;
  resumo: OrganizerSummary | null;
}) {
  const abas: { valor: Aba; rotulo: string; total?: number }[] = [
    { valor: "upcoming", rotulo: "Próximos", total: resumo?.upcoming_count },
    { valor: "past", rotulo: "Já aconteceram", total: resumo?.past_count },
  ];

  return (
    <div className="mb-4 border-b border-line">
      <div className="flex flex-wrap items-end justify-between gap-3">
        {/* Abas com sublinhado, e não um <select> de período: são só duas
            opções e a mais usada precisa estar a um clique. */}
        <div className="flex gap-1" role="group" aria-label="Período">
          {abas.map((a) => (
            <button
              key={a.valor}
              onClick={() => setAba(a.valor)}
              aria-pressed={aba === a.valor}
              className={`-mb-px border-b-2 px-3 pb-2 pt-1 text-sm font-semibold
                transition-colors ${
                  aba === a.valor
                    ? "border-accent text-ink"
                    : "border-transparent text-muted hover:text-body"
                }`}
            >
              {a.rotulo}
              {a.total !== undefined && (
                <span className="ml-1.5 text-xs font-normal text-muted">{a.total}</span>
              )}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2 pb-2">
          <div className="flex gap-1.5" role="group" aria-label="Filtrar por status">
            {STATUS.map((s) => (
              <button
                key={s.valor}
                onClick={() => setStatus(s.valor)}
                aria-pressed={status === s.valor}
                className={`h-8 rounded-full border px-3 text-[13px] font-medium
                  transition-colors ${
                    status === s.valor
                      ? "border-brand bg-brand text-white"
                      : "border-line-strong bg-white text-body hover:border-brand/40"
                  }`}
              >
                {s.rotulo}
              </button>
            ))}
          </div>

          <label htmlFor="ordenar" className="sr-only">
            Ordenar por
          </label>
          <select
            id="ordenar"
            value={ordem}
            onChange={(e) => setOrdem(e.target.value as Ordem)}
            className="h-8 rounded border border-line-strong bg-white px-2 text-[13px] text-body"
          >
            {ORDENS.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.rotulo}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ linha */

function LinhaDoEvento({
  ev,
  passado,
  ocupado,
  onPublicar,
}: {
  ev: OrganizerEvent;
  passado: boolean;
  ocupado: boolean;
  onPublicar: () => void;
}) {
  const vendidoPct = ev.capacity ? Math.round((ev.sold_count / ev.capacity) * 100) : 0;

  return (
    <article
      className="flex flex-wrap items-center gap-4 rounded-card border
        border-line bg-white p-4"
    >
      {/* 2:3 fixo, igual ao resto do site. Antes era 14×20 (0,70) contra um
          pôster 0,67, e o object-cover centralizado comia a testa de quem
          estivesse na arte. object-top corta pelo pé, que é onde não há rosto. */}
      <div className="w-14 shrink-0 overflow-hidden rounded border border-line bg-canvas">
        <div className="relative aspect-[2/3]">
          {ev.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={ev.image_url}
              alt=""
              className="size-full object-cover object-top"
            />
          ) : null}
        </div>
      </div>

      <div className="min-w-40 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold text-ink">{ev.title}</h3>
          {ev.status === "PUBLISHED" ? (
            <Badge tone="ok">Publicado</Badge>
          ) : (
            <Badge tone="warn">Rascunho</Badge>
          )}
          {passado && <Badge>Encerrado</Badge>}
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

      <div className="flex items-center gap-2">
        <Link
          href={`/organizador/vendas/${ev.id}`}
          className="inline-flex h-8 items-center rounded border
            border-line-strong px-3 text-[13px] font-semibold text-ink
            hover:bg-canvas"
        >
          Vendas
        </Link>

        {/* Publicar continua à vista: num rascunho é A ação da linha, e
            escondê-la num menu obrigaria a caçar o botão principal. */}
        {ev.status === "DRAFT" ? (
          <Button size="sm" loading={ocupado} onClick={onPublicar}>
            Publicar
          </Button>
        ) : (
          <MenuDeAcoes titulo={ev.title}>
            <ItemDeMenu href={`/eventos/${ev.id}`}>Ver página pública</ItemDeMenu>
            {/* Despublicar tira o evento do ar para todo mundo. É raro e é
                perigoso — vive no menu, longe do dedo que ia clicar em Vendas. */}
            <ItemDeMenu onClick={onPublicar} perigo>
              {ocupado ? "Despublicando…" : "Despublicar"}
            </ItemDeMenu>
          </MenuDeAcoes>
        )}
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------- menu */

function MenuDeAcoes({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  const [aberto, setAberto] = useState(false);
  const caixa = useRef<HTMLDivElement>(null);

  // Esc fecha e devolve o foco ao botão — sem isso o teclado fica preso num
  // menu que sumiu da tela mas continua sendo o último ponto focado.
  useEffect(() => {
    if (!aberto) return;
    function aoTeclar(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setAberto(false);
        caixa.current?.querySelector("button")?.focus();
      }
    }
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [aberto]);

  return (
    <div className="relative" ref={caixa}>
      <button
        onClick={() => setAberto((v) => !v)}
        aria-expanded={aberto}
        aria-haspopup="menu"
        aria-label={`Mais ações para ${titulo}`}
        className="grid size-8 place-items-center rounded border border-line-strong
          text-ink hover:bg-canvas"
      >
        <span aria-hidden="true" className="text-lg leading-none">
          ⋯
        </span>
      </button>

      {aberto && (
        <>
          {/* Camada invisível: clicar em qualquer lugar fora fecha o menu. */}
          <button
            aria-hidden="true"
            tabIndex={-1}
            onClick={() => setAberto(false)}
            className="fixed inset-0 z-10 cursor-default"
          />
          <div
            role="menu"
            onClick={() => setAberto(false)}
            className="absolute right-0 z-20 mt-1 w-52 overflow-hidden rounded-card
              border border-line bg-white py-1 text-left shadow-lg"
          >
            {children}
          </div>
        </>
      )}
    </div>
  );
}

function ItemDeMenu({
  href,
  onClick,
  perigo,
  children,
}: {
  href?: string;
  onClick?: () => void;
  perigo?: boolean;
  children: React.ReactNode;
}) {
  const classe = `block w-full px-3 py-2 text-left text-sm hover:bg-canvas ${
    perigo ? "text-danger" : "text-body"
  }`;

  return href ? (
    <Link role="menuitem" href={href} className={classe}>
      {children}
    </Link>
  ) : (
    <button role="menuitem" onClick={onClick} className={classe}>
      {children}
    </button>
  );
}
