"use client";

/**
 * Tela da portaria.
 *
 * Feita para ser usada em pé, num celular, com pressa e má iluminação. Três
 * consequências que moldaram tudo aqui:
 *
 *   - o resultado ocupa meia tela e some sozinho em 2s. Quem está na porta não
 *     tem mão livre para fechar aviso a cada pessoa;
 *   - o campo manual aceita o código de 8 caracteres, não o UUID. Ninguém dita
 *     36 caracteres com hífen numa fila;
 *   - o erro tem volta. A portaria lê o QR de quem está atrás, toca duas vezes,
 *     e sem desfazer a saída seria o cliente ficar de fora.
 *
 * A tela NÃO decide nada. Ela manda o que leu e o evento selecionado; o backend
 * confere a assinatura, trava a linha do ingresso e responde uma das quatro
 * situações.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Alert, Button, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { shortDate } from "@/lib/format";
import type { GateEvent, GateResponse, GateResult, Scan } from "@/lib/types";

const ID_LEITOR = "leitor-qr";
/** Quanto tempo o resultado fica na tela antes de liberar o próximo. */
const TEMPO_DO_RESULTADO = 2000;
/** Quantas leituras ficam disponíveis para desfazer. */
const HISTORICO = 5;

const APARENCIA: Record<
  GateResult,
  { fundo: string; titulo: string; icone: "ok" | "x" | "alerta" }
> = {
  VALID: { fundo: "bg-ok", titulo: "Pode entrar", icone: "ok" },
  ALREADY_USED: { fundo: "bg-warn", titulo: "Já utilizado", icone: "alerta" },
  WRONG_EVENT: { fundo: "bg-brand", titulo: "Outra sessão", icone: "alerta" },
  INVALID: { fundo: "bg-danger", titulo: "Não vale", icone: "x" },
};

export default function PortariaPage() {
  const { user, ready } = useAuth();
  const [eventos, setEventos] = useState<GateEvent[] | null>(null);
  const [eventoId, setEventoId] = useState<number | null>(null);
  const [resultado, setResultado] = useState<GateResponse | null>(null);
  const [historico, setHistorico] = useState<Scan[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [manual, setManual] = useState("");

  const carregarEventos = useCallback(async () => {
    try {
      const lista = await api<GateEvent[]>("/api/gate/events");
      setEventos(lista);
      setEventoId((atual) => atual ?? (lista.length === 1 ? lista[0].id : null));
    } catch {
      setErro("Não conseguimos carregar a lista de eventos.");
    }
  }, []);

  useEffect(() => {
    if (ready && user?.role === "GATE") void carregarEventos();
  }, [ready, user, carregarEventos]);

  const evento = eventos?.find((e) => e.id === eventoId) ?? null;

  const validar = useCallback(
    async (payload: string) => {
      if (!eventoId || !payload.trim()) return;
      setEnviando(true);
      setErro(null);
      try {
        const r = await api<GateResponse>("/api/gate/validate", {
          method: "POST",
          body: JSON.stringify({ payload: payload.trim(), event: eventoId }),
        });
        setResultado(r);
        avisar(r.result);
        setHistorico((atual) =>
          [
            {
              id: `${Date.now()}-${Math.random()}`,
              resultado: r.result,
              detalhe: r.detail,
              nome: r.ticket?.customer_name,
              lugar: r.ticket?.seat_label,
              code: r.result === "VALID" ? r.ticket?.code : undefined,
              quando: Date.now(),
            },
            ...atual,
          ].slice(0, HISTORICO),
        );
        // Recarrega o placar: é o número que a portaria acompanha a noite toda.
        void carregarEventos();
      } catch {
        setErro("Falha ao falar com o servidor. Tente novamente.");
      } finally {
        setEnviando(false);
        setManual("");
      }
    },
    [eventoId, carregarEventos],
  );

  async function desfazer(scan: Scan) {
    if (!scan.code) return;
    try {
      await api("/api/gate/undo", {
        method: "POST",
        body: JSON.stringify({ code: scan.code }),
      });
      setHistorico((atual) => atual.filter((s) => s.id !== scan.id));
      void carregarEventos();
    } catch (e) {
      setErro(
        e instanceof ApiError && e.status === 409
          ? ((e.data as { detail?: string })?.detail ?? "Não foi possível desfazer.")
          : "Não foi possível desfazer.",
      );
    }
  }

  if (!ready) return <Skeleton className="mx-auto mt-8 h-64 max-w-md" />;

  if (!user || user.role !== "GATE") {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="text-xl font-bold text-ink">Acesso da portaria</h1>
        <p className="mt-2 text-sm text-muted">
          {user
            ? "Sua conta não é de portaria."
            : "Entre com a conta de portaria para validar ingressos."}
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
    <div className="mx-auto max-w-md px-4 py-5">
      <div className="mb-4">
        <label htmlFor="evento" className="mb-1.5 block text-sm font-medium text-ink">
          Sessão nesta entrada
        </label>
        {!eventos ? (
          <Skeleton className="h-11 w-full" />
        ) : (
          <select
            id="evento"
            value={eventoId ?? ""}
            onChange={(e) => {
              setEventoId(e.target.value ? Number(e.target.value) : null);
              setResultado(null);
              setHistorico([]);
            }}
            className="h-11 w-full rounded border border-line-strong bg-white px-3 text-sm text-ink"
          >
            <option value="">Selecione…</option>
            {eventos.map((ev) => (
              <option key={ev.id} value={ev.id}>
                {ev.title} — {shortDate(ev.starts_at)}
              </option>
            ))}
          </select>
        )}
      </div>

      {evento && <Placar evento={evento} />}

      {erro && (
        <div className="mt-4">
          <Alert tone="danger">{erro}</Alert>
        </div>
      )}

      {!eventoId && (
        <div className="mt-6 rounded-card border border-dashed border-line-strong bg-white px-6 py-10 text-center">
          <p className="font-semibold text-ink">Escolha a sessão para começar</p>
          <p className="mx-auto mt-1 max-w-xs text-sm text-muted">
            A câmera e a digitação manual aparecem em seguida.
          </p>
        </div>
      )}

      {eventoId && (
        <>
          <div className="mt-5">
            <Leitor ativo={!resultado && !enviando} onLer={validar} />
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              void validar(manual);
            }}
            className="mt-4"
          >
            <label htmlFor="manual" className="mb-1.5 block text-sm font-medium text-ink">
              Ou digite o código do ingresso
            </label>
            <div className="flex gap-2">
              <input
                id="manual"
                value={manual}
                onChange={(e) => setManual(e.target.value.toUpperCase())}
                placeholder="A7K2M9QP"
                maxLength={40}
                autoComplete="off"
                autoCapitalize="characters"
                autoCorrect="off"
                spellCheck={false}
                // inputMode text e não numeric: o código mistura letra e número.
                className="h-12 min-w-0 flex-1 rounded border border-line-strong bg-white
                  px-3 text-center font-mono text-lg tracking-[0.2em] text-ink
                  placeholder:tracking-normal placeholder:text-muted"
              />
              <Button type="submit" size="lg" loading={enviando} disabled={!manual.trim()}>
                Validar
              </Button>
            </div>
            {/* Regra, não justificativa da funcionalidade. */}
            <p className="mt-1.5 text-xs text-muted">
              São 8 caracteres, impressos no ingresso. O ingresso precisa ser desta
              sessão.
            </p>
          </form>

          {historico.length > 0 && (
            <Historico itens={historico} onDesfazer={desfazer} />
          )}
        </>
      )}

      {resultado && (
        <PainelResultado
          resultado={resultado}
          onFechar={() => setResultado(null)}
        />
      )}
    </div>
  );
}

/** Placar de entradas — o número que a portaria acompanha a noite inteira. */
function Placar({ evento }: { evento: GateEvent }) {
  const pct = evento.tickets_total
    ? Math.round((evento.tickets_used / evento.tickets_total) * 100)
    : 0;

  return (
    <div className="rounded-card border border-line bg-white p-4">
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">
          Validados
        </span>
        <span aria-live="polite" className="text-2xl font-bold tabular-nums text-ink">
          {evento.tickets_used}
          <span className="text-base font-normal text-muted">/{evento.tickets_total}</span>
        </span>
      </div>
      <div
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-line"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${pct}% dos ingressos validados`}
      >
        <div className="h-full bg-ok transition-all" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1.5 text-xs text-muted">{evento.venue}</p>
    </div>
  );
}

function Historico({
  itens,
  onDesfazer,
}: {
  itens: Scan[];
  onDesfazer: (s: Scan) => void;
}) {
  return (
    <section className="mt-6">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
        Últimas leituras
      </h2>
      <ul className="divide-y divide-line overflow-hidden rounded-card border border-line bg-white">
        {itens.map((s) => (
          <li key={s.id} className="flex items-center gap-3 px-3 py-2.5">
            <span
              aria-hidden="true"
              className={`size-2 shrink-0 rounded-full ${
                s.resultado === "VALID"
                  ? "bg-ok"
                  : s.resultado === "INVALID"
                    ? "bg-danger"
                    : "bg-warn"
              }`}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">
                {s.nome ?? APARENCIA[s.resultado].titulo}
              </p>
              <p className="truncate text-xs text-muted">
                {s.lugar ? `${s.lugar} · ` : ""}
                {new Date(s.quando).toLocaleTimeString("pt-BR", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            </div>
            {/* Desfazer só aparece no que foi validado: não há o que reverter
                num ingresso recusado. */}
            {s.code && (
              <button
                onClick={() => onDesfazer(s)}
                className="shrink-0 rounded border border-line-strong px-2.5 py-1
                  text-xs font-semibold text-ink hover:bg-canvas"
              >
                Desfazer
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function PainelResultado({
  resultado,
  onFechar,
}: {
  resultado: GateResponse;
  onFechar: () => void;
}) {
  const { fundo, titulo, icone } = APARENCIA[resultado.result];

  // Some sozinho. Quem está na porta não tem mão livre para fechar um aviso a
  // cada pessoa que passa — e uma tela que exige toque vira gargalo na fila.
  useEffect(() => {
    const id = setTimeout(onFechar, TEMPO_DO_RESULTADO);
    return () => clearTimeout(id);
  }, [onFechar]);

  return (
    <div
      role="alert"
      onClick={onFechar}
      className={`fixed inset-x-0 top-0 z-50 flex min-h-[55vh] flex-col items-center
        justify-center gap-3 p-6 text-center text-white ${fundo}`}
    >
      <Icone tipo={icone} />
      {/* text-white explícito: a regra global `h2 { color: ink }` vence a cor
          herdada e deixaria o título ilegível no fundo colorido. */}
      <h2 className="text-4xl font-bold text-white">{titulo}</h2>

      {resultado.ticket && (
        <p className="text-lg font-semibold text-white">
          {resultado.ticket.customer_name}
          {resultado.ticket.seat_label && ` · ${resultado.ticket.seat_label}`}
        </p>
      )}
      <p className="max-w-xs text-sm text-white/90">{resultado.detail}</p>

      <p className="mt-2 text-xs text-white/70">toque para fechar agora</p>
    </div>
  );
}

function Icone({ tipo }: { tipo: "ok" | "x" | "alerta" }) {
  const d = {
    ok: "M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z",
    x: "M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z",
    alerta: "M1 21h22L12 2zm12-3h-2v-2h2zm0-4h-2v-4h2z",
  }[tipo];
  return (
    <svg viewBox="0 0 24 24" className="size-20 fill-white" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

type EstadoCamera = "iniciando" | "permissao" | "lendo" | "negada" | "indisponivel";

type Leitor5Qrcode = {
  start: (...a: unknown[]) => Promise<void>;
  stop: () => Promise<void>;
  clear: () => void;
};

/**
 * Leitor de câmera.
 *
 * A biblioteca mexe direto no DOM e só existe no navegador, então é importada
 * dinamicamente dentro do efeito — um import estático quebraria o build do
 * Next, que avalia o módulo no servidor.
 */
function Leitor({ ativo, onLer }: { ativo: boolean; onLer: (texto: string) => void }) {
  const [estado, setEstado] = useState<EstadoCamera>("iniciando");
  // useRef e não useState: trocar o callback não deve reiniciar a câmera.
  const onLerRef = useRef(onLer);
  onLerRef.current = onLer;

  useEffect(() => {
    if (!ativo) return;

    let cancelado = false;
    // Só pode parar o que começou. Sem esta trava, o stop() é chamado numa
    // câmera que nunca abriu — e a html5-qrcode lança "Cannot stop, scanner is
    // not running or paused" de forma SÍNCRONA, ou seja, não é uma Promise
    // rejeitada: o .catch() não pega, o erro sobe e derruba a página inteira.
    let rodando = false;
    let instancia: Leitor5Qrcode | null = null;

    const parar = async () => {
      if (!instancia || !rodando) return;
      rodando = false;
      try {
        await instancia.stop();
        instancia.clear();
      } catch {
        /* já estava parada — nada a fazer */
      }
    };

    (async () => {
      try {
        const { Html5Qrcode } = await import("html5-qrcode");
        if (cancelado) return;

        // O navegador só mostra o diálogo de permissão quando start() é
        // chamado. Avisar antes evita a tela parecer travada enquanto a
        // pessoa não decide.
        setEstado("permissao");
        instancia = new Html5Qrcode(ID_LEITOR) as unknown as Leitor5Qrcode;

        await instancia.start(
          // facingMode environment = câmera traseira, que é a que aponta pro QR.
          { facingMode: "environment" },
          { fps: 10, qrbox: { width: 240, height: 240 } },
          (texto: string) => {
            // Para a câmera ANTES de avisar: sem isso a mesma leitura dispara
            // dezenas de vezes por segundo enquanto o QR estiver no quadro.
            void parar();
            onLerRef.current(texto);
          },
          () => {
            /* quadro sem QR — acontece o tempo todo, não é erro */
          },
        );
        rodando = true;
        if (!cancelado) setEstado("lendo");
      } catch (e) {
        if (cancelado) return;
        const msg = String(e);
        setEstado(
          msg.includes("NotAllowedError") || msg.includes("Permission")
            ? "negada"
            : "indisponivel",
        );
      }
    })();

    return () => {
      cancelado = true;
      void parar();
    };
  }, [ativo]);

  const semCamera = estado === "negada" || estado === "indisponivel";

  return (
    <div>
      {/* O quadro só existe enquanto há chance de imagem. Sem câmera, um
          retângulo preto de meia tela empurra a digitação — que é justamente
          a saída de quem está nesse estado — para fora da dobra. */}
      <div
        id={ID_LEITOR}
        className={`w-full overflow-hidden rounded-card border border-line bg-ink
          [&_video]:size-full [&_video]:object-cover
          ${semCamera ? "hidden" : "aspect-square"}`}
      />

      {estado === "iniciando" && (
        <p className="mt-2 text-center text-sm text-muted">Abrindo a câmera…</p>
      )}
      {estado === "permissao" && (
        <p className="mt-2 text-center text-sm text-muted">
          Autorize o uso da câmera para ler o QR.
        </p>
      )}
      {estado === "lendo" && (
        <p className="mt-2 text-center text-sm text-muted">
          Aponte para o QR do ingresso.
        </p>
      )}
      {estado === "negada" && (
        <div className="mt-2">
          <Alert tone="warn" title="Câmera bloqueada">
            Toque no cadeado ao lado do endereço, autorize a câmera e recarregue.
            Enquanto isso, use a digitação abaixo.
          </Alert>
        </div>
      )}
      {estado === "indisponivel" && (
        <div className="mt-2">
          <Alert tone="warn" title="Sem câmera disponível">
            Este aparelho ou navegador não expôs uma câmera. Use a digitação
            abaixo — o código de 8 caracteres está impresso no ingresso.
          </Alert>
        </div>
      )}
    </div>
  );
}

/** Retorno tátil e sonoro: na portaria ninguém fica olhando a tela. */
function avisar(resultado: GateResult) {
  try {
    navigator.vibrate?.(resultado === "VALID" ? 60 : [80, 60, 80]);
  } catch {
    /* sem suporte a vibração */
  }
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = resultado === "VALID" ? 880 : 320;
    gain.gain.value = 0.05;
    osc.start();
    osc.stop(ctx.currentTime + 0.14);
  } catch {
    /* áudio bloqueado até a primeira interação do usuário */
  }
}
