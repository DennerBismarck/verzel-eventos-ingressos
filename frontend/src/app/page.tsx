"use client";

/**
 * Página "hello world" do Dia 0.
 *
 * Propósito único: provar que o pipeline inteiro está de pé —
 * Vercel serve o front, o front alcança a API Django, a API responde.
 * Se isto funciona em produção, o deploy está destravado e o resto do
 * projeto é só código.
 *
 * É Client Component de propósito: a chamada acontece no browser, depois
 * do carregamento. Se fosse feita no servidor durante o build, a API fora
 * do ar quebraria o deploy — e a gente quer justamente ver o estado real.
 *
 * Esta página é descartável: no Dia 1 vira a listagem de eventos.
 */

import { useEffect, useState } from "react";

import { API_URL, api, type HealthResponse } from "@/lib/api";

type Status =
  | { kind: "checking" }
  | { kind: "ok"; service: string }
  | { kind: "error"; message: string };

export default function Home() {
  const [status, setStatus] = useState<Status>({ kind: "checking" });

  useEffect(() => {
    api<HealthResponse>("/api/health")
      .then((data) => setStatus({ kind: "ok", service: data.service }))
      .catch((err: Error) =>
        setStatus({ kind: "error", message: err.message }),
      );
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-8 px-6 py-16">
      <header className="space-y-3">
        <p className="text-sm font-medium tracking-widest text-neutral-500 uppercase">
          Desafio Elite Dev · Verzel
        </p>
        <h1 className="text-4xl font-bold tracking-tight text-balance">
          Plataforma de Eventos e Ingressos
        </h1>
        <p className="text-neutral-600 dark:text-neutral-400">
          Organizador publica eventos de um catálogo externo, cliente compra
          ingresso com QR, portaria valida na entrada.
        </p>
      </header>

      <section className="rounded-xl border border-neutral-200 p-5 dark:border-neutral-800">
        <h2 className="mb-3 text-sm font-semibold">Conexão com a API</h2>

        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className={`size-2.5 rounded-full ${
              status.kind === "ok"
                ? "bg-emerald-500"
                : status.kind === "error"
                  ? "bg-red-500"
                  : "animate-pulse bg-amber-400"
            }`}
          />
          {/* role="status" faz o leitor de tela anunciar a mudança sem roubar o foco. */}
          <p role="status" className="text-sm">
            {status.kind === "checking" && "Verificando…"}
            {status.kind === "ok" && (
              <>
                Conectado a <strong>{status.service}</strong>
              </>
            )}
            {status.kind === "error" && (
              <>
                Sem resposta da API{" "}
                <span className="text-neutral-500">({status.message})</span>
              </>
            )}
          </p>
        </div>

        <p className="mt-3 font-mono text-xs break-all text-neutral-500">
          {API_URL}/api/health
        </p>
      </section>

      <footer className="text-sm text-neutral-500">
        Dia 0 — scaffold, autenticação com 3 papéis e deploy destravado.
      </footer>
    </main>
  );
}
