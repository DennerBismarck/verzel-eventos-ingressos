# Roteiro de defesa

> Não decore as frases. Entenda o mecanismo — a pergunta virá torta e você
> precisa reconstruir, não recitar. Cada seção tem: **o mecanismo**, **a
> pergunta que eles vão fazer**, e **a armadilha**.

---

## 1. `select_for_update` — o mesmo lugar não vendido 2x

**Código:** `backend/ticketing/services.py`, função `create_reservation`.

### O mecanismo

```python
with transaction.atomic():
    event = Event.objects.select_for_update().get(pk=event_id)
    if quantity > event.capacity - event.sold_count:
        raise ReservationError(...)
    event.sold_count += quantity
    event.save(update_fields=["sold_count"])
```

`select_for_update()` emite `SELECT ... FOR UPDATE`, que trava **aquela linha**
do evento até o fim da transação. Uma segunda transação que tente travar a mesma
linha **fica parada** naquela linha de código até a primeira commitar — e então
lê o `sold_count` já atualizado.

### A pergunta: "o que acontece sem isso?"

Duas requisições simultâneas leem `sold_count = 99` com `capacity = 100`. As
duas concluem "tem vaga". As duas gravam `100`. **Dois ingressos vendidos para o
mesmo lugar.**

O problema não é a leitura nem a escrita — é o **intervalo entre elas**. O lock
elimina o intervalo ao serializar quem passa por ali.

### Prove com o teste

`python manage.py test ticketing` roda 10 clientes concorrentes disputando 3
vagas. O teste imprime:

```
[sem lock] 10 clientes aprovados para 3 vagas; sold_count gravado: 2
[com lock] exatamente 3 aprovados, contador exato.
```

**Olhe o número 2.** Sem lock não houve só oversell — houve *lost update*: as
threads leram o mesmo valor e sobrescreveram umas às outras, e o contador ficou
**abaixo** do real. O banco passou a mentir nas duas direções.

### Armadilha 1: "por que dentro do `atomic()`?"

O lock dura até o **COMMIT**. Sem transação explícita, o autocommit do Django
encerra a transação na mesma hora e o lock morre antes de proteger qualquer
coisa. `select_for_update()` fora de `atomic()` levanta erro no Django.

### Armadilha 2: "a constraint no banco não bastaria?"

Não, e nem o lock sozinho basta. **Elas resolvem problemas diferentes:**

| | Protege contra | Falha se |
|---|---|---|
| `select_for_update` | concorrência (duas requisições ao mesmo tempo) | eu escrever a lógica errada |
| `CheckConstraint` | código errado, script manual, migration mal feita | — é a última linha |

A constraint sozinha transformaria a race num erro 500 feio para o cliente. O
lock sozinho não me protege de um bug meu. Uso as duas.

### Armadilha 3: "por que `update_fields=["sold_count"]`?"

Um `save()` completo reescreveria **todas** as colunas com os valores lidos no
início da transação. Se o organizador editasse o preço no meio, minha gravação
desfaria a edição dele em silêncio.

---

## 2. HMAC — o QR que não pode ser forjado

**Código:** `backend/ticketing/signing.py`.

### O mecanismo

O QR carrega `código.assinatura`, onde
`assinatura = HMAC-SHA256(TICKET_SIGNING_KEY, código)`. A portaria manda o
conteúdo lido; o servidor **recalcula** a assinatura e compara.

### A pergunta: "por que só o UUID não bastaria?"

Um UUID no QR é um *identificador*, não uma *prova*. Vaze ou adivinhe um código
e você tem uma entrada válida. Com HMAC, o código sem a assinatura correta não
vale nada — e a assinatura só pode ser produzida por quem tem a chave, que só o
servidor tem.

### Armadilha 1: "por que não `sha256(código)` puro?"

Porque **qualquer um** calcula `sha256` de qualquer coisa. Um hash puro não tem
segredo, então não prova origem. O que torna a assinatura infalsificável é a
**chave** que entra no cálculo. E HMAC é a construção correta para misturar chave
e mensagem — concatenar `chave + mensagem` num hash tem fraqueza conhecida
(*length-extension attack*).

### Armadilha 2: "por que a assinatura não é uma coluna?"

Ela é **derivável** de `code + chave` a qualquer momento. Guardar seria duplicar
estado — e um dump de banco vazado entregaria QRs prontos em vez de só códigos.

### Armadilha 3: "por que `hmac.compare_digest` e não `==`?"

A comparação normal de strings **sai no primeiro byte diferente**. O tempo dessa
saída revela quantos bytes você acertou; com medições repetidas dá para
descobrir a assinatura byte a byte (*timing attack*). `compare_digest` gasta
sempre o mesmo tempo.

### Armadilha 4: "por que chave separada da `SECRET_KEY`?"

Ciclos de vida diferentes. Rotacionar a `SECRET_KEY` do Django (que assina
sessões e JWT) não pode invalidar ingressos já emitidos e impressos.

---

## 3. Compartilhar por link — sem ceder a entrada

**Código:** `SharedTicketView` + `SharedTicketSerializer`.

### O mecanismo

Cada ingresso tem **dois** identificadores:

| Campo | Para quê | Quem vê |
|---|---|---|
| `code` | valida a entrada na portaria | só o dono |
| `share_token` | exibe o ingresso | quem tem o link |

A rota pública `/api/shared/{share_token}` devolve evento, local, nome e status
— e **não** devolve `code` nem `qr_payload`.

### A pergunta: "por que dois campos e não um?"

Porque compartilhar a *visualização* não é ceder o *acesso*. Se o link mostrasse
o código, mandar o ingresso para alguém no WhatsApp entregaria a entrada junto.
Ambos são uuid4 aleatórios: não dá para deduzir um a partir do outro, nem
enumerar incrementando id.

---

## 4. Portaria — o mesmo ingresso não validado 2x

**Código:** `validate_ticket` em `services.py`.

### O mecanismo — e a ordem importa

1. **Assinatura inválida** → `INVALID` *(antes de qualquer query: QR forjado é
   rejeitado sem custo de banco)*
2. Trava a linha do ingresso: `select_for_update(of=("self",))`
3. **Evento diferente do selecionado na portaria** → `WRONG_EVENT`
4. **`status == USED`** → `ALREADY_USED`, com quando e por quem
5. Senão → marca `USED`, grava `used_at`/`used_by` → `VALID`

### A pergunta: "por que lock aqui também?"

Dois leitores apontados para o mesmo QR ao mesmo tempo. Sem lock, ambos leem
`status = VALID`, ambos liberam a entrada. **É a mesma race do double-sell,
agora na porta.**

### Armadilha: "por que `of=("self",)`?"

Sem isso, o Postgres tentaria travar tudo que o `select_related` trouxe no JOIN
e recusaria com *"FOR UPDATE cannot be applied to the nullable side of an outer
join"* — porque `seat` é nullable e vira LEFT JOIN. **E travar o evento inteiro
para validar uma entrada seria errado de qualquer forma:** bloquearia as vendas
daquele evento cada vez que alguém passasse na portaria.

> Esse erro aconteceu de verdade e o teste pegou. É bom material: mostra que a
> escolha do lock não foi decorativa.

### Armadilha: "por que HTTP 200 mesmo em ingresso inválido?"

A portaria **perguntou** e foi respondida com sucesso. "Inválido" é o *conteúdo*
da resposta, não uma falha da requisição. Um 4xx faria o front tratar como erro
de rede e mostrar "algo deu errado" em vez de "ingresso já utilizado".

---

## 5. Perguntas gerais prováveis

**"Por que 409 e não 400 quando o estoque acaba?"**
O pedido está bem formado — o que mudou foi o **estado do mundo**. 400 diz "você
errou"; 409 diz "conflito com o estado atual". Com outra quantidade, o mesmo
pedido funciona.

**"Por que a reserva segura o estoque antes do pagamento?"**
Reservar depois de pagar abriria uma janela em que dois clientes pagam pelo mesmo
lugar e um precisa ser estornado. Segurando antes, o perdedor descobre **na
hora** — que é quando ele ainda consegue escolher outra coisa.

**"Por que `Decimal` e não `float` para dinheiro?"**
Float é binário: `0.10` não tem representação exata. Somar centavos acumula erro.

**"Por que a autorização do organizador está no `get_queryset`?"**
`Event.objects.filter(organizer=request.user)` faz o objeto alheio **não
existir** → 404. Um 403 confirmaria que aquele evento existe.

**"Você usou IA. O que exatamente é seu?"**
As decisões. Cada uma está em `DECISIONS.md` com a alternativa descartada e o
porquê — contador vs. contagem, constraint além do lock, dois serializers por
audiência, as duas APIs externas em vez de uma. E a verificação: nada entrou sem
ser exercitado contra o Postgres real. Dois bugs achados assim estão
documentados. *(Isto é uma resposta forte — o enunciado diz que usar IA bem é
valorizado. O que não se defende é não saber explicar.)*

---

## Antes da entrevista

- [ ] Rodar `python manage.py test ticketing` e **ler a saída do teste sem lock**
- [ ] Explicar em voz alta, sem olhar, por que lock e constraint não se substituem
- [ ] Explicar por que `sha256` puro não serviria no lugar do HMAC
- [ ] Saber apontar no código onde está cada uma das 4 partes acima
- [ ] Ter a demo pronta: reservar → pagar → QR → portaria → validar 2x
