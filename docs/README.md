# Documentação

Cinco arquivos, dois papéis diferentes. A distinção importa para ler cada um
com a expectativa certa.

## Documentos vivos — descrevem o projeto como ele é hoje

| Arquivo | O que é | Quando ler |
|---------|---------|------------|
| [`DECISIONS.md`](DECISIONS.md) | 60+ decisões numeradas, cada uma com a alternativa descartada e o porquê. Mais duas seções que valem por si: **"Bugs que valem contar"** (sintoma → diagnóstico → causa → correção) e **"O que eu decidi NÃO construir"** | Para qualquer pergunta que comece com "por que você fez assim?" |
| [`DEFESA.md`](DEFESA.md) | Os quatro mecanismos que sustentam o projeto — lock de estoque, HMAC do QR, token de compartilhamento e validação na portaria — explicados pelo funcionamento, não por decoreba | Antes da entrevista |
| [`CHALLENGE.md`](CHALLENGE.md) | Transcrição do enunciado da Verzel | Para conferir requisito contra implementação |

## Registros do dia 0 — mantidos inalterados, e já desatualizados

Estes dois **não descrevem o resultado**. São o que eu planejei antes de
começar, guardados porque a distância entre plano e execução é informação.

Os dois afirmam um modo de trabalho ("eu escrevo o núcleo, a IA fica no
boilerplate") que **não foi o que aconteceu**. Quem manda nesse assunto é a
seção "Uso de IA" do [README principal](../README.md). Cada arquivo abre com
uma nota dizendo isso.

| Arquivo | O que é |
|---------|---------|
| [`PLANNING.md`](PLANNING.md) | Arquitetura, modelo de dados, rascunho de endpoints e o cronograma de 7 dias que não se cumpriu como escrito |
| [`PROMPT-SESSAO.md`](PROMPT-SESSAO.md) | O prompt com que abri a sessão de trabalho com a IA |

## Fora daqui

- [`../README.md`](../README.md) — instalação, dados de teste, tabela da API,
  segurança, testes, deploy, uso de IA e limitações conhecidas. É a porta de
  entrada do projeto.
- [`../frontend/e2e/manual/verificar-camera.md`](../frontend/e2e/manual/verificar-camera.md)
  — como reproduzir a verificação da leitura de QR por câmera, que não cabe em
  navegador headless.
- `../frontend/AGENTS.md` — gerado e reescrito pelo `next dev`. É ruído de
  ferramenta, não documentação do projeto; fica versionado só para a árvore de
  trabalho não acusar mudança a cada execução.
