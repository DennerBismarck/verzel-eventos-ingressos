import { expect, test } from "@playwright/test";

import { abrirEventoDisponivel, comprarPista, entrar, sair } from "./apoio";

test.describe("organizador", () => {
  test("painel lista os próprios eventos, inclusive rascunho", async ({ page }) => {
    await entrar(page, "organizador");
    await expect(page.getByRole("heading", { name: "Meus eventos" })).toBeVisible();
    await expect(page.getByText("Rascunho").first()).toBeVisible();
    await expect(page.getByText("Publicado").first()).toBeVisible();
    // A barra de ocupação é o que dá a leitura rápida de como o evento vai.
    await expect(page.getByRole("progressbar").first()).toBeVisible();
  });

  test("publicar e despublicar muda a vitrine", async ({ page }) => {
    await entrar(page, "organizador");
    const rascunho = page.locator("article").filter({ hasText: "Rascunho" }).first();
    const titulo = await rascunho.getByRole("heading").innerText();

    await rascunho.getByRole("button", { name: "Publicar" }).click();
    await expect(
      page.locator("article").filter({ hasText: titulo }).getByText("Publicado"),
    ).toBeVisible();

    await sair(page);
    await page.goto(`/?q=${encodeURIComponent(titulo.split(" ")[0])}`);
    await expect(page.locator("article").first()).toBeVisible();

    // Devolve ao estado do seed, senão o teste da vitrine (que espera o
    // rascunho escondido) passa a falhar dependendo da ordem de execução.
    await entrar(page, "organizador");
    await page
      .locator("article")
      .filter({ hasText: titulo })
      .getByRole("button", { name: "Despublicar" })
      .click();
    await expect(
      page.locator("article").filter({ hasText: titulo }).getByText("Rascunho"),
    ).toBeVisible();
  });

  test("busca no catálogo externo e cria evento", async ({ page }) => {
    await entrar(page, "organizador");
    await page.goto("/organizador/novo");
    await page.locator("#termo").fill("interestelar");
    await page.locator("#conteudo").getByRole("button", { name: "Buscar" }).click();

    const primeiro = page.locator("li button").first();
    // Sem chave de API configurada o catálogo responde 503 explicando — e o
    // teste para aqui em vez de falhar por um motivo enganoso.
    const semChave = page.getByText(/sem chave de API/);
    await expect(primeiro.or(semChave)).toBeVisible();
    test.skip(await semChave.isVisible(), "catálogo sem chave neste ambiente");

    await primeiro.click();
    await page.getByLabel("Local").fill("Cine Teste, São Paulo");
    await page.getByLabel("Data e hora").fill("2027-03-15T20:00");
    await page.getByLabel(/Preço/).fill("45.00");
    await page.getByLabel(/Capacidade/).fill("70");
    await page.getByRole("button", { name: /Criar e publicar/ }).click();

    await expect(page).toHaveURL(/\/eventos\/\d+/);
    await expect(page.getByText("Cine Teste, São Paulo")).toBeVisible();
    await expect(page.getByText("R$ 45,00").first()).toBeVisible();
  });

  test("evento com data no passado é recusado no campo certo", async ({ page }) => {
    await entrar(page, "organizador");
    await page.goto("/organizador/novo");
    await page.locator("#conteudo").getByRole("button", { name: "Buscar" }).click();

    const primeiro = page.locator("li button").first();
    const semChave = page.getByText(/sem chave de API/);
    await expect(primeiro.or(semChave)).toBeVisible();
    test.skip(await semChave.isVisible(), "catálogo sem chave neste ambiente");

    await primeiro.click();
    await page.getByLabel("Local").fill("X");
    await page.getByLabel("Data e hora").fill("2020-01-01T20:00");
    await page.getByLabel(/Preço/).fill("10");
    await page.getByLabel(/Capacidade/).fill("10");
    await page.getByRole("button", { name: /Criar e publicar/ }).click();

    await expect(page.getByText("O evento precisa começar no futuro.")).toBeVisible();
  });

  test("painel de vendas mostra receita e comprador", async ({ page }) => {
    await entrar(page, "cliente");
    const id = await abrirEventoDisponivel(page);
    await comprarPista(page, 1);

    await sair(page);
    await entrar(page, "organizador");
    await page.goto(`/organizador/vendas/${id}`);

    await expect(page.getByText("RECEITA")).toBeVisible();
    await expect(page.getByText("JÁ ENTRARAM")).toBeVisible();
    await expect(page.getByRole("table")).toBeVisible();
    await expect(page.getByText("cliente1@verzel.dev").first()).toBeVisible();
  });

  test("vendas de evento que não é meu devolve mensagem, não tela quebrada", async ({
    page,
  }) => {
    await entrar(page, "organizador");
    await page.goto("/organizador/vendas/999999");
    await expect(page.getByText("Este evento não existe ou não é seu.")).toBeVisible();
  });
});
