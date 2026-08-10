/**
 * Cliente HTTP da API Django.
 *
 * Um único lugar que sabe a URL base, monta o header de auth e — o ponto
 * central deste arquivo — RENOVA o access token quando ele expira, sem que a
 * tela precise saber disso.
 */

import { lerSessao, limparSessao, trocarAccess } from "./session";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/** Erro com o status HTTP e o corpo já parseado, pra UI decidir o que mostrar. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public data: unknown,
  ) {
    super(`API ${status}`);
    this.name = "ApiError";
  }
}

type Options = RequestInit & {
  /**
   * Sobrescreve o token da sessão. Só serve para caso excepcional; o normal é
   * omitir e deixar a sessão responder — é isso que permite a renovação
   * transparente.
   */
  token?: string | null;
  /** Uso interno: impede que a tentativa após renovar tente renovar de novo. */
  _jaRenovou?: boolean;
};

/**
 * Renovação em voo, compartilhada.
 *
 * Se três requisições levarem 401 ao mesmo tempo, todas esperam a MESMA
 * renovação. Sem isto seriam três POSTs de refresh simultâneos, e as duas
 * últimas usariam um refresh já consumido.
 */
let renovacaoEmVoo: Promise<string | null> | null = null;

async function renovarAccess(): Promise<string | null> {
  if (renovacaoEmVoo) return renovacaoEmVoo;

  const sessao = lerSessao();
  if (!sessao?.refresh) return null;

  renovacaoEmVoo = (async () => {
    try {
      const res = await fetch(`${API_URL}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: sessao.refresh }),
      });
      if (!res.ok) return null;
      const { access } = (await res.json()) as { access: string };
      trocarAccess(access);
      return access;
    } catch {
      // Rede caiu no meio da renovação: não é motivo para deslogar.
      return null;
    } finally {
      renovacaoEmVoo = null;
    }
  })();

  return renovacaoEmVoo;
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const { token, headers, _jaRenovou, ...rest } = options;
  const access = token !== undefined ? token : lerSessao()?.access;

  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      // Só manda o header se houver token — endpoints públicos não precisam.
      ...(access ? { Authorization: `Bearer ${access}` } : {}),
      ...headers,
    },
  });

  // 401 com token significa access expirado: renova uma vez e repete a
  // chamada. Só uma vez — se o refresh também não resolver, insistir viraria
  // laço infinito.
  if (res.status === 401 && access && !_jaRenovou) {
    const novo = await renovarAccess();
    if (novo) {
      return api<T>(path, { ...options, token: undefined, _jaRenovou: true });
    }
    // Refresh expirou também: a sessão acabou de verdade.
    limparSessao();
  }

  // 204 não tem corpo; tentar dar .json() nele explode.
  const body = res.status === 204 ? null : await res.json().catch(() => null);

  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

export type HealthResponse = { status: string; service: string };
