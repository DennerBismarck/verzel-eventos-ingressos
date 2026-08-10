"use client";

/**
 * Tela da portaria.
 *
 * Feita para ser usada em pé, num celular, com pressa e má iluminação:
 * resultado em bloco grande e colorido, som e vibração, e sempre a opção de
 * digitar o código quando a câmera não colabora (exigência do enunciado).
 *
 * A tela NÃO decide nada. Ela manda o conteúdo lido e o evento selecionado
 * para o backend, que confere a assinatura HMAC, trava a linha do ingresso e
 * responde uma das quatro situações.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Alert, Button, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { shortDate } from "@/lib/format";
import type { GateEvent, GateResponse, GateResult } from "@/lib/types";

const ID_LEITOR = "leitor-qr";

const APARENCIA: Record<
  GateResult,
  { fundo: string; titulo: string; icone: "ok" | "x" | "alerta" }
> = {
  VALID: { fundo: "bg-ok", titulo: "Entrada liberada", icone: "ok" },
  ALREADY_USED: { fundo: "bg-warn", titulo: "Já utilizado", icone: "alerta" },
  WRONG_EVENT: { fundo: "bg-brand", titulo: "Evento errado", icone: "alerta" },
  INVALID: { fundo: "bg-danger", titulo: "Ingresso inválido", icone: "x" },
};

export default function PortariaPage() {
  const { user, token, ready } = useAuth();
  const [eventos, setEventos] = useState<GateEvent[] | null>(null);
  const [eventoId, setEventoId] = useState<number | null>(null);
  const [resultado, setResultado] = useState<GateResponse | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [manual, setManual] = useState("");

  useEffect(() => {
    if (!token) return;
    api<GateEvent[]>("/api/gate/events", { token })
      .then((lista) => {
        setEventos(lista);
        if (lista.length === 1) setEventoId(lista[0].id);
      })
      .catch(() => setErro("Não conseguimos carregar a lista de eventos."));
  }, [token]);

  const validar = useCallback(
    async (payload: string) => {
      if (!eventoId || !payload.trim()) return;
      setEnviando(true);
      setErro(null);
      try {
        const r = await api<GateResponse>("/api/gate/validate", {
          method: "POST",
          token,
          body: JSON.stringify({ payload: payload.trim(), event: eventoId }),
        });
        setResultado(r);
        avisar(r.result);
      } catch {
        setErro("Falha ao falar com o servidor. Tente novamente.");
      } finally {
        setEnviando(false);
        setManual("");
      }
    },
    [eventoId, token],
  );

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
    <div className="mx-auto max-w-md px-4 py-6">
      <h1 className="text-xl font-bold text-ink">Portaria</h1>
      <p className="mt-1 text-sm text-muted">
        Selecione o evento e aponte a câmera para o QR do ingresso.
      </p>

      <div className="mt-5">
        <label htmlFor="evento" className="mb-1.5 block text-sm font-medium text-ink">
          Evento nesta entrada
        </label>
        {!eventos ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <select
            id="evento"
            value={eventoId ?? ""}
            onChange={(e) => {
              setEventoId(e.target.value ? Number(e.target.value) : null);
              setResultado(null);
            }}
            className="h-10 w-full rounded border border-line-strong bg-white px-3 text-sm text-ink"
          >
            <option value="">Selecione…</option>
            {eventos.map((ev) => (
              <option key={ev.id} value={ev.id}>
                {ev.title} — {shortDate(ev.starts_at)}
              </option>
            ))}
          </select>
        )}
        <p className="mt-1.5 text-xs text-muted">
          É o que permite responder <strong>evento errado</strong> quando o ingresso é de
          outra sessão.
        </p>
      </div>

      {erro && (
        <div className="mt-4">
          <Alert tone="danger">{erro}</Alert>
        </div>
      )}

      {!eventoId && (
        <div className="mt-6 rounded-card border border-dashed border-line-strong bg-white px-6 py-10 text-center">
          <p className="font-semibold text-ink">Escolha o evento para começar</p>
          <p className="mx-auto mt-1 max-w-xs text-sm text-muted">
            A câmera e a digitação manual aparecem assim que a sessão desta entrada
            estiver selecionada.
          </p>
        </div>
      )}

      {eventoId && (
        <>
          <div className="mt-6">
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
              Ou digite o código
            </label>
            <div className="flex gap-2">
              <input
                id="manual"
                value={manual}
                onChange={(e) => setManual(e.target.value)}
                placeholder="0ef4ea9a-8d22-4e61-909c-…"
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                className="h-11 min-w-0 flex-1 rounded border border-line-strong bg-white
                  px-3 font-mono text-sm text-ink placeholder:text-muted"
              />
              <Button type="submit" size="lg" loading={enviando} disabled={!manual.trim()}>
                Validar
              </Button>
            </div>
            <p className="mt-1.5 text-xs text-muted">
              O código impresso no ingresso, para quando a câmera não lê.
            </p>
          </form>
        </>
      )}

      {resultado && (
        <PainelResultado resultado={resultado} onProximo={() => setResultado(null)} />
      )}
    </div>
  );
}

function PainelResultado({
  resultado,
  onProximo,
}: {
  resultado: GateResponse;
  onProximo: () => void;
}) {
  const { fundo, titulo, icone } = APARENCIA[resultado.result];

  return (
    // Ocupa a tela inteira: quem está na porta precisa ler de relance, sem
    // procurar onde apareceu a resposta.
    <div
      role="alert"
      className={`fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 p-6
        text-center text-white ${fundo}`}
    >
      <Icone tipo={icone} />
      {/* text-white explícito: a regra global `h2 { color: ink }` vence a cor
          herdada do contêiner e deixaria o título ilegível no fundo colorido. */}
      <h2 className="text-3xl font-bold text-white">{titulo}</h2>
      <p className="max-w-xs text-white/90">{resultado.detail}</p>

      {resultado.ticket && (
        <dl className="mt-2 w-full max-w-xs space-y-1 rounded border border-white/25 bg-white/10 p-4 text-left text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-white/70">Titular</dt>
            <dd className="font-semibold">{resultado.ticket.customer_name}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-white/70">Evento</dt>
            <dd className="truncate font-semibold">{resultado.ticket.event_title}</dd>
          </div>
          {resultado.ticket.seat_label && (
            <div className="flex justify-between gap-3">
              <dt className="text-white/70">Lugar</dt>
              <dd className="font-semibold">{resultado.ticket.seat_label}</dd>
            </div>
          )}
        </dl>
      )}

      <button
        onClick={onProximo}
        autoFocus
        className="mt-4 h-14 w-full max-w-xs rounded bg-white text-lg font-bold text-ink"
      >
        Próximo ingresso
      </button>
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
    <svg viewBox="0 0 24 24" className="size-16 fill-white" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

/**
 * Leitor de câmera.
 *
 * A biblioteca mexe direto no DOM e só existe no navegador, então é importada
 * dinamicamente dentro do efeito — um import estático quebraria o build do
 * Next, que avalia o módulo no servidor.
 */
type Leitor5Qrcode = {
  start: (...a: unknown[]) => Promise<void>;
  stop: () => Promise<void>;
  clear: () => void;
};

function Leitor({ ativo, onLer }: { ativo: boolean; onLer: (texto: string) => void }) {
  const [estado, setEstado] = useState<"iniciando" | "lendo" | "negado" | "indisponivel">(
    "iniciando",
  );
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
            ? "negado"
            : "indisponivel",
        );
      }
    })();

    return () => {
      cancelado = true;
      void parar();
    };
  }, [ativo]);

  return (
    <div>
      <div
        id={ID_LEITOR}
        className="aspect-square w-full overflow-hidden rounded-card border
          border-line bg-ink [&_video]:size-full [&_video]:object-cover"
      />
      {estado === "iniciando" && (
        <p className="mt-2 text-center text-sm text-muted">Abrindo a câmera…</p>
      )}
      {estado === "lendo" && (
        <p className="mt-2 text-center text-sm text-muted">
          Aponte para o QR do ingresso.
        </p>
      )}
      {estado === "negado" && (
        <div className="mt-2">
          <Alert tone="warn" title="Câmera bloqueada">
            Autorize o acesso à câmera nas permissões do navegador, ou digite o código
            abaixo.
          </Alert>
        </div>
      )}
      {estado === "indisponivel" && (
        <div className="mt-2">
          <Alert tone="warn" title="Câmera indisponível">
            Este dispositivo ou navegador não permitiu o uso da câmera. Use a digitação
            manual.
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
