# Desafio Elite Dev — Verzel (transcrição do enunciado)

## Proposta
Validar conhecimentos em Front-End e Back-End, lógica e capacidade de entender/atender a demanda.
Criar uma **Plataforma de Eventos e Ingressos**: um organizador publica eventos e um cliente compra ingressos.

- **Organizador** monta um evento a partir de um catálogo de shows/filmes vindo de uma **API externa**, definindo data, local, capacidade e preço.
- **Cliente** navega pelos eventos publicados, reserva o lugar, paga de forma simulada, recebe um ingresso com **código em QR** e pode compartilhá-lo por link.
- **Portaria** valida o ingresso na entrada.

> "Queremos ver a SUA mão no resultado." Interessa COMO você pensa, as decisões, o que descartou. Fuja do AI slop.

## Requisitos Funcionais
### Front-End
- Navegação e busca pelos eventos publicados (shows ou filmes em cartaz), com data, local e preço.
- Criação e gerenciamento dos eventos pelo organizador.
- Fluxo de reserva: seleção do lugar num **mapa de assentos** (cinema/teatro) OU **quantidade de ingressos** (pista). Implemente um dos dois, ou os dois.
- **Pagamento simulado**, contemplando confirmação E recusa.
- Área de **"Meus ingressos"**, exibindo o ingresso e seu código em QR.
- Tela de **portaria**, validando o ingresso com retorno claro: **válido, inválido, já utilizado ou evento errado**.
- Leitura do **QR pela câmera** na portaria, com digitação manual do código como alternativa.

### Back-End
- Gestão das chamadas para a API externa: **Ticketmaster Discovery** ou **TMDb** (uma, a outra, ou as duas).
  - developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2
  - developer.themoviedb.org/docs
- **Autenticação com 3 papéis**: Organizador (cria/gerencia eventos), Cliente (reserva/paga/recebe), Portaria (valida).
- Armazenamento dos eventos, reservas e ingressos.
- Garantia de que **o mesmo lugar não seja vendido duas vezes**.
- Geração do ingresso com **código em QR que não possa ser forjado**.
- Lógica para o cliente **compartilhar um ingresso via link** gerado pela aplicação.
- Validação na portaria garantindo que **o mesmo ingresso não seja validado duas vezes**.
- Cobrança **simulada**, sem transação real (pode usar sandbox de um provedor de verdade se preferir).

## Tecnologias Obrigatórias
- **Front-End:** React (com ou sem framework: Next.js, Vite, Remix...).
- **Back-End:** NodeJS, Python ou Java (NestJS, Express, FastAPI, Django, Spring Boot...).
- **Banco:** qualquer um; README com instruções claras de configuração/uso.

### Referências (não copiar; ponto de partida)
- ingresso.com — mapa de assentos de cinema.
- eventim.com.br — pista e setores por quantidade.
- sympla.com.br — criação de evento e checkout.

## Requisitos Não Funcionais
- **Prazo: 7 dias corridos** a partir do recebimento.
- **README detalhado**: passo a passo pra configurar/executar. Se algo não funciona, dizer no README. Ausência de explicação penaliza.
- **Dados de teste (seed):** 1 organizador, 2 clientes, 1 usuário de portaria e ≥1 evento publicado com ingressos disponíveis — pra percorrer o fluxo sem montar do zero.
- **Deploy:** não obrigatório, mas **publicar na Vercel/similar rende +1 ponto**.

## Opcionais (contam na avaliação, nenhum obrigatório)
- Busca e filtro de eventos, painel do organizador, cancelamento com devolução ao estoque.
- Mapa de assentos em tempo real, Docker Compose, testes, aplicação publicada.

### NÃO precisa fazer
Nota fiscal, revenda entre usuários, app nativo, recuperação de senha, envio de ingresso por e-mail.

## Uso de IA (permitido e recomendado)
- Usar IA bem é valorizado, não tira ponto. **Conte no README** quais ferramentas usou, em que partes, e o que fez sem IA.
- Se produziu artefatos (specs, PRD, fluxos, arquivos de contexto), **versione junto no repo**.

## Entrega
- **Repositório GitHub público.** Commits ao longo da semana com mensagens descritivas (o histórico mostra o processo).
- Enviar o link pelo formulário **elitedev.verzel.com.br**, indicando onde foi publicado e como executar.

## Dica oficial
- Faça o **básico rodar de ponta a ponta** e só depois agregue valor. Fluxo inteiro simples > pedaço sofisticado pela metade.
- Interface bem feita, documentação clara, organização de código, tratamento de erros, versionamento e testes básicos = diferenciais.
- Iniciativa/criatividade contam. "Dê o seu melhor e mostre o que VOCÊ tem de melhor."
