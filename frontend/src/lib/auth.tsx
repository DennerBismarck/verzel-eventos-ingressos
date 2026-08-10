"use client";

/**
 * Sessão do usuário no navegador.
 *
 * O token fica em localStorage. É a escolha pragmática para uma SPA que fala
 * com uma API em OUTRO domínio (Vercel -> Render): cookie HttpOnly cross-site
 * exigiria SameSite=None + domínio compartilhado, o que este deploy não tem.
 * O custo é assumido e conhecido: localStorage é legível por JavaScript, então
 * um XSS levaria o token junto. A mitigação é o access token ser curto (60 min).
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
  useState,
  type ReactNode,
} from "react";

import { api } from "./api";
import type { LoginResponse, Role, User } from "./types";

const CHAVE_TOKEN = "ingressos.access";
const CHAVE_USER = "ingressos.user";

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
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  // localStorage não existe no servidor: só depois da hidratação.
  useEffect(() => {
    try {
      const t = localStorage.getItem(CHAVE_TOKEN);
      const u = localStorage.getItem(CHAVE_USER);
      if (t && u) {
        setToken(t);
        setUser(JSON.parse(u) as User);
      }
    } catch {
      // localStorage bloqueado (modo privado, permissões): segue deslogado.
    }
    setReady(true);
  }, []);

  const guardar = useCallback((resposta: LoginResponse) => {
    setToken(resposta.access);
    setUser(resposta.user);
    try {
      localStorage.setItem(CHAVE_TOKEN, resposta.access);
      localStorage.setItem(CHAVE_USER, JSON.stringify(resposta.user));
    } catch {
      /* sessão só em memória */
    }
    return resposta.user;
  }, []);

  const login = useCallback(
    async (email: string, password: string) =>
      guardar(
        await api<LoginResponse>("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        }),
      ),
    [guardar],
  );

  const register = useCallback(
    async (dados: { email: string; password: string; full_name: string; role: Role }) => {
      await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(dados),
      });
      // Cadastrou, já entra: evita mandar o usuário para o login logo depois.
      return guardar(
        await api<LoginResponse>("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: dados.email, password: dados.password }),
        }),
      );
    },
    [guardar],
  );

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    try {
      localStorage.removeItem(CHAVE_TOKEN);
      localStorage.removeItem(CHAVE_USER);
    } catch {
      /* nada a limpar */
    }
  }, []);

  const value = useMemo(
    () => ({ user, token, ready, login, register, logout }),
    [user, token, ready, login, register, logout],
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
