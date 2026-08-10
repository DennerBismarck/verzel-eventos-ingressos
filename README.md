# Plataforma de Eventos e Ingressos

Desafio Elite Dev (Verzel) — organizador publica eventos a partir de um catálogo externo,
cliente compra ingressos com QR, portaria valida na entrada.

> **Status:** escopo completo e publicado — vitrine, compra por pista **e por
> lugar marcado**, ingresso com QR assinado, compartilhamento por link e
> validação na portaria.
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

### Telas

| Rota | Quem usa | O que faz |
|------|----------|-----------|
| `/` | qualquer um | Vitrine com busca e filtro por tipo |
| `/eventos/{id}` | qualquer um | Detalhe + compra (reserva → pagamento) |
| `/minha-conta` | cliente | Ingressos com QR, link de compartilhamento, histórico |
| `/ingresso/{token}` | público | Ingresso compartilhado, **somente leitura** |
| `/organizador` | organizador | Eventos próprios e publicação |
| `/organizador/novo` | organizador | Busca no catálogo externo e criação |
| `/organizador/vendas/{id}` | organizador | Receita, ocupação e quem comprou |
| `/portaria` | portaria | Leitura por câmera + digitação manual |

O design segue Sympla, Eventim e Ingresso.com: grade densa de pôsteres em 2:3,
bloco de data sobre a imagem, laranja no CTA. A tela da portaria é pensada para
celular em pé, com resultado em tela cheia, som e vibração.

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

Também cria **12 eventos** do organizador acima:

- **10 de pista publicados** — um deles já esgotado, para exibir esse estado;
- **1 em rascunho** — prova que a vitrine pública filtra por status;
- **1 de lugar marcado** — teatro de 80 poltronas em duas seções com preços
  diferentes (Plateia R$ 90, Balcão R$ 60) e 12 lugares já ocupados, para o mapa
  não abrir todo verde.

As datas são relativas ao dia em que o seed roda — então o seed nunca "vence" —
e o horário é fixo e plausível.

### Chaves das APIs externas

O catálogo externo precisa de chave. **Sem chave a aplicação sobe normalmente** —
`/api/catalog/search` responde `503` explicando o que falta, em vez de quebrar.

| Variável | Onde obter |
|----------|-----------|
| `TMDB_API_KEY` | themoviedb.org/settings/api → "API Key (v3 auth)" |
| `TICKETMASTER_API_KEY` | developer.ticketmaster.com → criar app → "Consumer Key" |

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
| GET | `/api/events` | público | Vitrine: eventos publicados. Filtros `?q=` (título/local) e `?kind=` |
| GET | `/api/events/{id}` | público | Detalhe de evento publicado (rascunho devolve 404) |
| GET | `/api/catalog/search` | organizador | Busca no catálogo externo. `?source=TMDB\|TICKETMASTER&q=` |
| GET/POST | `/api/organizer/events` | organizador | Lista/cria os eventos **do organizador logado** |
| GET/PATCH/DELETE | `/api/organizer/events/{id}` | organizador | Só os próprios (id alheio devolve 404) |
| GET | `/api/events/{id}/seats` | público | Mapa de assentos (livre/vendido, sem dizer de quem) |
| GET/POST | `/api/organizer/events/{id}/seats` | organizador | Lê e (re)gera o mapa por seções |
| GET/POST | `/api/reservations` | cliente | Lista/cria reserva (já segura o estoque) |
| POST | `/api/reservations/{id}/pay` | cliente | Pagamento simulado; emite os ingressos |
| POST | `/api/reservations/{id}/cancel` | cliente | Cancela e devolve ao estoque |
| GET | `/api/tickets` | cliente | Carteira de ingressos, com o payload do QR |
| GET | `/api/shared/{share_token}` | público | Ingresso compartilhado, **somente leitura** |
| GET | `/api/gate/events` | portaria | Eventos selecionáveis na tela da portaria |
| GET | `/api/organizer/events/{id}/sales` | organizador | Receita, ingressos validados e lista de compradores |
| POST | `/api/gate/validate` | portaria | Valida: `VALID`, `INVALID`, `ALREADY_USED`, `WRONG_EVENT` |

**Pagamento simulado:** não há transação financeira. A regra é determinística —
pedidos de **6 ingressos ou mais são recusados** e o estoque volta na hora.

Determinística de propósito: dá para demonstrar o caminho de falha ao vivo, o
que uma recusa aleatória não permitiria. E o limite fica **abaixo** do máximo do
seletor de quantidade (8), para que a recusa seja alcançável pela interface —
o enunciado pede a confirmação **e** a recusa no front, não só no servidor.

### Testes

#### Backend — 105 testes

```bash
cd backend && python manage.py test
```

| App | Testes | O que cobre |
|-----|--------|-------------|
| `ticketing` | 36 | No-double-sell (pista e assento), QR, portaria, vendas |
| `accounts` | 27 | Login por e-mail, papel no JWT, permissões por papel |
| `events` | 42 | Vitrine, painel, catálogo externo, mapa de assentos |

Destaque para **três testes de concorrência**: dois sobem 10 threads disputando
3 vagas de pista — um com `select_for_update` e outro sem, para demonstrar a
race condition que o lock elimina — e um terceiro põe 10 threads disputando a
**mesma poltrona**. O segundo imprime o resultado na saída:

```
[sem lock] 10 clientes aprovados para 3 vagas; sold_count gravado: 2
[com lock] exatamente 3 aprovados, contador exato.
```

O `2` não é engano: sem o lock houve oversell **e** _lost update_ — as threads
leram o mesmo contador e sobrescreveram umas às outras, deixando o banco abaixo
do real.

Os testes de catálogo **não tocam a rede**: `requests.get` é substituído por um
dublê. Teste que depende de API de terceiro falha quando o terceiro cai, gasta
cota a cada execução e não roda sem chave — deixa de ser teste e vira
monitoramento.

#### Ponta a ponta — 32 testes

```bash
# em um terminal — THROTTLE_AUTH_RATE afrouxado porque a suíte loga muitas
# vezes do MESMO IP e bateria no limite de força bruta (10/min em produção)
cd backend && python manage.py seed
THROTTLE_AUTH_RATE=1000/min python manage.py runserver

# em outro
cd frontend && npm run test:e2e
```

Playwright contra a aplicação real: Next servindo o front, Django falando com o
Postgres. **Nada é dublado** — o que estes testes provam é justamente a costura
entre as pontas, e um mock de `/api/reservations` passaria mesmo com o backend
recusando a reserva.

Cobrem vitrine, compra (confirmação **e** recusa), mapa de assentos, portaria,
painel do organizador e sessão (incluindo a renovação automática do token). A
tela da portaria roda **também num viewport de celular**, que é onde ela é usada
de verdade. `npm run test:e2e:ui` abre o modo interativo.

#### Leitura do QR pela câmera

Fica fora da suíte automática: navegador headless não tem câmera. A verificação
foi feita alimentando o Chromium com uma **câmera virtual** — um vídeo `.y4m`
montado a partir de um QR real capturado da própria aplicação — e está
documentada passo a passo em
[`frontend/e2e/manual/verificar-camera.md`](frontend/e2e/manual/verificar-camera.md),
para ser reproduzível em vez de ficar na palavra de quem escreveu.

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

**A aplicação está publicada e o fluxo inteiro funciona no ar:**

| Ambiente | URL |
|----------|-----|
| Front (Vercel) | https://verzel-eventos-ingressos.vercel.app |
| Back (Render) | https://ingressos-api.onrender.com |
| Docs da API | https://ingressos-api.onrender.com/api/docs |

Para percorrer sem montar nada: entre em `/entrar` e clique numa das contas de
demonstração (a senha já vem preenchida), compre um ingresso, abra o QR em
`/minha-conta`, e valide o código em `/portaria` com a conta de portaria.

> A Render no plano free hiberna após ~15 min sem tráfego. A primeira
> requisição depois disso leva ~50s — medido, não estimado. Não é bug, é o
> cold start. Se a vitrine demorar a preencher, é isso.

### Reproduzir o deploy

- **Front (Vercel):** importe o repo e defina **Root Directory = `frontend`**.
  Variável de ambiente: `NEXT_PUBLIC_API_URL` = URL da API na Render.
- **Back (Render):** New → Blueprint, apontando para este repo. O
  [`render.yaml`](render.yaml) descreve o web service + o Postgres.
  A Render pede `CORS_ALLOWED_ORIGINS` (URL da Vercel), `TMDB_API_KEY` e
  `TICKETMASTER_API_KEY`; `SECRET_KEY` e `TICKET_SIGNING_KEY` ela mesma gera.

> **Atenção em serviço já existente:** variável marcada como `sync: false` no
> `render.yaml` só é perguntada quando o blueprint é criado. Ao adicionar uma
> nova depois, é preciso preenchê-la à mão em Environment — senão ela sobe
> vazia. Foi o que aconteceu com `TICKETMASTER_API_KEY`.

O build da Render roda [`backend/build.sh`](backend/build.sh): instala
dependências, junta os estáticos, aplica as migrations e roda o seed. Migrations
no **build** e não no start, porque no start várias instâncias tentariam migrar
em paralelo.

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

**Ferramenta:** Claude Code (Opus), em pair programming.

**Como trabalhei:** a IA escreveu a maior parte do código; eu dirigi as decisões
de projeto e revisei o que entrou. Em cada ponto de decisão eu recebia as opções
com os trade-offs e escolhia — as escolhas estão registradas uma a uma em
[`docs/DECISIONS.md`](docs/DECISIONS.md), com a alternativa que descartei e o
porquê. Não é um log gerado no fim: foi preenchido enquanto decidia.

**Onde a IA escreveu:** scaffold do Django e do Next, configuração (settings,
CORS, JWT, WhiteNoise), `render.yaml`, comando de seed, models, clientes das APIs
externas, serializers, views, lógica de reserva/QR/portaria e todas as telas.

**O que eu fiz sem IA:** as decisões de arquitetura e modelagem listadas no
`DECISIONS.md` — contador vs. contagem para o estoque, constraint no banco além
do lock, unicidade do par `(source, external_id)`, separação dos serializers por
audiência, e a escolha de suportar as duas APIs externas em vez de uma.

**Verificação:** não aceitei código sem exercitá-lo. Cada camada foi testada
contra o Postgres real e num navegador real antes de virar commit — incluindo a
`CheckConstraint` (provei que o banco recusa `sold_count > capacity`), as
permissões por papel (403/401/404 nos casos certos), a tentativa de forjar
`organizer` no corpo do request, e o fluxo inteiro de compra e validação via
Playwright. **Cinco bugs** encontrados assim estão documentados na seção "Bugs"
do `DECISIONS.md`, com sintoma, método de diagnóstico, causa e correção — entre
eles uma hidratação abortada que deixava duas telas sem JavaScript e um erro
síncrono que derrubava a página da portaria justamente quando a câmera falhava.

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

Todos os requisitos obrigatórios estão implementados e no ar. O que segue são
limitações conhecidas, declaradas de propósito.

- **O mapa de assentos não é em tempo real.** O opcional do enunciado cita
  "mapa de assentos em tempo real"; aqui o mapa carrega ao abrir a página e
  recarrega após cada tentativa de reserva — não há WebSocket nem _polling_. Se
  outra pessoa comprar a poltrona enquanto sua tela está aberta, você descobre
  ao tentar reservar: recebe a mensagem, a seleção é limpa e o mapa é
  atualizado. **A falta é de conforto, não de correção** — a reserva trava a
  linha do assento no banco, então duas pessoas nunca levam o mesmo lugar.
  Ficou de fora por escolha de escopo.

- **A leitura do QR pela câmera não está na suíte automática.** Navegador
  headless não tem câmera. Ela *foi* verificada, alimentando o Chromium com uma
  câmera virtual montada a partir de um QR real da própria aplicação — o
  procedimento está em
  [`frontend/e2e/manual/verificar-camera.md`](frontend/e2e/manual/verificar-camera.md)
  para ser reproduzível. Na suíte automática ficam a digitação manual e o
  comportamento quando a câmera falha.

- **Cobertura da Ticketmaster no Brasil é fraca.** A Discovery API é
  majoritariamente EUA/Europa, então buscar por cidade brasileira costuma voltar
  vazio. Não é bug de integração — é o catálogo deles. Para demonstrar, busque
  termos internacionais (`coldplay`, `eagles`, `nba`). O TMDb, esse sim, responde
  em português e cobre bem o catálogo de filmes.

- **Sem chave de API, o catálogo externo responde 503 explicando** em vez de
  quebrar. O resto da aplicação (vitrine, compra, QR, portaria) segue
  funcionando, porque os eventos publicados guardam uma cópia dos dados e não
  consultam a API externa a cada request. Em produção as duas chaves estão
  configuradas.

- **O histórico de commits está concentrado.** O enunciado pede commits ao longo
  da semana, e a maior parte deste projeto foi feita em poucas sessões longas.
  As mensagens registram o processo — cada correção explica sintoma, causa e
  decisão — mas as datas não espelham sete dias de trabalho espaçado.
