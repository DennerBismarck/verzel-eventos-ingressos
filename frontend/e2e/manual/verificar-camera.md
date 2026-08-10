# Verificar a leitura do QR pela câmera

A suíte automática (`npm run test:e2e`) cobre a portaria pela **digitação
manual**, e cobre o comportamento quando a câmera falha. O que ela não cobre é
a leitura pela câmera em si: navegador headless não tem câmera, e a alternativa
— alimentar uma câmera virtual — depende de Python com Pillow e gera um vídeo
de ~40 MB, que não faz sentido versionar nem rodar a cada commit.

Este procedimento existe para que essa verificação seja **reproduzível** em vez
de ficar na palavra de quem escreveu. Foi assim que a leitura foi confirmada.

## Como funciona

O Chromium aceita um arquivo `.y4m` no lugar da câmera. O truque é montar esse
vídeo com um QR de verdade:

1. Playwright compra um ingresso e tira um screenshot do QR renderizado na tela.
2. Pillow monta um `.y4m` com esse QR centralizado num quadro 640×480.
   - **O QR precisa caber dentro do `qrbox` de 240×240** que o leitor varre.
     Com 320px ele fica maior que a região varrida, é cortado e nunca decodifica
     — foi exatamente o que aconteceu na primeira tentativa.
   - Y4M é formato cru: cabeçalho de texto e planos YUV. Como o QR é preto e
     branco, o plano Y é a própria imagem em tons de cinza e os planos U/V são
     `128` constante (croma neutro).
3. O Chromium sobe com a câmera virtual apontando para esse arquivo, e a tela da
   portaria lê normalmente.

## Passos

```bash
# 1. backend e front no ar, com seed aplicado
cd backend && python manage.py seed && python manage.py runserver
cd frontend && npx next start --port 3100

# 2. capturar um QR real (compra um ingresso e fotografa o código)
node e2e/manual/capturar-qr.mjs        # imprime {idEvento, codigo} e salva qr.png

# 3. montar o vídeo da câmera virtual
python3 e2e/manual/montar-video.py     # gera qr.y4m a partir de qr.png

# 4. rodar a portaria com a câmera virtual
DADOS='<json impresso no passo 2>' node e2e/manual/ler-com-camera.mjs
```

Saída esperada:

```
camera abriu: sim
LEITURA PELA CAMERA -> Entrada liberada | Entrada liberada.
```

## Flags que fazem a mágica

```
--use-fake-ui-for-media-stream          concede a permissão sem diálogo
--use-fake-device-for-media-stream      liga a câmera virtual
--use-file-for-fake-video-capture=…y4m  define o que ela "enxerga"
```
