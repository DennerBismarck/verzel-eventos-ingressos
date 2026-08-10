"""
Monta a câmera virtual (.y4m) a partir do QR capturado por capturar-qr.mjs.

Y4M é formato cru: cabeçalho de texto e planos YUV sem compressão. Como o QR é
preto e branco, o plano Y é a própria imagem em tons de cinza e os planos de
croma (U e V) são 128 constante — cinza neutro.
"""

import pathlib

from PIL import Image

AQUI = pathlib.Path(__file__).parent
LARGURA, ALTURA, FPS, QUADROS = 640, 480, 30, 90

# 180px e não mais: o leitor varre um qrbox de 240x240. Um QR maior que essa
# janela é cortado e nunca decodifica.
LADO_DO_QR = 180

qr = Image.open(AQUI / "qr.png").convert("L").resize(
    (LADO_DO_QR, LADO_DO_QR), Image.NEAREST
)
# Fundo branco em volta: sem a "zona de silêncio" do padrão, o decodificador
# não encontra os three finder patterns dos cantos.
quadro = Image.new("L", (LARGURA, ALTURA), 255)
quadro.paste(qr, ((LARGURA - LADO_DO_QR) // 2, (ALTURA - LADO_DO_QR) // 2))

luma = quadro.tobytes()
croma = bytes([128]) * ((LARGURA // 2) * (ALTURA // 2))

destino = AQUI / "qr.y4m"
with destino.open("wb") as f:
    f.write(f"YUV4MPEG2 W{LARGURA} H{ALTURA} F{FPS}:1 Ip A1:1 C420mpeg2\n".encode())
    for _ in range(QUADROS):
        f.write(b"FRAME\n")
        f.write(luma)
        f.write(croma)
        f.write(croma)

print(f"{destino.name}: {destino.stat().st_size / 1024 / 1024:.1f} MB")
