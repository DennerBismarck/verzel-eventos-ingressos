import { chromium, devices } from 'playwright';
const SP = process.env.SP ?? new URL('.', import.meta.url).pathname;
const F = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:3100';
const { idEvento, codigo } = JSON.parse(process.env.DADOS);

const b = await chromium.launch({
  args: [
    '--use-fake-ui-for-media-stream',      // concede a permissao sozinho
    '--use-fake-device-for-media-stream',  // camera virtual
    `--use-file-for-fake-video-capture=${SP}/qr.y4m`,
  ],
});
const ctx = await b.newContext({ ...devices['Pixel 7'], permissions: ['camera'] });
const p = await ctx.newPage();
const errs = [];
p.on('pageerror', e => errs.push(e.message.split(';')[0]));

await p.goto(F + '/entrar', { waitUntil: 'networkidle' });
await p.getByRole('button', { name: /portaria@verzel.dev/ }).click();
await p.getByRole('button', { name: 'Entrar', exact: true }).click();
await p.waitForURL('**/portaria');
await p.waitForSelector('select#evento');
await p.selectOption('select#evento', idEvento);

// A camera precisa abrir de verdade — se cair no estado "indisponivel", o
// teste nao esta exercitando a leitura.
await p.waitForSelector('text=Aponte para o QR do ingresso', { timeout: 30000 });
console.log('  camera abriu: sim');
console.log('  video na tela:', await p.locator('#leitor-qr video').count());

const painel = p.locator('div[role=alert].fixed');
await painel.waitFor({ timeout: 45000 });
const titulo = await painel.getByRole('heading').innerText();
const detalhe = await painel.locator('p').first().innerText();
await p.screenshot({ path: `${SP}/camera-leu.png` });
console.log('  LEITURA PELA CAMERA ->', titulo, '|', detalhe);
console.log('  codigo esperado:', codigo.slice(0, 13) + '...');
console.log('  erros:', errs.length ? errs.slice(0,2) : 'nenhum');
await b.close();
