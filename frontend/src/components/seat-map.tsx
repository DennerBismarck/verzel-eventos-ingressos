"use client";

/**
 * Mapa de assentos.
 *
 * Desenha o que o backend devolve, agrupado por seção e fila. Não decide nada
 * sobre disponibilidade: o `status` vem do servidor, e a reserva é conferida
 * de novo lá (com lock na linha do assento) no momento de reservar. Um mapa
 * carregado há um minuto já pode estar desatualizado — por isso a tela precisa
 * lidar bem com "esse lugar acabou de ser vendido", e não tentar impedir.
 *
 * Cada poltrona é um <button> de verdade: navegável por Tab, acionável por
 * Enter e anunciada pelo leitor de tela com fila, número, preço e situação.
 */

import { useMemo } from "react";

import { money } from "@/lib/format";
import type { Seat } from "@/lib/types";

type Props = {
  seats: Seat[];
  selecionados: Set<number>;
  onAlternar: (seat: Seat) => void;
  limite: number;
};

export function SeatMap({ seats, selecionados, onAlternar, limite }: Props) {
  // Agrupa por seção e depois por fila, preservando a ordem que o backend
  // mandou (o Meta.ordering do Seat já garante seção → fila → número).
  const secoes = useMemo(() => {
    const mapa = new Map<string, Map<string, Seat[]>>();
    for (const s of seats) {
      if (!mapa.has(s.section)) mapa.set(s.section, new Map());
      const filas = mapa.get(s.section)!;
      if (!filas.has(s.row)) filas.set(s.row, []);
      filas.get(s.row)!.push(s);
    }
    return [...mapa.entries()].map(([nome, filas]) => ({
      nome,
      preco: filas.values().next().value?.[0]?.price ?? "0",
      filas: [...filas.entries()].map(([letra, lugares]) => ({ letra, lugares })),
    }));
  }, [seats]);

  const cheio = selecionados.size >= limite;

  return (
    <div>
      {/* Referência espacial: sem isto o usuário não sabe qual ponta é a frente. */}
      <div className="mb-6 rounded border border-line bg-canvas py-2 text-center text-[11px] font-semibold uppercase tracking-[0.2em] text-muted">
        Palco
      </div>

      <div className="space-y-6 overflow-x-auto pb-2">
        {secoes.map((secao) => (
          <section key={secao.nome}>
            <div className="mb-2 flex items-baseline justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">{secao.nome}</h3>
              <span className="text-xs text-muted">{money(secao.preco)}</span>
            </div>

            <div className="space-y-1.5">
              {secao.filas.map((fila) => (
                <div key={fila.letra} className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="w-5 shrink-0 text-right text-[11px] font-medium text-muted"
                  >
                    {fila.letra}
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {fila.lugares.map((lugar) => {
                      const vendido = lugar.status === "SOLD";
                      const escolhido = selecionados.has(lugar.id);
                      // Bloqueia novos cliques ao atingir o limite, mas nunca
                      // impede DESmarcar o que já está escolhido.
                      const bloqueado = vendido || (cheio && !escolhido);

                      return (
                        <button
                          key={lugar.id}
                          type="button"
                          disabled={bloqueado}
                          aria-pressed={escolhido}
                          aria-label={
                            `Fila ${lugar.row}, lugar ${lugar.number}, ` +
                            `${money(lugar.price)}, ` +
                            (vendido ? "indisponível" : escolhido ? "selecionado" : "livre")
                          }
                          onClick={() => onAlternar(lugar)}
                          className={`size-7 rounded-t-md rounded-b-sm border text-[10px] font-semibold
                            transition-colors
                            ${
                              vendido
                                ? "cursor-not-allowed border-line bg-line text-muted/60"
                                : escolhido
                                  ? "border-accent bg-accent text-white"
                                  : bloqueado
                                    ? "cursor-not-allowed border-line bg-white text-muted/50"
                                    : "border-line-strong bg-white text-body hover:border-accent hover:bg-accent/10"
                            }`}
                        >
                          {lugar.number}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>

      <Legenda />
    </div>
  );
}

function Legenda() {
  const itens = [
    { classe: "border-line-strong bg-white", texto: "Livre" },
    { classe: "border-accent bg-accent", texto: "Selecionado" },
    { classe: "border-line bg-line", texto: "Vendido" },
  ];
  return (
    <ul className="mt-5 flex flex-wrap gap-4 border-t border-line pt-4 text-xs text-muted">
      {itens.map((i) => (
        <li key={i.texto} className="flex items-center gap-1.5">
          <span aria-hidden="true" className={`size-3.5 rounded-t rounded-b-sm border ${i.classe}`} />
          {i.texto}
        </li>
      ))}
    </ul>
  );
}
