import { defineConfig, devices } from "@playwright/test";

/**
 * Testes de ponta a ponta contra a aplicação REAL — front servido pelo Next e
 * backend Django falando com o Postgres. Nada é dublado.
 *
 * Por que não mockar a API: o que estes testes precisam provar é justamente a
 * costura entre as duas pontas. Um mock de `/api/reservations` passaria mesmo
 * se o backend estivesse recusando a reserva.
 *
 * Pré-requisito: o backend rodando em :8000 com o seed aplicado.
 *   cd backend && python manage.py seed && python manage.py runserver
 */

const BASE = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./e2e",
  // Um worker: os testes compram ingressos do MESMO seed e mexem no mesmo
  // estoque. Em paralelo, um teste veria o efeito do outro e a falha seria
  // irreprodutível — o pior tipo.
  workers: 1,
  fullyParallel: false,
  // Só no CI: localmente um teste instável deve falhar na hora, não ser
  // escondido por uma segunda tentativa.
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  timeout: 60_000,
  expect: { timeout: 15_000 },

  use: {
    baseURL: BASE,
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    // Rastro só do que falhou: guardar tudo enche o disco sem ajudar.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    // A portaria é usada em pé, num celular. Testar só no desktop deixaria de
    // fora justamente o dispositivo em que essa tela roda.
    {
      name: "portaria-mobile",
      testMatch: /portaria\.spec\.ts/,
      use: { ...devices["Pixel 7"] },
    },
  ],

  webServer: {
    command: "npx next start --port 3100",
    url: BASE,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
