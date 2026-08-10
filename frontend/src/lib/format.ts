/** Formatação pt-BR. Um lugar só, para não divergir entre telas. */

const BRL = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

/** A API manda Decimal como string ("42.00") de propósito, para não perder
 *  precisão no JSON. A conversão para número acontece só na exibição. */
export function money(value: string | number): string {
  return BRL.format(typeof value === "string" ? Number(value) : value);
}

const DIA_MES = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" });
const COMPLETA = new Intl.DateTimeFormat("pt-BR", {
  weekday: "long",
  day: "2-digit",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const CURTA = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function dateParts(iso: string) {
  const d = new Date(iso);
  const [dia, mes] = DIA_MES.format(d).split(" de ");
  return {
    dia,
    // "set." -> "SET"
    mes: (mes ?? "").replace(".", "").toUpperCase(),
    hora: d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
  };
}

export function fullDate(iso: string): string {
  return COMPLETA.format(new Date(iso));
}

export function shortDate(iso: string): string {
  return CURTA.format(new Date(iso));
}

/**
 * Preço para exibição: zero vira "Gratuito", não "R$ 0,00".
 *
 * "R$ 0,00" num cartaz de evento parece defeito de sistema, não cortesia — e
 * foi literalmente o sintoma do bug do preço em lugar marcado.
 */
export function preco(valor: string | number): string {
  const n = typeof valor === "string" ? Number(valor) : valor;
  return n > 0 ? money(n) : "Gratuito";
}
