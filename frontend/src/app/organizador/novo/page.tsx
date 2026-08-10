"use client";

/**
 * Criar evento a partir do catálogo externo.
 *
 * Dois passos, porque o catálogo devolve uma SUGESTÃO e não um evento pronto:
 * um filme do TMDb não tem local nem sessão. O organizador escolhe o item e
 * então preenche o que só ele sabe — onde, quando, quanto e quantos lugares.
 *
 * A busca vai para o NOSSO backend, que fala com TMDb/Ticketmaster. A chave
 * das APIs nunca chega ao navegador.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert, Button, Field, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { CatalogItem, EventKind, OrganizerEvent, Source } from "@/lib/types";

const FONTES: { valor: Source; rotulo: string; dica: string }[] = [
  { valor: "TMDB", rotulo: "Filmes (TMDb)", dica: "Filmes em cartaz e catálogo completo" },
  {
    valor: "TICKETMASTER",
    rotulo: "Shows (Ticketmaster)",
    dica: "Cobertura maior em EUA/Europa — tente termos internacionais",
  },
];

export default function NovoEventoPage() {
  const { user, token, ready } = useAuth();
  const [fonte, setFonte] = useState<Source>("TMDB");
  const [termo, setTermo] = useState("");
  const [itens, setItens] = useState<CatalogItem[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [erroBusca, setErroBusca] = useState<string | null>(null);
  const [escolhido, setEscolhido] = useState<CatalogItem | null>(null);

  async function buscar(e?: React.FormEvent) {
    e?.preventDefault();
    setBuscando(true);
    setErroBusca(null);
    try {
      const p = new URLSearchParams({ source: fonte });
      if (termo.trim()) p.set("q", termo.trim());
      setItens(await api<CatalogItem[]>(`/api/catalog/search?${p}`, { token }));
    } catch (err) {
      setErroBusca(
        err instanceof ApiError && err.status === 503
          ? "Este catálogo está sem chave de API configurada no servidor."
          : err instanceof ApiError && err.status === 502
            ? "O catálogo externo não respondeu. Tente de novo em instantes."
            : "Não foi possível buscar no catálogo.",
      );
      setItens(null);
    } finally {
      setBuscando(false);
    }
  }

  if (!ready) return <Skeleton className="mx-auto mt-8 h-64 max-w-4xl" />;

  if (!user || user.role !== "ORGANIZER") {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="text-xl font-bold text-ink">Área do organizador</h1>
        <p className="mt-2 text-sm text-muted">
          Entre com uma conta de organizador para publicar eventos.
        </p>
        <Link
          href="/entrar"
          className="mt-4 inline-flex h-10 items-center rounded bg-accent px-5
            text-sm font-semibold text-white hover:bg-accent-dark"
        >
          Entrar
        </Link>
      </div>
    );
  }

  if (escolhido) {
    return <Formulario item={escolhido} onVoltar={() => setEscolhido(null)} />;
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <nav aria-label="Trilha" className="mb-4 text-xs text-muted">
        <Link href="/organizador" className="hover:text-brand">
          Meus eventos
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-body">Novo evento</span>
      </nav>

      <h1 className="text-2xl font-bold text-ink">Escolha no catálogo</h1>
      <p className="mt-1 text-sm text-muted">
        Busque o filme ou show. Depois você define local, data, preço e capacidade.
      </p>

      <div className="mt-6 flex gap-2" role="tablist" aria-label="Fonte do catálogo">
        {FONTES.map((f) => (
          <button
            key={f.valor}
            role="tab"
            aria-selected={fonte === f.valor}
            onClick={() => {
              setFonte(f.valor);
              setItens(null);
            }}
            className={`rounded border px-4 py-2 text-sm font-semibold transition-colors
              ${
                fonte === f.valor
                  ? "border-brand bg-brand text-white"
                  : "border-line-strong bg-white text-body hover:border-brand/40"
              }`}
          >
            {f.rotulo}
          </button>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">
        {FONTES.find((f) => f.valor === fonte)?.dica}
      </p>

      <form onSubmit={buscar} className="mt-4 flex gap-2">
        <label htmlFor="termo" className="sr-only">
          Buscar no catálogo
        </label>
        <input
          id="termo"
          value={termo}
          onChange={(e) => setTermo(e.target.value)}
          placeholder={fonte === "TMDB" ? "Ex.: Duna, Interestelar" : "Ex.: Coldplay, Eagles"}
          className="h-10 min-w-0 flex-1 rounded border border-line-strong bg-white
            px-3 text-sm text-ink placeholder:text-muted"
        />
        <Button type="submit" loading={buscando}>
          Buscar
        </Button>
      </form>
      <p className="mt-1.5 text-xs text-muted">
        Deixe vazio para ver {fonte === "TMDB" ? "os filmes em cartaz" : "os próximos shows"}.
      </p>

      {erroBusca && (
        <div className="mt-6">
          <Alert tone="danger">{erroBusca}</Alert>
        </div>
      )}

      {buscando && (
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="aspect-[2/3] w-full" />
          ))}
        </div>
      )}

      {itens && !buscando && itens.length === 0 && (
        <div className="mt-6">
          <Alert tone="warn" title="Nada encontrado">
            Nenhum resultado para esse termo neste catálogo.
          </Alert>
        </div>
      )}

      {itens && !buscando && itens.length > 0 && (
        <ul className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {itens.map((item) => (
            <li key={`${item.source}-${item.external_id}`}>
              <button
                onClick={() => setEscolhido(item)}
                className="group block w-full overflow-hidden rounded-card border
                  border-line bg-white text-left hover:border-brand"
              >
                <div className="aspect-[2/3] overflow-hidden bg-canvas">
                  {item.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={item.image_url}
                      alt=""
                      loading="lazy"
                      className="size-full object-cover"
                    />
                  ) : (
                    <div className="grid size-full place-items-center p-3 text-center text-xs text-muted">
                      {item.title}
                    </div>
                  )}
                </div>
                <div className="p-2.5">
                  <p className="line-clamp-2 text-sm font-semibold leading-snug text-ink">
                    {item.title}
                  </p>
                  {item.venue && (
                    <p className="mt-1 line-clamp-1 text-xs text-muted">{item.venue}</p>
                  )}
                  <span className="mt-2 inline-block text-xs font-semibold text-brand group-hover:underline">
                    Usar este
                  </span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Passo 2: completar o que o catálogo não sabe. */
function Formulario({ item, onVoltar }: { item: CatalogItem; onVoltar: () => void }) {
  const { token } = useAuth();
  const router = useRouter();

  // O catálogo pode já trazer local e data (Ticketmaster) ou não (TMDb).
  // Quando traz, vira valor inicial editável — nunca imposição.
  const [venue, setVenue] = useState(item.venue);
  const [startsAt, setStartsAt] = useState(
    item.starts_at ? paraInputLocal(item.starts_at) : "",
  );
  const [price, setPrice] = useState("");
  const [capacity, setCapacity] = useState("");
  const [kind, setKind] = useState<EventKind>("GA");
  const [secoes, setSecoes] = useState<SecaoForm[]>([
    { name: "Plateia", rows: 5, seats_per_row: 10, price: "80.00" },
  ]);
  const [publicar, setPublicar] = useState(true);
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const totalAssentos = secoes.reduce((s, x) => s + x.rows * x.seats_per_row, 0);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setOcupado(true);
    setErros({});
    setGeral(null);
    try {
      const comLugar = kind === "SEATED";

      const criado = await api<OrganizerEvent>("/api/organizer/events", {
        method: "POST",
        token,
        body: JSON.stringify({
          source: item.source,
          external_id: item.external_id,
          title: item.title,
          description: item.description,
          image_url: item.image_url,
          venue,
          // datetime-local devolve sem fuso; o Date converte usando o fuso do
          // navegador, e o toISOString manda em UTC — que é como o Django grava.
          starts_at: new Date(startsAt).toISOString(),
          kind,
          // Com lugar marcado o evento nasce em RASCUNHO mesmo que o
          // organizador tenha pedido para publicar: publicar antes de existir
          // mapa colocaria na vitrine um teatro sem poltrona nenhuma.
          status: publicar && !comLugar ? "PUBLISHED" : "DRAFT",
          // A capacidade de um evento com lugar marcado é derivada do mapa;
          // mandar 0 aqui e deixar o gerador de assentos escrever o total.
          price: comLugar ? "0.00" : price,
          capacity: comLugar ? 0 : Number(capacity),
        }),
      });

      if (comLugar) {
        // Monta o mapa e só então publica, se era o pedido.
        await api(`/api/organizer/events/${criado.id}/seats`, {
          method: "POST",
          token,
          body: JSON.stringify({
            sections: secoes.map((s) => ({
              name: s.name,
              rows: rotulosDeFila(s.rows),
              seats_per_row: s.seats_per_row,
              price: s.price,
            })),
          }),
        });
        if (publicar) {
          await api(`/api/organizer/events/${criado.id}`, {
            method: "PATCH",
            token,
            body: JSON.stringify({ status: "PUBLISHED" }),
          });
        }
      }

      router.push(publicar ? `/eventos/${criado.id}` : "/organizador");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        const dados = err.data as Record<string, string[] | string>;
        const mapeado: Record<string, string> = {};
        for (const [campo, msgs] of Object.entries(dados)) {
          mapeado[campo] = Array.isArray(msgs) ? msgs[0] : String(msgs);
        }
        setErros(mapeado);
      } else {
        setGeral("Não foi possível criar o evento.");
      }
      setOcupado(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <button
        onClick={onVoltar}
        className="mb-4 text-sm font-semibold text-brand hover:underline"
      >
        ← Escolher outro item
      </button>

      <div className="grid gap-6 sm:grid-cols-[140px_1fr]">
        <div className="overflow-hidden rounded-card border border-line bg-canvas">
          {item.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={item.image_url} alt="" className="aspect-[2/3] w-full object-cover" />
          ) : (
            <div className="aspect-[2/3]" />
          )}
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            {item.source === "TMDB" ? "Filme · TMDb" : "Show · Ticketmaster"}
          </p>
          <h1 className="mt-1 text-xl font-bold leading-tight text-ink">{item.title}</h1>
          {item.description && (
            <p className="mt-2 line-clamp-3 text-sm text-muted">{item.description}</p>
          )}
        </div>
      </div>

      <form onSubmit={salvar} className="mt-8 space-y-4">
        {geral && <Alert tone="danger">{geral}</Alert>}

        <Field
          label="Local"
          name="venue"
          required
          value={venue}
          onChange={(e) => setVenue(e.target.value)}
          error={erros.venue}
          placeholder="Ex.: Cinemark Eldorado, São Paulo"
          hint={item.venue ? "Veio do catálogo — edite se a sua sessão for em outro lugar." : undefined}
        />

        <Field
          label="Data e hora"
          name="starts_at"
          type="datetime-local"
          required
          value={startsAt}
          onChange={(e) => setStartsAt(e.target.value)}
          error={erros.starts_at}
          hint="Precisa ser no futuro."
        />

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-ink">Como vende o ingresso?</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {(
              [
                { valor: "GA", titulo: "Pista", texto: "Vende quantidade; entra quem chegar" },
                {
                  valor: "SEATED",
                  titulo: "Lugar marcado",
                  texto: "Cada ingresso é uma poltrona específica",
                },
              ] as const
            ).map((o) => (
              <label
                key={o.valor}
                className={`flex cursor-pointer items-start gap-3 rounded border p-3
                  ${
                    kind === o.valor
                      ? "border-brand bg-brand/4"
                      : "border-line-strong bg-white hover:border-brand/40"
                  }`}
              >
                <input
                  type="radio"
                  name="kind"
                  checked={kind === o.valor}
                  onChange={() => setKind(o.valor)}
                  className="mt-0.5 accent-brand"
                />
                <span>
                  <span className="block text-sm font-semibold text-ink">{o.titulo}</span>
                  <span className="block text-xs text-muted">{o.texto}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        {kind === "GA" ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Preço do ingresso (R$)"
              name="price"
              type="number"
              step="0.01"
              min="0"
              required
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              error={erros.price}
              placeholder="42.00"
            />
            <Field
              label="Capacidade (lugares)"
              name="capacity"
              type="number"
              min="1"
              required
              value={capacity}
              onChange={(e) => setCapacity(e.target.value)}
              error={erros.capacity}
              placeholder="120"
            />
          </div>
        ) : (
          <MontadorDeMapa
            secoes={secoes}
            onMudar={setSecoes}
            total={totalAssentos}
          />
        )}

        <label className="flex items-start gap-3 rounded border border-line-strong bg-white p-3">
          <input
            type="checkbox"
            checked={publicar}
            onChange={(e) => setPublicar(e.target.checked)}
            className="mt-0.5 accent-brand"
          />
          <span>
            <span className="block text-sm font-semibold text-ink">Publicar agora</span>
            <span className="block text-xs text-muted">
              Publicado aparece na vitrine e aceita compras. Desmarque para salvar como
              rascunho.
            </span>
          </span>
        </label>

        <div className="flex gap-2 pt-2">
          <Button type="submit" size="lg" loading={ocupado}>
            {publicar ? "Criar e publicar" : "Salvar rascunho"}
          </Button>
          <Button type="button" variant="ghost" size="lg" onClick={onVoltar}>
            Voltar
          </Button>
        </div>
      </form>
    </div>
  );
}

type SecaoForm = { name: string; rows: number; seats_per_row: number; price: string };

/**
 * Rótulos de fila: A, B, ... Z, AA, AB...
 *
 * O organizador informa QUANTAS filas; a nomeação é nossa. Pedir para digitar
 * "A,B,C,D,E" seria trabalho manual com erro garantido em sala grande.
 */
function rotulosDeFila(quantidade: number): string[] {
  const saida: string[] = [];
  for (let i = 0; i < quantidade; i++) {
    let n = i;
    let rotulo = "";
    do {
      rotulo = String.fromCharCode(65 + (n % 26)) + rotulo;
      n = Math.floor(n / 26) - 1;
    } while (n >= 0);
    saida.push(rotulo);
  }
  return saida;
}

function MontadorDeMapa({
  secoes,
  onMudar,
  total,
}: {
  secoes: SecaoForm[];
  onMudar: (s: SecaoForm[]) => void;
  total: number;
}) {
  function atualizar(i: number, campo: keyof SecaoForm, valor: string | number) {
    onMudar(secoes.map((s, idx) => (idx === i ? { ...s, [campo]: valor } : s)));
  }

  return (
    <div className="rounded-card border border-line-strong bg-white p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-ink">Mapa de assentos</h2>
        <span className="text-xs text-muted">
          {total} {total === 1 ? "lugar" : "lugares"} no total
        </span>
      </div>

      <div className="space-y-3">
        {secoes.map((s, i) => (
          <div key={i} className="rounded border border-line p-3">
            <div className="grid gap-2 sm:grid-cols-[1fr_5rem_5rem_6rem]">
              <label className="text-xs text-muted">
                Seção
                <input
                  value={s.name}
                  onChange={(e) => atualizar(i, "name", e.target.value)}
                  className="mt-1 h-9 w-full rounded border border-line-strong px-2 text-sm text-ink"
                />
              </label>
              <label className="text-xs text-muted">
                Filas
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={s.rows}
                  onChange={(e) => atualizar(i, "rows", Math.max(1, Number(e.target.value)))}
                  className="mt-1 h-9 w-full rounded border border-line-strong px-2 text-sm text-ink"
                />
              </label>
              <label className="text-xs text-muted">
                Por fila
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={s.seats_per_row}
                  onChange={(e) =>
                    atualizar(i, "seats_per_row", Math.max(1, Number(e.target.value)))
                  }
                  className="mt-1 h-9 w-full rounded border border-line-strong px-2 text-sm text-ink"
                />
              </label>
              <label className="text-xs text-muted">
                Preço (R$)
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={s.price}
                  onChange={(e) => atualizar(i, "price", e.target.value)}
                  className="mt-1 h-9 w-full rounded border border-line-strong px-2 text-sm text-ink"
                />
              </label>
            </div>

            <div className="mt-2 flex items-center justify-between">
              <p className="text-xs text-muted">
                Filas {rotulosDeFila(s.rows)[0]} a {rotulosDeFila(s.rows).at(-1)} ·{" "}
                {s.rows * s.seats_per_row} lugares
              </p>
              {secoes.length > 1 && (
                <button
                  type="button"
                  onClick={() => onMudar(secoes.filter((_, idx) => idx !== i))}
                  className="text-xs font-semibold text-danger hover:underline"
                >
                  Remover seção
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <Button
        type="button"
        variant="secondary"
        size="sm"
        className="mt-3"
        onClick={() =>
          onMudar([
            ...secoes,
            { name: `Seção ${secoes.length + 1}`, rows: 3, seats_per_row: 8, price: "50.00" },
          ])
        }
      >
        Adicionar seção
      </Button>

      <p className="mt-3 text-xs text-muted">
        O mapa só pode ser refeito enquanto nenhum lugar tiver sido vendido.
      </p>
    </div>
  );
}

/** ISO com fuso -> "YYYY-MM-DDTHH:mm", que é o que datetime-local aceita. */
function paraInputLocal(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
