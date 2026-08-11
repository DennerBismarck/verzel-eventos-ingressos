# Como eu conduzi a ferramenta

O enunciado pede para versionar os artefatos de contexto: *"ver como você
conduziu a ferramenta conta a seu favor"*. Este arquivo é isso — as instruções
que eu dei ao longo do projeto, transcritas como eu escrevi, com o que cada uma
provocou.

O prompt de abertura está em [`PROMPT-SESSAO.md`](PROMPT-SESSAO.md). O que segue
é a condução depois que o trabalho começou.

Não é um catálogo de prompts bonitos. É o registro de onde eu intervim, o que
eu recusei e o que eu mandei refazer.

---

## 1. Definir o padrão do histórico, antes de haver histórico

> "Continue e pode deixar o prompt-sessao dentro do commit. **Faça commits bem
> detalhados e atômicos**."

Dado cedo, e é o que faz o repositório ser auditável hoje: 60 commits em que
cada correção tem o seu, explicando sintoma, causa e decisão. Um pedido tardio
teria produzido mensagens inventadas depois do fato.

## 2. Recusar a estética de ferramenta

> "Sim, pode seguir. Mas **evite ter um design e front que pareça muito
> característico de IAs**. Se possível, copie um pouco de sites bons que já
> existem como ingresso.com, eventim.com e sympla.com."

O enunciado usa o termo *AI slop* — "aquela interface que sai pronta da
ferramenta e que você reconhece de longe". Eu apontei o problema e as
referências. Daí saíram a grade densa de pôsteres 2:3, o bloco de data sobre a
arte e o laranja restrito ao CTA, em vez do gradiente roxo com cards
arredondados que é a assinatura visual de projeto gerado.

## 3. Conferir a entrega contra o enunciado, não contra a própria opinião

> "Beleza, `Desafio-Elite-Dev-2026.pdf` desse pdf tá tudo pronto então?"

Pedi a verificação item a item contra o PDF. Foi assim que apareceu que a
**recusa do pagamento estava inalcançável pela interface**: o limite de recusa
era 10 e o seletor de quantidade parava em 8. O backend recusava corretamente,
mas o enunciado pede a recusa **no front-end**, e por ali não havia caminho.
Limite ajustado para 6, com teste E2E para não regredir.

## 4. Elevar o teto depois do escopo obrigatório

> "Uma coisa, eu gostaria de adicionar alguma **camada legal de senioridade**.
> Então podemos fazer um tratamento de **segurança de informação**, aplicação de
> **arquiteturas mais escaláveis**, **otimização**, aplicação de **filas por
> seção** para casos de conflito de duas pessoas escolherem o mesmo bilhete,
> etc."

Com o escopo do PDF pronto, essa foi a direção que definiu o resto do projeto.
Produziu: rate limit por escopo com chave na conta alvo, rotação de refresh com
blacklist, cabeçalhos de segurança fora do `DEBUG`, testes de contagem de query
contra N+1 — e a **decisão de não construir a fila**, com a análise registrada
em ["O que eu decidi NÃO construir"](DECISIONS.md). Pedir uma coisa e concluir
que ela não deve existir também é decisão.

## 5. Revisar o produto rodando, não o código

O prompt mais longo que dei. Percorri a aplicação no ar e listei ~35 problemas
**com diagnóstico**, agrupados por tela, definindo a ordem de execução. Trecho
literal:

> "Elenquei algumas possíveis melhorias:
>
> **Bugs (arruma primeiro)**
> - Preço R$ 0,00 em evento com lugar marcado — a home e o painel leem
>   `event.price` em vez de `min(secoes.preco)`. Afeta home, página do evento e
>   lista do organizador.
> - Atribuição TMDB ausente — obrigatória por contrato: aviso + logo no rodapé.
>
> **Conteúdo / seed**
> - Persistir o overview do TMDB e usá-lo na página do evento; template
>   `Sessão especial de ${titulo}` só como fallback.
> - Tirar o estado do título: "Minions & Monstros" + `soldOut`, "A Última Casa"
>   + `seatingType: 'assigned'`.
> - Espalhar os números de venda no seed — nenhum evento a 0/90.
>
> **Portaria — maior ganho por esforço**
> - Faixa de resultado grande (verde/vermelho/âmbar) ocupando meia tela, com
>   vibração e auto-limpeza em ~2s.
> - Código curto de 6–8 caracteres no lugar do UUID no campo manual.
> - Estados da câmera: pedindo permissão, negada (com instrução), indisponível.
> - Contador ao vivo "37/80 validados".
> - Últimos 5 scans com desfazer.
> - Reescrever o texto de ajuda como regra ("O ingresso precisa ser desta
>   sessão"), não como justificativa da feature.
> - Header próprio — busca de eventos não faz sentido aqui."

Repare que os itens não são "isso está feio". Cada um nomeia a causa provável
ou a regra violada — `event.price` em vez do mínimo das seções, a atribuição
exigida por contrato de licença, o UUID de 36 caracteres sendo impossível de
ditar numa fila.

## 6. Cortar escopo

> "Calma, **meia entrada e essas coisas que não são incluídas no pdf lá não
> precisa** por, creio eu."

Interrompi a implementação de itens da minha própria lista ao perceber que
estavam fora do enunciado. O enunciado diz: *"preferimos o fluxo inteiro simples
e completo a um pedaço sofisticado com telas pela metade"*.

Mais tarde, mesma coisa com os pôsteres: eu havia cogitado substituir a arte do
TMDb por arte própria e voltei atrás depois de concluir que a atribuição já
satisfaz a licença e que arte genérica pioraria a vitrine.

## 7. Restringir o consumo de recursos da máquina

> "**Cuidado quando for fazer testes pra não arrombar a memória do meu pc.**"

> "Continue e **tente não matar meu pc**."

Restrição de ambiente, não de produto — mas mudou como o trabalho foi feito: um
servidor de cada vez, um navegador por vez, processos encerrados após cada
verificação. Também produziu a lição de nunca usar `pkill -f` com um padrão que
casa com o próprio processo, registrada no `DECISIONS.md` depois de derrubar o
terminal três vezes.

## 8. Apontar um sintoma de performance sem prescrever a solução

> "Uma coisa que acho interessante implementarmos é **guardar os filmes e coisas
> puxadas de apis externas em cache** pois toda hora que eu recarrego a página,
> ele demora. E aí só puxar da api de novo quando houver uma alteração."

Descrevi o sintoma e a direção. A investigação mostrou **duas causas
diferentes**: o catálogo externo (resolvido com *stale-while-revalidate* —
1,25 s medidos viraram 0,001 s) e o cold start da Render, que cache nenhum
resolve e que virou limitação declarada no README. Pedir cache e receber
"metade disso não é cache" é o resultado certo.

## 9. Checar a afirmação, não aceitar a autocrítica

> "Como estão concentrados nossos commits? Começamos faz uns dias, não?"

O README afirmava "histórico concentrado", escrito de memória. Mandei conferir:
quatro dias de calendário, e os 47 commits do dia mais pesado distribuídos das
08:38 às 20:08 — cerca de um a cada quinze minutos, que é exatamente o commit
incremental que o enunciado quer ver. A autocrítica vaga foi trocada por número
verificável.

---

## O padrão

Relendo, o que se repete não é o tamanho do prompt — é o tipo:

| Tipo de intervenção | Exemplos |
|---|---|
| **Definir padrão antes do trabalho** | commits atômicos (1), design sem cara de IA (2) |
| **Conferir contra a fonte** | o PDF (3), o `git log` (9) |
| **Elevar o teto** | camada de senioridade (4) |
| **Diagnosticar, não reclamar** | as ~35 melhorias com causa (5), o cache (8) |
| **Cortar** | fora do enunciado (6), recursos da máquina (7) |

Nenhum deles é "faça um sistema de ingressos". O enunciado avisa que qualquer
enunciado colado numa ferramenta devolve um sistema inteiro — e que o que
interessa é o que vem depois disso.
