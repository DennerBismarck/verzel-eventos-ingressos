import { expect, test } from "@playwright/test";

test.describe("vitrine", () => {
  test("lista eventos publicados com cartaz e preço", async ({ page }) => {
    await page.goto("/");
    const cards = page.locator("article");
    await expect(cards.first()).toBeVisible();
    // toHaveCount reexecuta até bater; count() lê uma vez e pode ler antes de
    // a API responder — foi assim que este teste viu 0 na primeira versão.
    await expect(cards).not.toHaveCount(0);
    expect(await cards.count()).toBeGreaterThan(3);
    // Cartaz ausente deixaria a vitrine com cara de protótipo.
    await expect(cards.first().locator("img")).toBeVisible();
    await expect(page.getByText(/a partir de/).first()).toBeVisible();
  });

  test("busca filtra por título", async ({ page }) => {
    await page.goto("/");
    await page.getByPlaceholder(/Busque por evento/).first().fill("moana");
    await page.getByRole("search").getByRole("button", { name: "Buscar" }).click();
    await expect(page).toHaveURL(/\?q=moana/);
    await expect(page.getByRole("heading", { name: /Resultados para/ })).toBeVisible();
    await expect(page.locator("article")).toHaveCount(1);
  });

  test("busca sem resultado explica em vez de mostrar tela vazia", async ({ page }) => {
    await page.goto("/?q=zzzzzznaoexiste");
    await expect(page.getByText("Nenhum evento encontrado")).toBeVisible();
  });

  test("evento esgotado aparece marcado e sem opção de compra", async ({ page }) => {
    await page.goto("/?q=Minions");
    const card = page.locator("article").first();
    await expect(card.getByText("Esgotado")).toBeVisible();

    await card.getByRole("link").click();
    // O título do aviso é um <p>, não um heading — getByRole("heading") nunca
    // casaria, e o teste falharia dizendo que o app está errado.
    await expect(page.locator("aside").getByText("Esgotado")).toBeVisible();
    await expect(page.getByRole("button", { name: /Reservar/ })).toHaveCount(0);
  });

  test("rascunho não aparece para o público", async ({ page }) => {
    await page.goto("/?q=Zona Zero");
    await expect(page.getByText("Nenhum evento encontrado")).toBeVisible();
  });

  test("filtro separa pista de lugar marcado", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Lugar marcado" }).click();
    await expect(page.locator("article")).toHaveCount(1);

    await page.getByRole("button", { name: "Pista" }).click();
    // Espera a contagem CRESCER. "diferente de 1" passava durante o
    // carregamento, quando existem 0 artigos, e a leitura seguinte via 0.
    await expect
      .poll(() => page.locator("article").count(), { timeout: 15_000 })
      .toBeGreaterThan(3);
  });

  test("detalhe mostra data, local e organizador", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Ver ingressos" }).click();
    await expect(page.getByText("Quando")).toBeVisible();
    await expect(page.getByText("Onde")).toBeVisible();
    await expect(page.getByText("Organização")).toBeVisible();
  });

  test("evento inexistente explica em vez de quebrar", async ({ page }) => {
    await page.goto("/eventos/999999");
    await expect(page.getByText(/não existe ou não está mais publicado/)).toBeVisible();
  });
});
