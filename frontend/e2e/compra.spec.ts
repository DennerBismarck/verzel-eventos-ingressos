import { expect, test } from "@playwright/test";

import { abrirEventoDisponivel, comprarPista, entrar, sair } from "./apoio";

test.describe("compra de pista", () => {
  test("visitante deslogado é mandado ao login e volta ao evento", async ({ page }) => {
    const id = await abrirEventoDisponivel(page);
    await page.getByRole("button", { name: "Entrar para comprar" }).click();
    // O "next" preserva para onde voltar; sem ele o usuário cairia na home e
    // teria que procurar o evento de novo.
    await expect(page).toHaveURL(new RegExp(`/entrar\\?next=.*eventos.*${id}`));
  });

  test("reserva segura o estoque antes do pagamento", async ({ page }) => {
    await entrar(page, "cliente");
    await abrirEventoDisponivel(page);

    const antes = Number(
      (await page.getByText(/disponíve/).innerText()).match(/\d+/)![0],
    );

    await page.getByRole("button", { name: "Aumentar quantidade" }).click();
    await page.getByRole("button", { name: /Reservar ingressos/ }).click();

    // A tela diz "reservado" ANTES de qualquer pagamento — é o que o backend
    // realmente faz, e o usuário precisa saber que o lugar já está guardado.
    await expect(page.getByText("Aguardando pagamento")).toBeVisible();
    await expect(page.getByText(/reservado/)).toBeVisible();

    await page.getByRole("button", { name: "Cancelar reserva" }).click();
    await expect(page.getByRole("button", { name: /Reservar ingressos/ })).toBeVisible();

    // Cancelar tem que devolver ao estoque, não só mudar o texto da tela.
    await page.reload();
    const depois = Number(
      (await page.getByText(/disponíve/).innerText()).match(/\d+/)![0],
    );
    expect(depois).toBe(antes);
  });

  test("compra emite um ingresso por lugar, com QR e código", async ({ page }) => {
    await entrar(page, "cliente");
    await abrirEventoDisponivel(page);
    await comprarPista(page, 2);

    await page.goto("/minha-conta");
    const ingressos = page.locator("article");
    await expect(ingressos.first()).toBeVisible();
    expect(await ingressos.count()).toBeGreaterThanOrEqual(2);

    await page.getByRole("button", { name: /Ampliar/ }).first().click();
    const dialogo = page.getByRole("dialog");
    await expect(dialogo.locator("svg").first()).toBeVisible();
    // O código impresso permite entrar quando a câmera falha.
    await expect(dialogo.locator(".font-mono").first()).toHaveText(
      /^[0-9a-f-]{36}$/,
    );
  });

  test("pagamento confirmado: até 5 ingressos a compra passa", async ({ page }) => {
    await entrar(page, "cliente");
    await abrirEventoDisponivel(page);

    const mais = page.getByRole("button", { name: "Aumentar quantidade" });
    for (let i = 1; i < 5; i++) await mais.click();
    await expect(page.getByRole("status")).toHaveText("5");

    await page.getByRole("button", { name: /Reservar ingressos/ }).click();
    await page.getByRole("button", { name: /^Pagar/ }).click();
    await expect(page.getByText("Compra confirmada")).toBeVisible();
  });

  test("pagamento recusado: 6 ou mais devolve o estoque e explica", async ({ page }) => {
    /**
     * O enunciado pede o pagamento simulado "contemplando a confirmação e
     * também a recusa" — no FRONT. Este caminho já existia no backend, mas
     * ficou inalcançável pela tela por um tempo: o seletor parava em 8 e a
     * recusa começava em 10. Este teste existe para que isso não volte.
     */
    await entrar(page, "cliente");
    await abrirEventoDisponivel(page);

    const disponiveis = () =>
      page.getByText(/disponíve/).innerText().then((s) => Number(s.match(/\d+/)![0]));
    const antes = await disponiveis();

    const mais = page.getByRole("button", { name: "Aumentar quantidade" });
    for (let i = 1; i < 6; i++) await mais.click();
    await expect(page.getByRole("status")).toHaveText("6");

    await page.getByRole("button", { name: /Reservar ingressos/ }).click();
    await page.getByRole("button", { name: /^Pagar/ }).click();

    // A recusa precisa dizer POR QUE, e oferecer saída.
    await expect(page.getByText("Pagamento recusado")).toBeVisible();
    await expect(page.getByText(/aprovação manual/)).toBeVisible();
    await expect(page.getByText(/voltaram para o estoque/)).toBeVisible();

    await page.getByRole("button", { name: "Escolher outra quantidade" }).click();
    await expect(page.getByRole("status")).toHaveText("1");

    // E o estoque tem que ter voltado de verdade, não só na mensagem.
    await page.reload();
    expect(await disponiveis()).toBe(antes);
  });

  test("link compartilhado mostra o ingresso sem revelar o código", async ({ page }) => {
    await entrar(page, "cliente");
    await abrirEventoDisponivel(page);
    await comprarPista(page, 1);

    await page.goto("/minha-conta");
    await page.getByRole("button", { name: /Ampliar/ }).first().click();
    const dialogo = page.getByRole("dialog");
    const codigo = (await dialogo.locator(".font-mono").first().innerText()).trim();
    const link = await dialogo.getByLabel("Link do ingresso").inputValue();
    await page.keyboard.press("Escape");

    // Quem abre o link não pode receber o que valida a entrada.
    await sair(page);
    await page.goto(link);
    await expect(page.getByText("Válido")).toBeVisible();
    // exact: sem isso casa também com o parágrafo "O código ... fica com o
    // titular", e o seletor vira ambíguo.
    await expect(page.getByText("Titular", { exact: true })).toBeVisible();
    expect(await page.locator("body").innerText()).not.toContain(codigo);
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });
});
