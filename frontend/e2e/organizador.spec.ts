import { expect, test } from "@playwright/test";

import {
  abrirEventoDisponivel,
  comprarPista,
  entrar,
  encontrarLinha,
  sair,
} from "./apoio";

test.describe("organizador", () => {
  test("painel lista os próprios eventos, inclusive rascunho", async ({ page }) => {
    await entrar(page, "organizador");
    await expect(page.getByRole("heading", { name: "Meus eventos" })).toBeVisible();
    await expect(page.getByText("Rascunho").first()).toBeVisible();
    await expect(page.getByText("Publicado").first()).toBeVisible();
    // A barra de ocupação é o que dá a leitura rápida de como o evento vai.
    await expect(page.getByRole("progressbar").first()).toBeVisible();
  });

  test("resumo do topo mostra receita, ingressos e o próximo evento", async ({ page }) => {
    await entrar(page, "organizador");

    await expect(page.getByText("Receita confirmada")).toBeVisible();
    await expect(page.getByText("Ingressos vendidos")).toBeVisible();
    await expect(page.getByText("Próximo evento")).toBeVisible();
    // Dinheiro formatado, e não a string crua da API.
    await expect(page.getByText(/^R\$\s/).first()).toBeVisible();
  });

  test("separa futuros de passados e filtra por status", async ({ page }) => {
    await entrar(page, "organizador");

    // A aba começa nos próximos: o seed tem sessões que já aconteceram, e elas
    // não podem aparecer aqui.
    const passado = page.locator("article").filter({ hasText: "Encerrado" });
    await expect(passado).toHaveCount(0);

    await page.getByRole("button", { name: /Já aconteceram/ }).click();
    await expect(passado.first()).toBeVisible();

    // O filtro é do SERVIDOR: a lista é paginada, então filtrar na tela só
    // reordenaria a página atual.
    await page.getByRole("button", { name: "Próximos" }).click();
    await page.getByRole("button", { name: "Rascunhos" }).click();
    // Escopado nas linhas da lista: getByText("Publicado") solto casa por
    // SUBSTRING e pegava o próprio chip "Publicados" do filtro — o teste
    // acusaria o app de não filtrar nada.
    await expect(page.locator("article").filter({ hasText: "Publicado" })).toHaveCount(0);
    await expect(page.locator("article").filter({ hasText: "Rascunho" }).first()).toBeVisible();
  });

  test("lista paginada avisa que tem mais, em vez de esconder", async ({ page }) => {
    await entrar(page, "organizador");

    // A API pagina de 12 em 12. Antes do botão, o 13º evento simplesmente não
    // existia na tela e nada avisava — o organizador concluiria que o evento
    // lá do fim tinha sumido.
    const linhas = page.locator("article");
    await expect(linhas).toHaveCount(12);

    const mais = page.getByRole("button", { name: "Mostrar mais eventos" });
    await expect(mais).toBeVisible();
    await mais.click();

    await expect.poll(() => linhas.count()).toBeGreaterThan(12);
    await expect(mais).toHaveCount(0);
  });

  test("publicar e despublicar muda a vitrine", async ({ page }) => {
    await entrar(page, "organizador");
    // Filtra por rascunho em vez de procurar na lista: com mais de 12 eventos
    // o rascunho pode estar na segunda página.
    await page.getByRole("button", { name: "Rascunhos" }).click();
    const rascunho = page.locator("article").filter({ hasText: "Rascunho" }).first();
    const titulo = await rascunho.getByRole("heading").innerText();

    await rascunho.getByRole("button", { name: "Publicar" }).click();

    // Publicado, ele sai do filtro "Rascunhos" — o sumiço É a confirmação de
    // que a mudança valeu. Para ver o novo estado, volta para "Todos".
    await expect(page.locator("article").filter({ hasText: titulo })).toHaveCount(0);
    await page.getByRole("button", { name: "Todos" }).click();

    const linha = await encontrarLinha(page, titulo);
    await expect(linha.getByText("Publicado")).toBeVisible();

    await sair(page);
    await page.goto(`/?q=${encodeURIComponent(titulo.split(" ")[0])}`);
    await expect(page.locator("article").first()).toBeVisible();

    // Devolve ao estado do seed, senão o teste da vitrine (que espera o
    // rascunho escondido) passa a falhar dependendo da ordem de execução.
    //
    // Despublicar mora atrás do menu de três pontinhos: é a ação que tira o
    // evento do ar para todo mundo, e ficava colada no botão "Vendas".
    await entrar(page, "organizador");
    // A lista abre paginada: o evento pode estar na segunda página, e é
    // exatamente o que um organizador faria para chegar até ele.
    const paraDespublicar = await encontrarLinha(page, titulo);
    await paraDespublicar.getByRole("button", { name: /Mais ações/ }).click();
    await page.getByRole("menuitem", { name: "Despublicar" }).click();

    // Confere pelo FILTRO, e não caçando na lista completa: a mudança faz a
    // lista recarregar do zero, as páginas já abertas se perdem e o evento
    // volta para a segunda. Filtrado por rascunho ele é o único, na primeira.
    await page.getByRole("button", { name: "Rascunhos" }).click();
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
    // .first(): o local aparece duas vezes na página — na ficha "Onde" e no
    // bloco "Como chegar". As duas são corretas; o seletor é que precisa dizer
    // qual delas basta.
    await expect(page.getByText("Cine Teste, São Paulo").first()).toBeVisible();
    await expect(page.getByText("R$ 45,00").first()).toBeVisible();
  });

  test("prévia do mapa acompanha filas e lugares digitados", async ({ page }) => {
    await entrar(page, "organizador");
    await page.goto("/organizador/novo");
    await page.locator("#conteudo").getByRole("button", { name: "Buscar" }).click();

    const primeiro = page.locator("li button").first();
    const semChave = page.getByText(/sem chave de API/);
    await expect(primeiro.or(semChave)).toBeVisible();
    test.skip(await semChave.isVisible(), "catálogo sem chave neste ambiente");

    await primeiro.click();
    await page.getByRole("radio", { name: /Lugar marcado/ }).check();

    // O padrão é 5 filas × 10 lugares.
    await expect(page.getByText("50 lugares").first()).toBeVisible();

    await page.getByLabel("Filas", { exact: true }).fill("8");
    await page.getByLabel("Por fila", { exact: true }).fill("12");
    await expect(page.getByText("96 lugares").first()).toBeVisible();

    // Seção nova nasce SEM nome — e o formulário diz por que não dá para
    // seguir, em vez de deixar um "Seção 2" provisório virar definitivo.
    await page.getByRole("button", { name: "Adicionar seção" }).click();
    await expect(page.getByPlaceholder("Ex.: Balcão, Camarote").nth(1)).toHaveValue("");
    await page.getByRole("button", { name: /Criar e publicar/ }).click();
    await expect(page.getByText("Dê um nome à seção.")).toBeVisible();
    await expect(page).toHaveURL(/\/organizador\/novo/);
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

    // A recusa aparece ANTES do envio, no campo que a causou — o servidor
    // recusaria de qualquer forma, e a mensagem é a mesma dos dois lados.
    await expect(page.getByText("O evento precisa começar no futuro.")).toBeVisible();

    await page.getByRole("button", { name: /Criar e publicar/ }).click();
    await expect(page).toHaveURL(/\/organizador\/novo/);
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
