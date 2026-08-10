/**
 * Sessão do usuário, FORA do React.
 *
 * Por que fora: quem precisa do access token não é só a interface — é a função
 * `api()`, que roda em qualquer lugar e precisa poder TROCAR o token no meio de
 * uma requisição (renovação automática). Se a única fonte de verdade fosse um
 * estado de componente, todo chamador que já tivesse copiado o token numa
 * variável seguiria usando o valor velho depois da renovação.
 *
 * O React se conecta aqui por useSyncExternalStore, que é exatamente a
 * ferramenta para "estado que vive fora e a UI observa".
 */

import type { LoginResponse, User } from "./types";

const CHAVE = "ingressos.sessao";

export type Sessao = { access: string; refresh: string; user: User } | null;

// Referência estável: useSyncExternalStore compara por identidade e entraria em
// laço infinito se getSnapshot devolvesse um objeto novo a cada chamada.
let sessao: Sessao = null;
let carregada = false;

const ouvintes = new Set<() => void>();

function avisar() {
  for (const fn of ouvintes) fn();
}

export function assinar(fn: () => void) {
  ouvintes.add(fn);
  return () => ouvintes.delete(fn);
}

export function lerSessao(): Sessao {
  return sessao;
}

/**
 * Instantâneo usado na renderização do servidor E na hidratação.
 *
 * Sempre null: no servidor não existe localStorage. Devolver aqui algo
 * diferente do primeiro render do cliente quebraria a hidratação — foi
 * exatamente o tipo de erro que derrubou duas telas antes.
 */
export function lerSessaoDoServidor(): Sessao {
  return null;
}

export function sessaoCarregada() {
  return carregada;
}

export function gravarSessao(dados: LoginResponse) {
  sessao = { access: dados.access, refresh: dados.refresh, user: dados.user };
  try {
    localStorage.setItem(CHAVE, JSON.stringify(sessao));
  } catch {
    // localStorage bloqueado (modo privado): a sessão vale só em memória.
  }
  avisar();
  return sessao.user;
}

export function limparSessao() {
  sessao = null;
  try {
    localStorage.removeItem(CHAVE);
  } catch {
    /* nada a limpar */
  }
  avisar();
}

/** Chamado uma vez, depois da hidratação. */
export function carregarSessao() {
  if (carregada) return;
  carregada = true;
  try {
    const cru = localStorage.getItem(CHAVE);
    if (cru) {
      const dados = JSON.parse(cru) as Sessao;
      // Sessão gravada por uma versão anterior do app pode não ter refresh.
      if (dados?.access && dados?.refresh && dados?.user) sessao = dados;
    }
  } catch {
    /* JSON corrompido ou storage bloqueado: entra deslogado */
  }
  avisar();
}

/** Troca só o access, preservando refresh e usuário. */
export function trocarAccess(access: string) {
  if (!sessao) return;
  sessao = { ...sessao, access };
  try {
    localStorage.setItem(CHAVE, JSON.stringify(sessao));
  } catch {
    /* segue em memória */
  }
  avisar();
}
