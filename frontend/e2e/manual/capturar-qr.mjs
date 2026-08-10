import { chromium } from 'playwright';
const SP = process.env.SP ?? new URL('.', import.meta.url).pathname;
const F = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:3100';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto(F + '/entrar', { waitUntil: 'networkidle' });
await p.getByRole('button', { name: /cliente1@verzel.dev/ }).click();
await p.getByRole('button', { name: 'Entrar', exact: true }).click();
await p.waitForURL('**/minha-conta');
// compra um ingresso novo, para nao pegar um ja validado
await p.goto(F + '/', { waitUntil: 'networkidle' });
await p.getByRole('link', { name: 'Ver ingressos' }).click();
await p.waitForURL('**/eventos/*');
const idEvento = p.url().split('/').pop();
await p.getByRole('button', { name: /Reservar ingressos/ }).click();
await p.getByRole('button', { name: /^Pagar/ }).click();
await p.waitForSelector('text=Compra confirmada');
await p.goto(F + '/minha-conta', { waitUntil: 'networkidle' });
await p.getByRole('button', { name: /Ampliar/ }).first().click();
const dlg = p.getByRole('dialog');
await dlg.locator('svg').first().waitFor();
const codigo = (await dlg.locator('.font-mono').first().innerText()).trim();
// screenshot so do QR grande, com margem branca (zona de silencio do padrao)
await dlg.locator('svg').first().screenshot({ path: `${SP}/qr.png` });
console.log(JSON.stringify({ idEvento, codigo }));
await b.close();
