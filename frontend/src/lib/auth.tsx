"use client";

/**
 * Ponte entre a sessão (que vive em session.ts, fora do React) e a interface.
 *
 * O token fica em localStorage. É a escolha pragmática para uma SPA que fala
 * com uma API em OUTRO domínio (Vercel -> Render): cookie HttpOnly cross-site
 * exigiria SameSite=None + domínio compartilhado, o que este deploy não tem.
 * O custo é assumido e conhecido: localStorage é legível por JavaScript, então
 * um XSS levaria o token junto. A mitigação é o access token ser curto (60 min)
 * e a renovação acontecer sozinha, sem prender o usuário a uma sessão longa.
 *
 * E o mais importante: nada aqui AUTORIZA nada. Esconder um link é conveniência
 * de navegação — quem decide quem pode o quê é a permission class do Django.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { api } from "./api";
import {
  assinar,
  carregarSessao,
  gravarSessao,
  lerSessao,
  lerSessaoDoServidor,
  limparSessao,
  sessaoCarregada,
} from "./session";
import type { LoginResponse, Role, User } from "./types";

type AuthContextValue = {
  user: User | null;
  token: string | null;
  /** false enquanto o localStorage ainda não foi lido (evita piscar a UI). */
  ready: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (dados: {
    email: string;
    password: string;
    full_name: string;
    role: Role;
  }) => Promise<User>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  // useSyncExternalStore é a forma correta de observar estado que mora fora do
  // React. O terceiro argumento é o instantâneo do servidor — sempre null,
  // porque lá não existe localStorage. É o que mantém servidor e cliente
  // idênticos no primeiro render e não quebra a hidratação.
  const sessao = useSyncExternalStore(assinar, lerSessao, lerSessaoDoServidor);
  const carregada = useSyncExternalStore(assinar, sessaoCarregada, () => false);

  // Só depois de hidratar: localStorage não existe no servidor.
  useEffect(() => {
    carregarSessao();
  }, []);

  const login = useCallback(
    async (email: string, password: string) =>
      gravarSessao(
        await api<LoginResponse>("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        }),
      ),
    [],
  );

  const register = useCallback(
    async (dados: { email: string; password: string; full_name: string; role: Role }) => {
      await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(dados),
      });
      // Cadastrou, já entra: evita mandar o usuário para o login logo depois.
      return gravarSessao(
        await api<LoginResponse>("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: dados.email, password: dados.password }),
        }),
      );
    },
    [],
  );

  const value = useMemo(
    () => ({
      user: sessao?.user ?? null,
      token: sessao?.access ?? null,
      ready: carregada,
      login,
      register,
      logout: limparSessao,
    }),
    [sessao, carregada, login, register],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>");
  return ctx;
}

export const NOME_DO_PAPEL: Record<Role, string> = {
  ORGANIZER: "Organizador",
  CUSTOMER: "Cliente",
  GATE: "Portaria",
};
