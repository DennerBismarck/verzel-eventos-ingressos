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
| 14 | Suportar **as duas** APIs externas (TMDb + Ticketmaster) | O enunciado permite as duas. Com dois provedores atrás da mesma interface, a abstração fica *provada* — uma implementação só não demonstra que a costura funciona | Só TMDb (menos trabalho, mas o desacoplamento vira promessa em vez de fato) |
| 15 | Catálogo devolve **sugestão**, não evento pronto | Filme não tem local nem horário; show tem. Em vez de inventar dado para o filme, `venue`/`starts_at` são opcionais no catálogo e obrigatórios no Event — quem preenche é o organizador | Forçar o mesmo formato nos dois (obrigaria a fabricar data falsa para filmes) |
| 16 | Backend faz **proxy** da API externa | A chave fica só no servidor. Chamada direta do front colocaria a chave no bundle JavaScript, legível por qualquer visitante | Front chamar TMDb direto (mais rápido, vaza a chave) |
| 17 | `sold_count` como contador no Event + `CheckConstraint` | O lock do no-double-sell já é na linha do Event; contar Reservations exigiria travar outra tabela. O contador permite a constraint no banco como 2ª camada | Contar `Reservation` a cada leitura (sempre correto, mais caro, e impossibilita a constraint) |
| 18 | **Sem** `unique(source, external_id)` — só índice | O mesmo filme pode virar dois eventos (sessões em datas diferentes). Unicidade proibiria um caso legítimo do negócio | `unique_together` (trava demais) |
| 19 | `price` como `DecimalField`, nunca `Float` | Float é binário: `0.10` não tem representação exata e somas acumulam erro em centavos | `FloatField` |
| 20 | Dois serializers para Event (público / organizador) | O público não vê `sold_count` nem dados do organizador. Um serializer só, escondendo campos por `if`, é onde vaza informação por descuido | Serializer único com lógica condicional |
| 21 | Autorização do organizador via `get_queryset`, não `if` na view | `Event.objects.filter(organizer=request.user)` faz o objeto alheio simplesmente não existir → 404. Um 403 confirmaria que o evento existe | Checar `obj.organizer == user` depois de buscar (vaza existência via 403) |
| 22 | Erro do catálogo externo vira **502**, chave ausente vira **503** | Falha de terceiro não pode virar 500 nosso. Os códigos separam "eles caíram" de "falta configurar aqui" | Deixar a exceção subir como 500 (mistura culpa nossa com culpa deles) |
| 23 | `timeout=6s` em toda chamada externa + cache de 15 min | Sem timeout, uma API lenta prende o worker do gunicorn até morrer — um terceiro derruba a nossa API. O cache poupa cota de requisições | Chamada sem timeout (padrão do `requests` é esperar para sempre) |
| 24 | Reserva **segura o estoque antes** do pagamento | Reservar depois de pagar abriria janela em que dois clientes pagam pelo mesmo lugar e um precisa ser estornado. Segurando antes, o perdedor descobre na hora — quando ainda consegue escolher outra coisa | Só descontar no pagamento confirmado (mais simples, gera estorno) |
| 25 | Pagamento simulado com regra **determinística** (≥10 ingressos → recusa) | Dá para demonstrar o caminho de falha ao vivo na defesa | Recusa aleatória (demo irreprodutível — péssimo numa entrevista) |
| 26 | `Payment` como model próprio, não campo em `Reservation` | Registra a TENTATIVA: uma reserva recusada deixa rastro com data e motivo | Campo `paid=True/False` (perde o histórico da tentativa) |
| 27 | Assinatura do QR **não** é coluna | Derivável de `code + TICKET_SIGNING_KEY` a qualquer momento. Guardar duplicaria estado — e um dump vazado entregaria QRs prontos | Coluna `signature` (redundante e mais perigosa em vazamento) |
| 28 | `share_token` separado do `code` | Compartilhar a visualização não é ceder a entrada. O link mostra o ingresso mas não revela o que valida na portaria | Um identificador só (mandar no WhatsApp entregaria a entrada) |
| 29 | `total_price` congelado na reserva | Reajuste do organizador não pode alterar retroativamente quem já reservou | Calcular do preço do evento na hora de exibir |
| 30 | Regras em `services.py`, fora das views | A mesma regra vale para API, admin e teste — e o teste de concorrência roda sem subir servidor | Lógica dentro da view (intestável em concorrência) |
| 31 | Portaria responde **HTTP 200** mesmo para ingresso inválido | A portaria perguntou e foi respondida. "Inválido" é o conteúdo, não falha da requisição; um 4xx faria o front mostrar "erro de rede" | 4xx por resultado negativo |
| 32 | Estoque acabado → **409**, não 400 | O pedido está bem formado; mudou o estado do mundo. Com outra quantidade o mesmo pedido funciona | 400 (diz "você errou" quando o cliente não errou) |
| 33 | Visual copiado de Sympla/Eventim/Ingresso.com, não "genérico" | Grid denso de pôsteres, bloco de data, laranja no CTA. Fugir de gradiente roxo, hero centralizado e `rounded-3xl` — o enunciado pede explicitamente para fugir de AI slop | Tema escuro com gradiente (bonito em print, não parece bilheteria) |
| 34 | Pôster em proporção **2:3** fixa | É o formato que o TMDb devolve. Deixar o navegador decidir causaria _layout shift_ quando a imagem chegasse | `height: auto` |
| 35 | `<img>` em vez de `next/image` | As imagens vêm de hosts externos e já chegam no tamanho certo; o otimizador da Vercel cobraria transformação sem ganho | `next/image` (custo sem benefício aqui) |
| 36 | Vitrine renderizada no **cliente**, não no servidor | SSR daria SEO melhor, mas exigiria o backend acordado a cada request — e a Render free hiberna, o que faria a home levar 50s | SSR/ISR na home |
| 37 | Token em `localStorage` | O front (Vercel) e a API (Render) estão em domínios diferentes; cookie HttpOnly cross-site exigiria `SameSite=None` e domínio compartilhado. **Custo assumido:** XSS levaria o token — mitigado por access token de 60 min | Cookie HttpOnly (não viável neste deploy) |
| 38 | Cartazes do seed **fixos** no código, não buscados na hora | O seed roda no build da Render; não pode depender de a API externa estar de pé nem gastar cota a cada deploy | Buscar no TMDb durante o seed |
| 39 | Recusa de pagamento devolve **402**, tratada como resultado e não erro | O cliente precisa saber que não tem ingresso. Um 200 com lista vazia seria fácil de ignorar por engano no front | 200 sempre |
| 40 | `sold_count` do evento sobe **também** em lugar marcado | A verdade sobre QUAL poltrona foi vendida está nas linhas de `Seat`; o contador existe para a vitrine responder "quantos restam" sem contar assentos a cada card, e para a `CheckConstraint` valer nos dois tipos | Derivar `available` contando `Seat` (uma query por evento na listagem = N+1) |
| 41 | Mapa é gerado por **seções** (nome, nº de filas, lugares por fila, preço) | O organizador descreve a sala em 4 campos em vez de cadastrar 80 poltronas. Os rótulos A, B, C… são gerados pelo sistema | Cadastro poltrona a poltrona; ou pedir a lista de filas digitada ("A,B,C,D,E") |
| 42 | Refazer o mapa é **bloqueado** assim que houver assento vendido | Recriar apagaria a linha que um ingresso emitido aponta. O `PROTECT` do `Ticket.seat` barraria de qualquer forma, mas com erro de banco em vez de explicação | Permitir sempre; ou versionar mapas (complexidade sem demanda) |
| 43 | Evento com lugar marcado nasce em **rascunho** | Publicar antes de existir mapa colocaria na vitrine um teatro sem poltrona nenhuma. Vira publicado só depois do mapa criado | Publicar direto e torcer para o organizador montar o mapa em seguida |
| 44 | Mapa público mostra situação, **nunca o comprador** | Saber que a C4 está ocupada é necessário para escolher; saber de quem, não | Devolver a reserva junto (vazaria quem comprou o quê) |
| 45 | Rota do mapa **sem paginação** | Paginar o mapa desenharia meia sala na tela | Paginação padrão do DRF |
| 46 | Sessão vive **fora do React** (`session.ts` + `useSyncExternalStore`) | Quem precisa trocar o token é a `api()`, no meio de uma requisição. Com a verdade num estado de componente, qualquer chamador que já tivesse copiado o token seguiria com o valor velho depois da renovação | Estado no contexto e passar `token` por parâmetro (impede renovar de forma transparente) |
| 47 | Renovação **compartilhada** por promessa em voo | Telas disparam chamadas em paralelo; sem isso seriam N refresh simultâneos e os últimos usariam um token já consumido | Renovar por requisição |
| 48 | Renova **uma vez** e só; se falhar, limpa a sessão | Insistir viraria laço infinito com o servidor recusando | Tentar N vezes com espera progressiva (complexidade sem ganho aqui) |
| 49 | Sessão malformada é **descartada** na leitura | Um objeto sem `full_name` derrubava a árvore React inteira. "Deslogado" é um estado do qual o usuário sai sozinho; tela branca não | Confiar no que está no storage |
| 50 | Receita conta **só reserva paga** | Pendente ainda pode ser recusada; recusada e cancelada nunca entraram. Somar tudo inflaria o faturamento do organizador | Somar todas as reservas |
| 51 | Dinheiro trafega como **string** também fora dos serializers | `Decimal` solto num dicionário de resposta é serializado como número JSON e vira float no JavaScript — o problema que `DecimalField` evita no resto da API | Devolver o `Decimal` cru |
| 52 | E2E contra a aplicação **real**, sem mock de API | O que estes testes provam é a costura entre as pontas; um mock de `/api/reservations` passaria mesmo com o backend recusando | Mockar a rede no Playwright (rápido e inútil aqui) |
| 53 | E2E com **um worker só** | Os testes compram do mesmo seed e disputam o mesmo estoque; em paralelo um veria o efeito do outro e a falha seria irreprodutível | `fullyParallel` (rápido, instável) |
| 54 | Rate limit com **escopos separados** por risco | auth 10/min (força bruta), gate 120/min (a portaria valida em rajada e apertar atrapalharia o uso legítimo), catalog 30/min (cada chamada gasta cota nossa no terceiro) | Um limite único para tudo (ou sufoca a portaria, ou é inútil no login) |
| 55 | Limite de auth **configurável**, com padrão estrito | Limite de taxa é configuração de ambiente. Sem a variável, o throttle derruba a suíte E2E e a reação natural seria afrouxar a produção — o pior desfecho | Valor fixo no código |
| 56 | Rotação de refresh + blacklist | Um refresh vazado só serve até a vítima usar o dela; e o logout passa a revogar de verdade, em vez de apagar do navegador e torcer | Refresh estático de 7 dias |
| 57 | Reserva expira em **10 minutos** | Sem prazo, quem fecha a aba trava o lugar para sempre. É o que toda bilheteria faz | Segurar até alguém cancelar na mão (ninguém cancela) |
| 58 | Expiração roda **na hora de reservar**, não só em cron | É o momento em que o estoque importa. Funciona sem agendador — e a Render free não tem cron. O comando existe para quem tiver, mas não é pré-requisito de correção | Depender só de cron (o sistema fica errado onde não há um) |
| 59 | `expires_at` derivado de `created_at` | O prazo é regra do sistema, não dado do registro. Coluna duplicaria estado e o banco poderia discordar da constante | Coluna `expires_at` |
| 60 | Otimizar só o que foi **medido** | 17 queries em `/reservations` viraram 5; a vitrine já estava em 2 e não foi tocada | Otimizar por intuição (mexe no que já estava bom) |
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

### Dia 1 — POST devolvendo 500 em vez de 403

**Sintoma:** `POST /api/organizer/events` com token de **cliente** retornava 500.
Esperado: 403. O `GET` na mesma rota retornava 301.

**Como isolei:** o traceback não vinha da minha view — vinha de
`django/middleware/common.py`. A view nem chegou a rodar, então a permission
class não era a culpada.

**Causa:** o `DefaultRouter` do DRF gera rotas **com barra final**
(`/organizer/events/`), mas o resto da API é sem (`/api/events`,
`/api/auth/login`). O `APPEND_SLASH` do Django tenta redirecionar `…/events`
para `…/events/`; num GET isso é um 301, mas num **POST** ele não consegue
redirecionar preservando o corpo do request — então levanta `RuntimeError`.

**Correção:** `DefaultRouter(trailing_slash=False)`.

**Aprendizado:** inconsistência de rota não é questão de estilo. Metade da API
com barra e metade sem transforma um 403 legítimo num 500, e um 500 mascara
completamente o erro real de permissão. Ler *de onde* vem o traceback (meu
código ou middleware) foi o que encurtou o diagnóstico.

### Dia 2 — `FOR UPDATE cannot be applied to the nullable side of an outer join`

**Sintoma:** 5 testes da portaria quebrando com esse erro do Postgres.

**Causa:** em `validate_ticket` eu fazia
`Ticket.objects.select_for_update().select_related("event", "customer", "seat")`.
Como `seat` é nullable, o `select_related` gera um LEFT OUTER JOIN — e o
Postgres recusa aplicar `FOR UPDATE` ao lado nulável de um outer join, porque
não existe linha para travar quando o assento é nulo.

**Correção:** `select_for_update(of=("self",))`, que trava só a linha do
ingresso.

**O detalhe que importa:** o erro não era só sintático. Travar `event` e
`customer` para validar uma entrada **bloquearia a venda do evento inteiro toda
vez que alguém passasse na portaria**. O Postgres me obrigou a escolher o
escopo do lock — e o escopo certo era o mais estreito.

### Dia 2 — teste que passava sem testar nada

`test_assinatura_adulterada_e_rejeitada` fazia `payload[:-1] + "0"` para
corromper a assinatura. Quando a assinatura já terminava em `"0"`, o "ataque"
era idêntico ao original e o teste passava sem exercitar nada. Corrigido para
trocar por um caractere garantidamente diferente.

**Aprendizado:** teste verde não é prova de nada se o cenário que ele monta não
é o cenário que ele diz montar.

### Dia 3 — hidratação abortada nas rotas dinâmicas (React #418)

**Sintoma:** só `/eventos/[id]` e `/ingresso/[token]` — justamente as rotas
renderizadas sob demanda — quebravam com "Minified React error #418".

**Como isolei:** rodei as 8 rotas num navegador de verdade registrando
`pageerror`. As 8 estáticas passavam, as 2 dinâmicas falhavam → o problema
estava no **layout compartilhado**, não nas páginas. Confirmei com `curl`: em
rota estática o HTML do servidor traz o *fallback* do `<Suspense>`; em rota
dinâmica traz o `<header>` inteiro.

**Causa:** o cabeçalho chamava `useSearchParams()` dentro de um `<Suspense>`.
Nas rotas dinâmicas o servidor renderiza o componente completo, mas o cliente
começa pelo fallback — servidor e cliente divergem e o React aborta a
hidratação (a página vira HTML morto, sem JavaScript).

**Correção:** ler o `?q=` de `window.location.search` dentro de um `useEffect`.
Efeito não roda no servidor, então o primeiro render é idêntico dos dois lados.

**Aprendizado:** hidratação quebrada não aparece como tela de erro — aparece
como "o botão não funciona". Sem abrir o console num navegador real, isso
chegaria intacto na entrega.

### Dia 3 — a portaria derrubava a própria página

**Sintoma:** a API respondia `200 {"result":"INVALID"}` e a tela mostrava
"This page couldn't load".

**Causa:** quando a câmera não abre (permissão negada, dispositivo sem câmera),
o `stop()` da `html5-qrcode` **lança de forma síncrona** — não é Promise
rejeitada. O `.catch()` que eu tinha posto nunca era chamado, o erro subia e
matava a árvore React inteira.

**Correção:** flag `rodando` para só parar o que começou, e `try/catch`
envolvendo a chamada — não `.catch()`.

**Aprendizado:** `.catch()` só pega rejeição de Promise. Função que devolve
Promise mas valida argumento antes ainda pode lançar sincronamente — e o
usuário afetado é exatamente aquele com a câmera bloqueada, que é quem mais
precisava da digitação manual funcionar.

### Dia 4 — a chave de API estava indo para o log

**Sintoma:** ao escrever o teste de erro HTTP do catálogo, o console cuspiu
`requests.exceptions.HTTPError: 401 para ...api_key=chave-de-teste`.

**Causa:** os dois provedores autenticam pela **query string** (`?api_key=` no
TMDb, `?apikey=` na Ticketmaster). No `except` eu usava `logger.exception`, que
despeja o traceback inteiro — e a mensagem do `requests` carrega a URL
completa. Em produção isso escreveria a chave real nos logs da Render, legível
por qualquer pessoa com acesso ao dashboard.

**Correção:** `logger.error` registrando só tipo da exceção e status HTTP. Mais
um teste com `assertLogs` verificando as duas pontas: o segredo não aparece, e
o diagnóstico continua aparecendo.

**Aprendizado:** eu tinha escrito, no comentário original, que a mensagem que
sobe é genérica "porque a URL contém a api_key". Eu sabia do risco e mesmo
assim deixei o traceback ir inteiro para o log — proteger a resposta e esquecer
o log é meio caminho. Segredo em query string vaza por todo lugar que registra
URL: log de aplicação, log de proxy, histórico de navegador, referer.

### Dia 4 — o teste que media o artifício, não o sistema

Ao cobrir permissões, escrevi um teste afirmando que usuário desativado é
barrado. Ele **falhou com 200** — e a primeira leitura foi "achei uma falha de
segurança".

Não era. O teste usava `force_authenticate`, que **pula a camada de
autenticação** — exatamente onde o simplejwt recusa token de conta inativa. O
caminho real nunca esteve aberto, e reescrevi o teste emitindo um token de
verdade para provar isso.

Ainda assim somei `is_active` explícito à `HasRole`: a permission class não deve
assumir *quem* autenticou. Trocar o backend ou somar uma sessão de admin
reabriria a porta. O segundo teste chama a permissão direto, sem autenticador.

**Aprendizado:** quando um teste falha, a primeira pergunta é se ele está
medindo o que diz medir. Atalho de teste que contorna uma camada também
contorna as garantias daquela camada.

### Dia 5 — a vitrine mentiria em evento de lugar marcado

**Sintoma:** nenhum, até existir tela. É o tipo de bug que só aparece quando o
caminho é percorrido de ponta a ponta.

**Causa:** `_reserve_seats` marcava as poltronas como vendidas mas nunca mexia
no `sold_count` do evento, e `_release_stock` devolvia o assento e **retornava
antes** de decrementar o contador.

Como `available` lê o contador, um teatro com a sala inteira vendida seguiria
anunciando todos os lugares livres — e um cancelamento deixaria o contador
inflado para sempre.

**Por que passou despercebido:** não havia rota para criar assentos. O tipo
`SEATED` existia no banco, tinha lógica de reserva e até teste de lock, mas era
inalcançável pela aplicação. Código testado em unidade e nunca exercitado
inteiro.

**Aprendizado:** cobertura de teste não substitui percorrer o fluxo. Os dois
lados desse bug estavam em funções testadas.

### Dia 5 — recusar 100 mil objetos depois de construí-los

O gerador de mapa validava os limites **depois** de montar a lista de `Seat`.
Com 20 seções cheias, seriam 100 mil objetos alocados em memória só para
responder "não". Reescrito em duas passadas: a primeira valida a forma e
**conta**, a segunda constrói. Somar é barato; instanciar não.

Foi o teste do mapa gigante que expôs isso — e o mesmo teste também mostrou que
meu limite estava em `> 5000` quando 50 filas × 100 lugares dão exatamente 5000.

### Dia 6 — a chave de API no log (segunda parte da mesma lição)

Já registrado acima. Vale ligar com o achado do dia 6: **o Decimal cru na
resposta de vendas** virava número JSON, ou seja, float no cliente. São o mesmo
erro em roupas diferentes — proteger o caminho principal e esquecer a borda. O
`DecimalField` cuidava de todos os serializers; o dicionário montado à mão
escapou.

### Dia 6 — a suíte de E2E encontrou mais bug em si mesma do que no produto

Das 28 primeiras execuções, **todas** falharam: o CORS não liberava a porta que
eu escolhi para os testes. Depois disso, 8 falhas — e 7 eram defeito do teste,
não do produto:

- `.count()` **não reexecuta**. Três testes liam a contagem antes de a API
  responder e viam `0`. `toHaveCount` e `expect.poll` esperam; `count()` não.
- `getByRole("alert")` casava também com o `__next-route-announcer__` que o
  Next injeta.
- `getByText("Titular")` casava com o `<dt>` e com o parágrafo que menciona
  "titular".
- `getByRole("heading", { name: "Esgotado" })` nunca casaria: o título do aviso
  é um `<p>`. O teste acusaria o app de estar errado.
- `localStorage` em `about:blank` levanta `SecurityError`.
- E um teste chamado *"pagamento de 10 ou mais é recusado"* que não testava
  recusa nenhuma — a interface limita a compra a 8, então aquele caminho é
  inalcançável pela tela.

**A oitava era real** e valeu a suíte inteira: uma sessão malformada no
`localStorage` derrubava a árvore React e deixava tela branca.

**Aprendizado:** teste novo mente mais que código novo. Antes de acreditar numa
falha, vale perguntar se o teste mede o que diz medir — foi a mesma pergunta que
salvou o caso do `force_authenticate` no dia 4.

### Dia 7 — a correção do preço apagou a ordenação da vitrine

O `com_preco_inicial()` nasceu para matar o N+1 do preço em evento de lugar
marcado: anota `Min("seats__price")`. Como `seats` é relação múltipla, o Django
monta um `GROUP BY` — e nesse caso ele **descarta o `Meta.ordering`**, senão a
coluna da ordenação teria de entrar no agrupamento e mudaria o resultado.

Resultado: desde aquela correção, a consulta da vitrine saía **sem `ORDER BY`
nenhum**. E parecia certa. O Postgres devolvia na ordem de inserção do seed,
que por acaso é cronológica. Nada disso é garantia: sem `ORDER BY` o plano pode
mudar com o volume, e numa lista **paginada** isso faz a página 2 repetir
linhas da 1 e sumir com outras.

Escrevi dois testes, porque um só passaria por sorte: um afirma a ordem
cronológica na vitrine; o outro olha o SQL e exige que exista `ORDER BY`. Sem o
segundo, o primeiro passaria por acidente sempre que o banco devolvesse na
ordem de inserção — que é exatamente o que estava acontecendo.

**Aprendizado:** otimização mexe em mais coisa do que o nome sugere. Um
`annotate()` não é só "uma coluna a mais": ele reescreve a consulta.

### Dia 7 — a vitrine anunciava sessão que já tinha acontecido

O `create_reservation` recusa evento começado desde o primeiro dia ("Este
evento já começou"). A vitrine, porém, filtrava só por `status=PUBLISHED`. Um
evento cuja data passasse continuava em "Em cartaz", com botão de comprar, até
o cliente percorrer o fluxo inteiro e levar o erro no fim.

Nunca apareceu porque o seed só tinha evento futuro. Foi ao adicionar as
sessões passadas — necessárias para a aba "Já aconteceram" do painel — que o
bug ficou visível na tela.

A página do evento **continua existindo** por link direto: quem foi à sessão
ainda tem o link em "Meus ingressos", e devolver 404 apagaria a página do
próprio evento a que a pessoa foi. Sumir da vitrine e deixar de existir são
coisas diferentes.

**Aprendizado:** dado de teste que só cobre o caminho feliz esconde bug de
borda. O seed é código: se ele só produz eventos futuros, a metade do sistema
que lida com o passado nunca é exercitada.

### Dia 7 — o mapa que eu decidi não embutir

A página do evento pedia um mapa do local. A resposta óbvia é um iframe do
Google Maps. Não embuti, por três razões que valem mais que a conveniência:

1. O iframe carrega scripts e cookies de terceiro em **toda** visita, inclusive
   a de quem só queria ver o preço. Entrega o passo do visitante a um terceiro
   antes de ele pedir.
2. O `venue` é texto livre digitado pelo organizador ("Cinemark Eldorado, São
   Paulo"). O pino cairia no lugar errado com frequência — e um mapa errado é
   pior que mapa nenhum, porque ele parece certo.
3. Um mapa embutido custa cota de API por carregamento, num plano gratuito.

O link resolve o mesmo problema real (chegar lá) sem nenhum dos três. É menos
vistoso e mais honesto sobre o que o dado permite.

### Dia 7 — o limite de login cobrava do usuário certo

A suíte de E2E começou a levar 429 no login. O primeiro impulso é afrouxar o
limite; o correto era perguntar o que ele estava contando.

Estava contando **acerto junto com erro**. Força bruta é, por definição, uma
sequência de erros — quem acerta a senha não está adivinhando. Cobrar cota do
acerto punia o uso legítimo (a pessoa que entra no celular, no tablet e no
computador gastava o mesmo orçamento do atacante) sem tirar nada do atacante,
que erra de qualquer jeito.

Agora o `allow_request` só CONSULTA o histórico; quem grava é a view, depois de
saber que a credencial não prestava — é a única camada que conhece o desfecho.
Não abre brecha: quem já tem a senha certa não precisa de força bruta.

O teste que garante isso não é "25 logins certos passam". É o outro: **um
acerto no meio da rajada não devolve cota** ao atacante. Nove erros, um acerto,
e o décimo erro ainda fecha a porta.

**Aprendizado:** quando um controle de segurança atrapalha o uso legítimo, às
vezes o problema não é a intensidade — é a métrica.

### Dia 7 — a suíte de E2E falhou inteira, e a culpa não era do código

17 de 17 testes falharam com "elemento não encontrado". O motivo: o Next
bloqueia o acesso aos próprios chunks de `/_next/static` quando o host da
requisição não é aquele pelo qual o servidor de dev foi iniciado. Subi em
`localhost`, o Playwright abre em `127.0.0.1` — outra origem, para o Next.

O sintoma não se parece nada com a causa. Os chunks são bloqueados, o React
nunca hidrata, nenhuma chamada à API sai, e a tela fica eternamente no
esqueleto de carregamento. A suíte acusa a aplicação de estar quebrada.

Resolvido com `allowedDevOrigins` no `next.config.ts` — dev-only, não existe em
produção — em vez de mandar quem for rodar os testes lembrar de subir o
servidor no host certo.

## O que eu decidi NÃO construir

Tão importante quanto a lista acima. Cada item abaixo foi considerado, tem
justificativa técnica para ficar de fora, e a decisão é reversível.

### Fila de aplicação para disputa de assento

**A ideia:** enfileirar os pedidos por seção (Redis/Celery) para que duas
pessoas não conflitem ao escolher a mesma poltrona.

**Por que não:** *a fila já existe*. `SELECT ... FOR UPDATE` faz o Postgres
enfileirar o segundo cliente até o primeiro commitar — é uma fila, mantida pelo
banco, com garantia transacional. Uma fila de aplicação na frente disso não
muda o desfecho: adiciona um serviço, um worker, latência e três modos de falha
novos para produzir exatamente o mesmo resultado.

**O que uma fila resolveria de verdade:** *admissão sob carga extrema* — 50 mil
pessoas no minuto da abertura, onde o objetivo é proteger o banco de virar
gargalo e dar ao usuário uma posição na fila em vez de um timeout. Isso é
controle de tráfego, não de correção, e é um problema que este sistema não tem.

**O que eu construí no lugar:** o **prazo de reserva**. A intuição por trás do
pedido — "duas pessoas competindo pelo mesmo lugar" — apontava para um problema
real, mas não era o conflito simultâneo (esse o lock já resolve). Era o lugar
preso por uma reserva que ninguém pagou nem cancelou.

**Quando eu mudaria de ideia:** se a medição mostrasse fila de locks no
Postgres em pico, ou p99 de reserva subindo com concorrência.

### Arquitetura distribuída (serviços separados, mensageria, cache externo)

O sistema tem três entidades e um fluxo. Separar em serviços agora trocaria uma
transação que já é atômica por consistência eventual entre processos — e o
requisito central do desafio é justamente *não vender o mesmo lugar duas vezes*.
Seria trocar a garantia mais forte que eu tenho pela mais fraca, em nome de uma
escala que não existe.

### Cache de leitura na vitrine

A vitrine faz **2 queries** medidas. Cache aqui adicionaria invalidação — e um
evento esgotado aparecendo como disponível é pior que 2 queries.

---

### Checklist da defesa (marcar quando souber explicar de cabeça, em voz alta)
- [ ] Por que `select_for_update` resolve o double-sell — e o que acontece sem ele
- [ ] Por que HMAC impede forjar o QR (e por que só UUID não impediria)
- [ ] Por que a permissão é checada no backend e não só escondendo o botão no front
- [ ] Por que o default de permissão é `IsAuthenticated` e não `AllowAny`
- [ ] O que é o `refresh` token e por que o `access` é curto
