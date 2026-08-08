# Plataforma de Eventos e Ingressos

Desafio Elite Dev (Verzel) — organizador publica eventos a partir de um catálogo externo,
cliente compra ingressos com QR, portaria valida na entrada.

> **Status:** em desenvolvimento. Veja o planejamento em [`docs/PLANNING.md`](docs/PLANNING.md)
> e o log de decisões em [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Stack
- **Front-end:** Next.js (React)
- **Back-end:** Django REST Framework (Python)
- **Banco:** PostgreSQL
- **API externa:** TMDb (filmes) / Ticketmaster Discovery (shows)

## Como rodar (preencher conforme construir)
### Pré-requisitos
- Python 3.x, Node 20+, PostgreSQL 15+ (ou Docker)

### Backend
```bash
# cd backend
# python -m venv .venv && source .venv/bin/activate
# pip install -r requirements.txt
# cp .env.example .env   # preencher DATABASE_URL, SECRET_KEY, TMDB_API_KEY...
# python manage.py migrate
# python manage.py seed   # cria organizador, 2 clientes, portaria e 1 evento publicado
# python manage.py runserver
```

### Frontend
```bash
# cd frontend
# npm install
# cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=...
# npm run dev
```

## Dados de teste (seed)
| Papel | E-mail | Senha |
|-------|--------|-------|
| Organizador | _(preencher)_ | _(preencher)_ |
| Cliente 1 | _(preencher)_ | _(preencher)_ |
| Cliente 2 | _(preencher)_ | _(preencher)_ |
| Portaria | _(preencher)_ | _(preencher)_ |

## Deploy
- Front: _(URL Vercel)_
- Back: _(URL Render/Railway)_

## Decisões técnicas
Ver [`docs/DECISIONS.md`](docs/DECISIONS.md). Destaques:
- **Mesmo lugar não vendido 2x:** transações + `select_for_update`.
- **QR não forjável:** assinatura HMAC com segredo do servidor.
- **Portaria sem validar 2x:** lock + checagem de estado (válido/inválido/já usado/evento errado).

## Uso de IA
_(preencher: quais ferramentas, em que partes usei e o que fiz sem IA — a Verzel valoriza isso)_

## O que faltou / não funciona como esperado
_(seja honesto aqui — o enunciado diz que a ausência de explicação penaliza)_
