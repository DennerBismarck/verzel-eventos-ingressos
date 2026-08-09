# Plataforma de Eventos e Ingressos

Desafio Elite Dev (Verzel) — organizador publica eventos a partir de um catálogo externo,
cliente compra ingressos com QR, portaria valida na entrada.

> **Status:** Dia 0 concluído — scaffold, autenticação JWT com 3 papéis, seed de usuários,
> deploy configurado. Fluxo de compra em construção.
> Planejamento em [`docs/PLANNING.md`](docs/PLANNING.md), decisões em [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Stack
- **Front-end:** Next.js 16 (App Router, React 19, TypeScript, Tailwind 4)
- **Back-end:** Django 5.2 + Django REST Framework, JWT via `djangorestframework-simplejwt`
- **Banco:** PostgreSQL 16 (via Docker Compose em dev)
- **API externa:** TMDb (filmes) / Ticketmaster Discovery (shows)

---

## Como rodar

### Pré-requisitos
Python 3.12+, Node 20+, Docker (para o Postgres).

### 1. Banco
```bash
docker compose up -d db
```
Sobe o Postgres na porta **5433** do host (5433, não 5432, para não colidir com um
Postgres já instalado na máquina).

### 2. Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # ajuste SECRET_KEY e TMDB_API_KEY
python manage.py migrate
python manage.py seed         # cria os usuários de teste
python manage.py runserver    # http://127.0.0.1:8000
```

### 3. Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                   # http://localhost:3000
```

A home mostra um indicador de conexão com a API — bolinha verde significa que
front e back estão conversando.

---

## Dados de teste (seed)

Senha de **todos**: `verzel123`

| Papel | E-mail |
|-------|--------|
| Organizador | `organizador@verzel.dev` |
| Cliente 1 | `cliente1@verzel.dev` |
| Cliente 2 | `cliente2@verzel.dev` |
| Portaria | `portaria@verzel.dev` |

`python manage.py seed` é idempotente (rodar de novo não duplica).
Use `--reset` para recriar do zero.

---

## API

Documentação interativa: **`/api/docs`** (Swagger UI, gerado do código via drf-spectacular).

| Método | Rota | Acesso | O que faz |
|--------|------|--------|-----------|
| GET | `/api/health` | público | Verifica se a API está de pé |
| POST | `/api/auth/register` | público | Cria conta (`role`: ORGANIZER, CUSTOMER ou GATE) |
| POST | `/api/auth/login` | público | Devolve `access`, `refresh` e os dados do usuário |
| POST | `/api/auth/refresh` | público | Troca o refresh por um novo access |
| GET | `/api/auth/me` | autenticado | Dados do usuário do token |

Exemplo:
```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"organizador@verzel.dev","password":"verzel123"}'
```

> **Nota de segurança:** o padrão de permissão do projeto é `IsAuthenticated`
> (fail closed). Endpoint público declara `AllowAny` explicitamente — assim,
> esquecer a permissão numa view nova fecha a porta em vez de abri-la.

---

## Deploy

- **Front (Vercel):** importe o repo e defina **Root Directory = `frontend`**.
  Variável de ambiente: `NEXT_PUBLIC_API_URL` = URL da API na Render.
- **Back (Render):** New → Blueprint, apontando para este repo. O
  [`render.yaml`](render.yaml) descreve o web service + o Postgres.
  A Render vai pedir `CORS_ALLOWED_ORIGINS` (URL da Vercel) e `TMDB_API_KEY`;
  `SECRET_KEY` e `TICKET_SIGNING_KEY` ela mesma gera.

| Ambiente | URL |
|----------|-----|
| Front (Vercel) | https://verzel-eventos-ingressos.vercel.app |
| Back (Render) | https://ingressos-api.onrender.com |
| Docs da API | https://ingressos-api.onrender.com/api/docs |

> A Render no plano free hiberna após ~15 min sem tráfego. A primeira
> requisição depois disso pode levar ~50s. Não é bug — é o cold start.

---

## Decisões técnicas
O log completo está em [`docs/DECISIONS.md`](docs/DECISIONS.md). Destaques:

- **Mesmo lugar não vendido 2x:** transação + `select_for_update` na linha do
  evento/assento, com constraint no banco como rede de segurança.
- **QR não forjável:** o QR carrega código + assinatura HMAC-SHA256 feita com uma
  chave que só o servidor tem (`TICKET_SIGNING_KEY`, separada da `SECRET_KEY`).
- **Portaria sem validar 2x:** lock na linha do ingresso dentro da transação e
  checagem de estado → válido / inválido / já utilizado / evento errado.
- **Papéis:** campo `role` no User + permission classes do DRF por endpoint.
  A guarda de rota no front é UX; a autorização real é no backend.

---

## Uso de IA
_(seção obrigatória — preencher ao longo da semana)_

**Ferramenta:** Claude Code (Opus).

**Onde usei IA:** scaffold do Django e do Next, configuração (settings, CORS,
JWT, WhiteNoise), `render.yaml`, comando de seed, página hello world.

**Onde NÃO usei IA (escrito à mão):** _(a preencher — a ideia é: models de
negócio, lógica de reserva, no-double-sell, geração/assinatura do QR e validação
da portaria)_.

Artefatos de contexto usados com a IA estão versionados em [`docs/`](docs/).

---

## Notas de desenvolvimento

- `npx tsc --noEmit` sozinho acusa `Cannot find name 'LayoutProps'`. Não é erro
  real: é um tipo que o Next gera em `.next/types`. Use `npm run build` (ou
  `npx next typegen` antes do `tsc`) como typecheck válido.
- Se a porta 3000 estiver ocupada: `npm run dev -- --port 3001`. A porta 3001 já
  está liberada no CORS de desenvolvimento.

## O que faltou / não funciona como esperado
_(seja honesto aqui — o enunciado diz que a ausência de explicação penaliza)_

- Fluxo de compra, ingresso com QR e portaria: em construção (Dias 1–4).
- Mapa de assentos: planejado para o Dia 5, depois do fluxo de pista estar no ar.
