# Log de Decisões (ADR-lite)

> A Verzel disse que quer ver COMO você pensa e o que descartou. Preencha isto ENQUANTO decide,
> não no fim. Uma linha por decisão. Formato: Decisão · Por quê · O que descartei.

| # | Decisão | Por quê | Alternativa descartada |
|---|---------|---------|------------------------|
| 1 | Django REST + Next.js (não tudo em Next) | Backend Python é meu ponto forte; auth/roles, transações e admin (seed) saem rápido e bem defendidos | Full Next.js/Prisma (menos vitrine de backend); Express (mais boilerplate de auth) |
| 2 | Reserva: pista primeiro, assentos depois | Dica oficial: fluxo inteiro > peça pela metade. Garante entregável no dia 4 | Ir direto no mapa de assentos (risco de prazo) |
| 3 | QR assinado com HMAC(SECRET, ...) | Impede forjar o ingresso sem o segredo do servidor | Só o UUID no QR (forjável/enumerável) |
| 4 | JWT (simplejwt) | Stateless, simples de guardar 3 papéis | Sessão por cookie (mais estado no servidor) |
| 5 | Login por **e-mail**, `username` removido do User | Um identificador só; é o que o usuário já digita e o que o seed do enunciado usa | Manter `username` (campo a mais, sem valor pro domínio) |
| 6 | `role` como CharField com choices no User | São exatamente 3 papéis mutuamente exclusivos; simples de serializar no JWT e de explicar | Groups/Permissions do Django (resolve um problema de granularidade que não temos) |
| 7 | Permissão padrão do DRF = `IsAuthenticated`, público é explícito | **Fail closed**: esquecer a permissão numa view nova nega acesso em vez de expor | Default `AllowAny` (um esquecimento vira vazamento) |
| 8 | `TICKET_SIGNING_KEY` separada da `SECRET_KEY` | Rotacionar uma não invalida a outra; ingressos emitidos sobrevivem à troca da chave do Django | Assinar o QR com a própria `SECRET_KEY` (acopla dois ciclos de vida diferentes) |
| 9 | `role` embutido no JWT | Front sabe qual menu montar logo após o login, sem 2ª chamada; token é assinado, não dá pra adulterar | Consultar `/me` sempre (round-trip a mais em toda navegação). **Atenção:** é só pra UI — a autorização real continua sendo a permission class lendo o banco |
| 10 | Postgres via Docker Compose na porta **5433** | Não colide com um Postgres já instalado no host; já engatilha o bônus "Docker Compose" do enunciado | Instalar Postgres na máquina (mais atrito pra quem for avaliar) |
| 11 | Config por env var (`django-environ` + `DATABASE_URL`) | Mesmo código em dev e produção; é o formato que Render/Railway entregam pronto | Settings separados por ambiente (mais arquivos, mais chance de divergir) |
| 12 | Backend na **Render** (blueprint), front na **Vercel** | Vercel é o habitat natural do Next; Render tem free tier com Postgres e lê `render.yaml` versionado | Backend na Vercel como serverless (transação + `select_for_update` fica desconfortável em ambiente efêmero) |
| 13 | Hello world com ping na API já no Dia 0 | Deploy é o risco menos controlável do prazo; descobrir CORS/env quebrado no Dia 7 seria fatal | Deixar o deploy pro fim (risco concentrado no pior momento) |
| _ | _(adicione as suas ao longo da semana)_ | | |

## Uso de IA (rascunho — vira seção do README)
- Ferramentas: Claude Code (Opus), em modo par.
- **Dia 0 — IA:** scaffold Django/Next, `settings.py`, CORS, JWT/simplejwt, custom User + manager,
  permission classes por papel, comando `seed`, `render.yaml`, página hello world.
- **Dia 0 — sem IA:** _(nada ainda — Dia 0 é infraestrutura)_
- **A partir do Dia 1 — escrito à mão por mim:** models de negócio, lógica de reserva,
  no-double-sell (`select_for_update`), geração/assinatura do QR, validação da portaria.

## Bugs que valem contar na defesa

### Dia 0 — "Failed to fetch" no front em produção
**Sintoma:** front na Vercel mostrava "Sem resposta da API", mas abrir
`https://ingressos-api.onrender.com/api/health` direto no navegador retornava 200.

**Como isolei:** `curl` com e sem o header `Origin`. Sem `Origin` → 200 normal.
Com `Origin: https://verzel-eventos-ingressos.vercel.app` → **também 200, mas sem
o header `access-control-allow-origin`**. A resposta trazia `vary: origin`, o que
prova que o middleware de CORS rodou e decidiu *não* liberar — logo, a origem não
estava na allowlist, e não era API fora do ar nem cold start (0,58s de resposta).

**Causa:** `CORS_ALLOWED_ORIGINS` na Render ainda apontava para `http://localhost:3000`,
valor posto no primeiro deploy antes de a URL da Vercel existir.

**Aprendizado:** o servidor respondeu normalmente; quem barrou foi o **browser**, que
descartou o corpo antes de o JavaScript vê-lo. Como o `fetch()` nunca chega a receber
uma resposta, não há status para reportar — daí a mensagem genérica "Failed to fetch".
Por isso o `curl` funcionava e o site não: curl não aplica same-origin policy.
CORS não protege o servidor, protege o **usuário** — impede que um site qualquer leia,
no navegador dele, dados de outra origem em nome dele.

### Checklist da defesa (marcar quando souber explicar de cabeça, em voz alta)
- [ ] Por que `select_for_update` resolve o double-sell — e o que acontece sem ele
- [ ] Por que HMAC impede forjar o QR (e por que só UUID não impediria)
- [ ] Por que a permissão é checada no backend e não só escondendo o botão no front
- [ ] Por que o default de permissão é `IsAuthenticated` e não `AllowAny`
- [ ] O que é o `refresh` token e por que o `access` é curto
