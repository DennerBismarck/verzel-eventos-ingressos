import Link from "next/link";

import { dateParts, preco } from "@/lib/format";
import type { PublicEvent } from "@/lib/types";

/**
 * Card da vitrine.
 *
 * Proporção 2:3 no pôster porque é o formato que o TMDb devolve — deixar o
 * navegador escolher causaria "layout shift" quando a imagem chegasse.
 * A Ticketmaster manda 16:9; o object-cover recorta sem distorcer.
 */
export function EventCard({ event }: { event: PublicEvent }) {
  const { dia, mes } = dateParts(event.starts_at);
  const esgotado = event.available <= 0;

  return (
    <article className="group relative flex flex-col overflow-hidden rounded-card border border-line bg-white">
      <div className="relative aspect-[2/3] overflow-hidden bg-canvas">
        {event.image_url ? (
          // <img> e não next/image: as imagens vêm de hosts externos (TMDb e
          // Ticketmaster) e o otimizador da Vercel cobraria por transformação
          // sem ganho real — os pôsteres já vêm no tamanho certo.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={event.image_url}
            alt=""
            loading="lazy"
            // object-top: cartaz recortado pelo centro corta rosto. O topo é
            // onde a informação costuma estar.
            className="size-full object-cover object-top transition-transform
              duration-300 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="grid size-full place-items-center bg-brand/5 px-4">
            <span className="text-center text-sm font-semibold text-brand/50">
              {event.title}
            </span>
          </div>
        )}

        {/* Véu escuro no rodapé do pôster.
            O bloco de data ficava sobre a arte crua e, em cartaz claro ou com
            texto na base, um encostava no outro. O gradiente separa os dois
            sem esconder a imagem. */}
        <div
          aria-hidden="true"
          className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t
            from-ink/80 via-ink/35 to-transparent"
        />

        {/* Bloco de data sobre o pôster — padrão Eventim/Sympla. */}
        <div
          className="absolute bottom-2 left-2 rounded bg-ink/90 px-2 py-1 text-center
            leading-none text-white"
        >
          <span className="block text-base font-bold">{dia}</span>
          <span className="block text-[10px] font-semibold tracking-wider text-white/80">
            {mes}
          </span>
        </div>

        {esgotado && (
          <div className="absolute inset-0 grid place-items-center bg-ink/65">
            <span className="rounded border border-white/30 px-3 py-1 text-sm font-bold uppercase tracking-wide text-white">
              Esgotado
            </span>
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-1 p-3">
        <h3 className="text-sm font-semibold leading-snug text-ink">
          {/* O link cobre o card inteiro, mas o texto do link é só o título —
              é isso que o leitor de tela anuncia ao navegar por links. */}
          <Link href={`/eventos/${event.id}`} className="before:absolute before:inset-0">
            {event.title}
          </Link>
        </h3>

        <p className="line-clamp-1 text-xs text-muted">{event.venue}</p>

        <p className="mt-auto pt-2 text-[13px] font-semibold text-ink">
          {esgotado ? (
            <span className="text-muted">Indisponível</span>
          ) : (
            <>
              <span className="font-normal text-muted">a partir de </span>
              {preco(event.price_from)}
            </>
          )}
        </p>
      </div>
    </article>
  );
}

export function EventCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-card border border-line bg-white">
      <div className="aspect-[2/3] animate-pulse bg-line" />
      <div className="space-y-2 p-3">
        <div className="h-4 w-4/5 animate-pulse rounded bg-line" />
        <div className="h-3 w-3/5 animate-pulse rounded bg-line" />
        <div className="h-4 w-2/5 animate-pulse rounded bg-line" />
      </div>
    </div>
  );
}
