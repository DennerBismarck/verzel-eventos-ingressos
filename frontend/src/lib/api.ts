/**
 * Cliente HTTP da API Django.
 *
 * Um único lugar que sabe a URL base e como montar o header de auth.
 * Assim, quando o token mudar de lugar (hoje localStorage, talvez cookie
 * depois), muda só aqui.
 */

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

type Options = RequestInit & { token?: string | null };

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const { token, headers, ...rest } = options;

  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      // Só manda o header se houver token — endpoints públicos não precisam.
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  // 204 não tem corpo; tentar dar .json() nele explode.
  const body = res.status === 204 ? null : await res.json().catch(() => null);

  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

export type HealthResponse = { status: string; service: string };
