import { expect, test } from "@playwright/test";

import { entrar, sair } from "./apoio";

test.describe("acesso e sessão", () => {
  test("cada papel cai na sua área depois de entrar", async ({ page }) => {
    const destinos = [
      ["cliente", /\/minha-conta/],
      ["organizador", /\/organizador/],
      ["portaria", /\/portaria/],
    ] as const;

    for (const [conta, url] of destinos) {
      await sair(page);
      await entrar(page, conta);
      await expect(page).toHaveURL(url);
    }
  });

  test("guarda de rota é só navegação — a API é quem nega", async ({ page }) => {
    await entrar(page, "cliente");

    // A tela abre; o que não aparece é conteúdo, porque a API recusa. Se a
    // guarda fosse a única proteção, bastaria burlar o front para ler dados.
    await page.goto("/organizador");
    await expect(page.getByText("Sua conta não é de organizador.")).toBeVisible();

    const resposta = await page.request.get(
      "http://127.0.0.1:8000/api/organizer/events",
      { headers: { Authorization: `Bearer ${await pegarAccess(page)}` } },
    );
    expect(resposta.status()).toBe(403);
  });

  test("sem token a API recusa mesmo que a tela abra", async ({ page }) => {
    await page.goto("/");
    const resposta = await page.request.get("http://127.0.0.1:8000/api/tickets");
    expect(resposta.status()).toBe(401);
  });

  test("access expirado é renovado sozinho, sem derrubar o usuário", async ({ page }) => {
    await entrar(page, "cliente");

    const antes = await pegarSessao(page);
    expect(antes.refresh, "a sessão precisa guardar o refresh").toBeTruthy();

    const renovacoes: number[] = [];
    page.on("response", (r) => {
      if (r.url().includes("/api/auth/refresh")) renovacoes.push(r.status());
    });

    // Estraga o access mantendo o refresh: é o estado depois de 60 minutos.
    await page.evaluate((quebrado) => {
      const o = JSON.parse(localStorage.getItem("ingressos.sessao")!);
      o.access = quebrado;
      localStorage.setItem("ingressos.sessao", JSON.stringify(o));
    }, antes.access.slice(0, -6) + "AAAAAA");

    // Espera a renovação ACONTECER antes de julgar. O cabeçalho "Meus
    // ingressos" é markup estático e aparece antes de qualquer fetch — usá-lo
    // como sinal fazia a asserção correr antes da resposta chegar.
    const renovou = page.waitForResponse((r) => r.url().includes("/api/auth/refresh"));
    // /minha-conta dispara DUAS chamadas autenticadas em paralelo.
    await page.goto("/minha-conta");
    await renovou;
    await expect(page.getByRole("heading", { name: "Meus ingressos" })).toBeVisible();
    // Dá tempo de uma segunda renovação indevida aparecer, se houver.
    await page.waitForTimeout(1000);

    const depois = await pegarSessao(page);
    expect(depois.access).not.toBe(antes.access);
    // Uma renovação só, mesmo com duas requisições falhando juntas: senão a
    // segunda usaria um refresh já consumido.
    expect(renovacoes).toEqual([200]);
  });

  test("refresh inválido desloga em vez de entrar em laço", async ({ page }) => {
    await entrar(page, "cliente");

    let tentativas = 0;
    page.on("response", (r) => {
      if (r.url().includes("/api/auth/refresh")) tentativas++;
    });

    // Usuário COMPLETO de propósito: a primeira versão deste teste injetava
    // só { role } e a tela quebrava em user.full_name.charAt(0) antes de
    // qualquer requisição — o teste media o crash, não a renovação.
    await page.evaluate(() => {
      const o = JSON.parse(localStorage.getItem("ingressos.sessao")!);
      localStorage.setItem(
        "ingressos.sessao",
        JSON.stringify({ ...o, access: "lixo", refresh: "lixo" }),
      );
    });
    await page.goto("/minha-conta");
    // A sessão é limpa DEPOIS que a renovação falha; esperar o valor sumir é
    // mais confiável que cravar um tempo fixo.
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem("ingressos.sessao")), {
        timeout: 15_000,
      })
      .toBeNull();
    // Uma tentativa, não um laço.
    expect(tentativas).toBeLessThanOrEqual(2);
  });

  test("sessão malformada é descartada em vez de derrubar a tela", async ({ page }) => {
    /**
     * Regressão: um objeto de sessão sem `full_name` fazia o cabeçalho
     * estourar em charAt(0) e a árvore React inteira morria — tela branca, sem
     * nem conseguir sair. Acontece de verdade com sessão gravada por uma
     * versão anterior do app.
     */
    await page.goto("/");
    await page.evaluate(() => {
      localStorage.setItem(
        "ingressos.sessao",
        JSON.stringify({ access: "a", refresh: "b", user: { role: "CUSTOMER" } }),
      );
    });
    await page.goto("/minha-conta");

    // A tela abre, deslogada, e a sessão inválida é jogada fora.
    await expect(page.getByRole("link", { name: "Criar conta" })).toBeVisible();
    expect(await page.evaluate(() => localStorage.getItem("ingressos.sessao"))).toBeNull();
  });

  test("cadastro valida senha fraca no campo certo", async ({ page }) => {
    await page.goto("/criar-conta");
    await page.getByLabel("Nome completo").fill("Teste");
    await page.getByLabel("E-mail").fill(`t${Date.now()}@teste.dev`);
    await page.getByLabel("Senha").fill("123");
    await page.getByRole("button", { name: "Criar conta" }).click();

    // O erro tem que aparecer NO campo, não num "algo deu errado" genérico.
    await expect(page.getByText(/senha/i).last()).toBeVisible();
    await expect(page.getByLabel("Senha")).toHaveAttribute("aria-invalid", "true");
  });
});

async function pegarSessao(page: import("@playwright/test").Page) {
  return page.evaluate(
    () => JSON.parse(localStorage.getItem("ingressos.sessao")!) as {
      access: string;
      refresh: string;
    },
  );
}

async function pegarAccess(page: import("@playwright/test").Page) {
  return (await pegarSessao(page)).access;
}
