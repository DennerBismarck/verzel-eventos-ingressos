import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Só em desenvolvimento. O Next trata o host pelo qual o servidor foi
  // iniciado como a única origem confiável para servir os chunks de
  // /_next/static — e o Playwright abre a aplicação em 127.0.0.1, que o Next
  // considera OUTRA origem mesmo apontando para a mesma máquina.
  //
  // O sintoma não parece um problema de origem: os chunks são bloqueados, o
  // React nunca hidrata, nenhuma chamada à API sai, e a tela fica eternamente
  // no esqueleto de carregamento. A suíte inteira falha com "elemento não
  // encontrado", como se a aplicação estivesse quebrada.
  //
  // Não afeta produção: `allowedDevOrigins` só existe no servidor de dev.
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
