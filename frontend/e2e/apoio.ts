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

/** Abre o primeiro evento de pista com ingresso disponível. */
export async function abrirEventoDisponivel(page: Page) {
  await page.goto("/");
  await page.getByRole("link", { name: "Ver ingressos" }).click();
  await expect(page).toHaveURL(/\/eventos\/\d+/);
  return page.url().split("/").pop()!;
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
