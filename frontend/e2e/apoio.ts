import { expect, type Page } from "@playwright/test";

/** Contas criadas pelo `manage.py seed`. Senha igual para todas. */
export const CONTAS = {
  organizador: "organizador@verzel.dev",
  cliente: "cliente1@verzel.dev",
  portaria: "portaria@verzel.dev",
} as const;

/**
 * Entra usando os atalhos de conta de demonstração da própria tela de login.
 *
 * Clicar no atalho em vez de digitar e-mail e senha é de propósito: se o
 * atalho quebrar, quem for avaliar o projeto trava logo no primeiro passo, e
 * este teste avisa.
 */
export async function entrar(page: Page, conta: keyof typeof CONTAS) {
  await page.goto("/entrar");
  await page.getByRole("button", { name: new RegExp(CONTAS[conta]) }).click();
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(page).toHaveURL(/\/(minha-conta|organizador|portaria)/);
}

export async function sair(page: Page) {
  // Precisa estar numa origem válida: em about:blank o acesso ao localStorage
  // levanta SecurityError.
  if (!page.url().startsWith("http")) await page.goto("/");
  await page.evaluate(() => localStorage.clear());
}

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/**
 * Abre o evento de PISTA com mais ingressos sobrando.
 *
 * A versão anterior clicava no primeiro "Ver ingressos" da vitrine e confiava
 * no nome da função para o resto. Funcionou até as próprias execuções da suíte
 * esgotarem esse evento: os testes passaram a falhar em "Aumentar quantidade"
 * está desabilitado, que parece bug de produto e é falta de estoque.
 *
 * Escolhe pela API em vez de pela tela porque a vitrine não mostra QUANTOS
 * restam — só "Esgotado". E um teste que compra 5 ingressos precisa de um
 * evento que tenha 5, não de um que tenha 1.
 */
export async function abrirEventoDisponivel(page: Page) {
  const r = await page.request.get(`${API}/api/events?kind=GA`);
  const eventos: { id: number; available: number }[] = (await r.json()).results;
  const alvo = eventos.sort((a, b) => b.available - a.available)[0];

  expect(alvo?.available, "o seed não tem evento de pista com estoque").toBeGreaterThan(8);

  await page.goto(`/eventos/${alvo.id}`);
  await expect(page.getByRole("button", { name: "Aumentar quantidade" })).toBeEnabled();
  return String(alvo.id);
}

/** Compra `quantidade` ingressos de pista e devolve o código do primeiro. */
export async function comprarPista(page: Page, quantidade = 1) {
  for (let i = 1; i < quantidade; i++) {
    await page.getByRole("button", { name: "Aumentar quantidade" }).click();
  }
  await page.getByRole("button", { name: /Reservar ingressos/ }).click();
  await expect(page.getByText("Confirme sua compra")).toBeVisible();
  await page.getByRole("button", { name: /^Pagar/ }).click();
  await expect(page.getByText("Compra confirmada")).toBeVisible();
}

/** Abre o primeiro ingresso da carteira e devolve o código para digitação. */
export async function pegarCodigoDoIngresso(page: Page) {
  await page.goto("/minha-conta");
  await page.getByRole("button", { name: /Ampliar/ }).first().click();
  const dialogo = page.getByRole("dialog");
  await expect(dialogo).toBeVisible();
  const codigo = await dialogo.locator(".font-mono").first().innerText();
  await page.keyboard.press("Escape");
  return codigo.trim();
}

/**
 * Acha a linha de um evento no painel, paginando se preciso.
 *
 * A API pagina de 12 em 12 e a tela acumula com "Mostrar mais eventos". Sem
 * isto, um teste que procura um evento específico falha por ele estar na
 * segunda página — e a falha parece um bug de produto, não de alcance.
 *
 * É um `expect.poll` e não um laço simples porque trocar de filtro dispara um
 * pedido novo: logo depois do clique a lista ainda é a ANTERIOR, e um laço que
 * olhasse uma vez só desistiria antes de o botão sequer aparecer.
 */
export async function encontrarLinha(page: Page, texto: string) {
  const linha = page.locator("article").filter({ hasText: texto });

  await expect
    .poll(
      async () => {
        if (await linha.count()) return true;
        const mais = page.getByRole("button", { name: "Mostrar mais eventos" });
        if (await mais.count()) await mais.click();
        return false;
      },
      { timeout: 20_000 },
    )
    .toBe(true);

  return linha.first();
}
