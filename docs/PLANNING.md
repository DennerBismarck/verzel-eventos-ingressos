# Planejamento — Plataforma de Eventos e Ingressos (Desafio Verzel)

> Stack: **Django REST Framework (Python) + Next.js (React) + PostgreSQL**
> Reserva: **pista (quantidade) primeiro, mapa de assentos depois**
> Modo de trabalho: **par** — Denner escreve o núcleo; IA no boilerplate; tudo explicado pra defender.

---

## 0. Princípio-guia (ler todo dia)
1. **Fluxo inteiro simples > pedaço sofisticado pela metade.** Faça a pista funcionar de ponta a ponta e no ar ANTES de tocar em mapa de assentos.
2. **Sua mão no resultado.** Você escreve a lógica de negócio (reserva, no-double-sell, QR, portaria). IA só no repetitivo — e você tem que saber explicar cada linha.
3. **Commit todo dia** com mensagem descritiva. O histórico é avaliado.
4. **Documente as decisões** em `DECISIONS.md` enquanto decide (não no fim).

---

## 1. Arquitetura

```
┌─────────────────┐        HTTPS/JSON        ┌──────────────────────┐
│  Next.js (React)│  ───────────────────────▶ │  Django REST (DRF)   │
│  Vercel         │  ◀─────────────────────── │  Render/Railway      │
│  - páginas      │        JWT (Bearer)       │  - API /api/...      │
│  - QR scan cam  │                           │  - auth 3 papéis     │
└─────────────────┘                           │  - regras de negócio │
                                              └──────────┬───────────┘
                                                         │
                                    ┌────────────────────┼───────────────────┐
                                    │                    │                   │
                              ┌─────▼─────┐        ┌──────▼──────┐     ┌──────▼──────┐
                              │PostgreSQL │        │ TMDb API    │     │Ticketmaster │
                              │           │        │ (filmes)    │     │(shows, opc.)│
                              └───────────┘        └─────────────┘     └─────────────┘
```

- **Chave da API externa fica no backend** (nunca no front). O front pede ao Django "buscar catálogo", o Django chama TMDb/Ticketmaster.
- **Auth:** `djangorestframework-simplejwt`. Usuário tem `role` ∈ {ORGANIZER, CUSTOMER, GATE}. Permissões DRF checam o papel por endpoint.

---

## 2. Modelo de dados (Django models)

- **User** (custom, herda AbstractUser): `role` = ORGANIZER | CUSTOMER | GATE.
- **Event**: `organizer(FK User)`, `source` (tmdb|ticketmaster), `external_id`, `title`, `description`, `image_url`, `venue`, `starts_at`, `kind` (GA=pista | SEATED=assento), `status` (draft|published), `created_at`.
  - GA: `price`, `capacity`, `sold_count`.
- **Seat** (só p/ SEATED): `event(FK)`, `section`, `row`, `number`, `price`, `status` (available|sold). Unique(`event`,`section`,`row`,`number`).
- **Reservation**: `customer(FK)`, `event(FK)`, `status` (pending|paid|refused|cancelled), `quantity` (GA) / `seats(M2M Seat)`, `total_price`, `created_at`.
- **Ticket**: `reservation(FK)`, `event(FK)`, `customer(FK)`, `seat(FK null)`, `code` (uuid4), `signature` (HMAC), `status` (valid|used), `used_at`, `used_by(FK User null)`, `share_token` (uuid4).
- **Payment** (simulado): `reservation(FK)`, `status` (confirmed|refused), `created_at`.

---

## 3. As 4 partes que a defesa VAI cobrar (domine estas)

### 3.1 Mesmo lugar não vendido 2x
- **Sempre dentro de `transaction.atomic()`.**
- **Pista (GA):** trave a linha do evento com `Event.objects.select_for_update().get(id=...)`, cheque `capacity - sold_count >= quantity`, então `sold_count += quantity`. Uma constraint no banco (`sold_count <= capacity`) é o cinto de segurança.
- **Assento (SEATED):** `Seat.objects.select_for_update().filter(id__in=..., status='available')`. Se a contagem travada ≠ pedida → algum assento já foi vendido → aborta a transação. Marca como `sold` só os travados.
- **Por que funciona:** `select_for_update` segura um lock de linha até o commit; uma segunda transação concorrente espera e vê o estado já atualizado. Sem isso = race condition (dois compram o mesmo assento).

### 3.2 QR que não pode ser forjado
- O QR **não** carrega só o id do ingresso. Carrega `ticket_id + code + assinatura`, onde `assinatura = HMAC-SHA256(SECRET_KEY, ticket_id + code)`.
- A portaria manda o conteúdo do QR ao backend, que **recalcula a assinatura** e compara. Sem a `SECRET_KEY` do servidor, ninguém gera uma assinatura válida → não dá pra forjar.
- (Alternativa equivalente: um JWT curto assinado pelo servidor como payload do QR.)

### 3.3 Compartilhar ingresso por link
- Cada Ticket tem um `share_token` (uuid aleatório). Rota pública `/ingresso/{share_token}` mostra o ingresso (somente leitura).
- Token aleatório = não dá pra adivinhar/enumerar. (Decisão a documentar: link é view-only; validar só a portaria faz.)

### 3.4 Portaria valida sem validar 2x
- `POST /api/gate/validate` recebe o conteúdo do QR (ou código manual) + o evento selecionado na portaria.
- Dentro de `transaction.atomic()` + `select_for_update` no Ticket:
  1. Assinatura inválida / não existe → **inválido**
  2. `ticket.event != evento_da_portaria` → **evento errado**
  3. `ticket.status == 'used'` → **já utilizado** (retorna quando/por quem)
  4. senão → marca `used`, `used_at=now` → **válido**
- O lock impede que dois leitores validem o mesmo ingresso ao mesmo tempo.

---

## 4. API (rascunho de endpoints)

```
POST /api/auth/register            (role no corpo)     POST /api/auth/login  → JWT
GET  /api/catalog?q=&source=       [ORGANIZER]  proxy TMDb/Ticketmaster
POST /api/events                   [ORGANIZER]  cria evento a partir do catálogo
GET  /api/events?search=&date=     [público]    lista publicados (+ filtro)
GET  /api/events/{id}                            detalhe (+ assentos se SEATED)
POST /api/events/{id}/reserve      [CUSTOMER]   {quantity} ou {seat_ids}
POST /api/reservations/{id}/pay    [CUSTOMER]   {simulate: confirm|refuse}
GET  /api/tickets/me               [CUSTOMER]   meus ingressos (+ QR)
GET  /api/tickets/shared/{token}   [público]    ingresso compartilhado
POST /api/gate/validate            [GATE]       valida QR/código
```

---

## 5. Frontend (páginas Next.js)
- `/` — lista + busca/filtro de eventos publicados
- `/eventos/[id]` — detalhe + fluxo de reserva (quantidade OU mapa)
- `/checkout` — pagamento simulado (confirma/recusa)
- `/meus-ingressos` — lista + QR (`qrcode.react`)
- `/ingresso/[shareToken]` — ingresso compartilhado (view-only)
- `/organizador` — painel: buscar catálogo externo, criar/gerenciar eventos
- `/portaria` — câmera lê QR (`html5-qrcode`) + campo manual → válido/inválido/já usado/evento errado
- `/login`, `/registro`
- Guarda de rota por papel (ORGANIZER/CUSTOMER/GATE).

---

## 6. Cronograma — 7 dias

> Regra: ao fim do **Dia 4** você tem o fluxo de PISTA completo e NO AR. Isso já é entregável. Tudo depois é upside.

| Dia | Meta | "Chão garantido" |
|-----|------|------------------|
| **0** (setup) | Repo, docs, scaffold Django+Next, Postgres, JWT com 3 papéis, models base + migrations, seed esqueleto. **Deploy "hello world" cedo** pra destravar deploy. | auth funcionando |
| **1** | Integração TMDb (proxy no backend) + Organizador cria/publica evento GA. Lista + detalhe no front. | criar e ver evento |
| **2** | Reserva GA + **no-double-sell (transação)** + pagamento simulado (confirma/recusa) + geração de Ticket com **QR assinado**. | comprar ingresso |
| **3** | "Meus ingressos" + render QR + compartilhar por link. Backend da portaria (`validate`, 4 estados, sem validar 2x). | ter e compartilhar ingresso |
| **4** | Portaria no front: **câmera QR** + código manual. **Fluxo GA completo + deployado.** ✅ ponto de entrega seguro | **projeto entregável** |
| **5** | Mapa de assentos (SEATED): modelar seats, UI do mapa, no-double-sell por assento. | assentos |
| **6** | Polimento: UI, tratamento de erros, busca/filtro, painel organizador, cancelamento+devolução (opcional), **testes básicos** (pytest no no-double-sell e na validação). | qualidade |
| **7** | README completo (com **seção de uso de IA**), `DECISIONS.md` final, conferir seed, **deploy final**, buffer de bugs, commits limpos. **Enviar.** | entrega |

---

## 7. Diferenciais que valem nota (se sobrar tempo, nesta ordem)
1. Deploy publicado (**+1 ponto oficial**) — priorize.
2. Testes básicos (pytest) nas 4 regras críticas.
3. Docker Compose (backend + Postgres).
4. Busca/filtro + painel do organizador.
5. Cancelamento com devolução ao estoque.
6. Mapa de assentos em tempo real.

## 8. NÃO fazer (o próprio enunciado dispensa)
Nota fiscal, revenda entre usuários, app nativo, recuperação de senha, envio por e-mail.

---

## 9. Preparação da defesa (a entrevista depois do projeto)
Saiba responder de cabeça, em voz alta:
- Como você garante que o mesmo assento não é vendido 2x? (→ `select_for_update` + transação + constraint)
- Por que o QR não pode ser forjado? (→ HMAC/assinatura com segredo do servidor)
- Como os 3 papéis são protegidos no backend? (→ permissões DRF por papel)
- Por que Django + Next e não tudo num framework só? (→ seu ponto forte no backend Python + React no front; separação clara)
- Onde usou IA e onde não usou? (→ tenha a resposta pronta; está no README)
- O que você faria diferente com mais tempo? (→ WebSocket pro mapa em tempo real, fila de reserva, etc.)
- Qual foi o bug mais chato e como debugou? (→ tenha uma história real)
