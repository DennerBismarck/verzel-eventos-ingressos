import { expect, test } from "@playwright/test";

import {
  abrirEventoDisponivel,
  comprarPista,
  entrar,
  pegarCodigoDoIngresso,
  sair,
} from "./apoio";

/**
 * As quatro respostas exigidas pelo enunciado, pela interface, num viewport de
 * celular — que é onde essa tela roda de verdade.
 *
 * A leitura por câmera não é testada aqui: o navegador do teste não tem câmera.
 * O que dá para garantir, e está garantido, é que a tela não quebra quando a
 * câmera falha e que a digitação manual — a alternativa exigida pelo enunciado
 * — funciona.
 */
test.describe("portaria", () => {
  test("valida, recusa repetido e recusa forjado", async ({ page }) => {
    await entrar(page, "cliente");
    const idEvento = await abrirEventoDisponivel(page);
    await comprarPista(page, 1);
    const codigo = await pegarCodigoDoIngresso(page);

    await sair(page);
    await entrar(page, "portaria");
    await page.goto("/portaria");

    // Sem evento escolhido não há como responder "evento errado".
    await expect(page.getByText("Escolha o evento para começar")).toBeVisible();
    await page.selectOption("#evento", idEvento);

    const validar = async (valor: string) => {
      await page.locator("#manual").fill(valor);
      await page.getByRole("button", { name: "Validar" }).click();
      // .fixed: o Next injeta um __next-route-announcer__ que também tem
      // role=alert, e o seletor puro fica ambíguo.
      const painel = page.locator("div[role=alert].fixed");
      await expect(painel).toBeVisible();
      const titulo = await painel.getByRole("heading").innerText();
      await page.getByRole("button", { name: "Próximo ingresso" }).click();
      return titulo;
    };

    expect(await validar(codigo)).toBe("Entrada liberada");
    expect(await validar(codigo)).toBe("Já utilizado");
    expect(await validar("nao-e-um-codigo")).toBe("Ingresso inválido");
  });

  test("acusa ingresso de outro evento", async ({ page }) => {
    await entrar(page, "cliente");
    await abrirEventoDisponivel(page);
    await comprarPista(page, 1);
    const codigo = await pegarCodigoDoIngresso(page);

    await sair(page);
    await entrar(page, "portaria");
    await page.goto("/portaria");

    // Escolhe deliberadamente uma sessão que não é a do ingresso.
    const opcoes = page.locator("#evento option");
    await page.selectOption("#evento", { index: (await opcoes.count()) - 1 });

    await page.locator("#manual").fill(codigo);
    await page.getByRole("button", { name: "Validar" }).click();
    const painel = page.locator("div[role=alert].fixed");
    await expect(painel.getByRole("heading")).toHaveText("Evento errado");
    // Precisa dizer de QUAL evento é, senão a portaria não sabe para onde mandar.
    await expect(painel).toContainText("Este ingresso é de:");
  });

  test("cliente não acessa a tela da portaria", async ({ page }) => {
    await entrar(page, "cliente");
    await page.goto("/portaria");
    await expect(page.getByText("Sua conta não é de portaria.")).toBeVisible();
    await expect(page.locator("#manual")).toHaveCount(0);
  });
});
