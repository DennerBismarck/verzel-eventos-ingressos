"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert, Button, Field } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/types";

const PAPEIS: { valor: Role; titulo: string; texto: string }[] = [
  { valor: "CUSTOMER", titulo: "Cliente", texto: "Comprar ingressos e receber o QR" },
  { valor: "ORGANIZER", titulo: "Organizador", texto: "Publicar e gerenciar eventos" },
  { valor: "GATE", titulo: "Portaria", texto: "Validar entradas no local" },
];

export default function CriarContaPage() {
  const { register } = useAuth();
  const router = useRouter();

  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [role, setRole] = useState<Role>("CUSTOMER");
  const [erros, setErros] = useState<Record<string, string>>({});
  const [geral, setGeral] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setOcupado(true);
    setErros({});
    setGeral(null);
    try {
      const user = await register({ email, password: senha, full_name: nome, role });
      router.push(
        user.role === "ORGANIZER"
          ? "/organizador"
          : user.role === "GATE"
            ? "/portaria"
            : "/minha-conta",
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        // O DRF devolve {campo: ["mensagem"]}. Mostrar cada erro NO SEU campo é
        // o que diferencia um formulário utilizável de um "algo deu errado".
        const dados = err.data as Record<string, string[] | string>;
        const mapeado: Record<string, string> = {};
        for (const [campo, msgs] of Object.entries(dados)) {
          mapeado[campo] = Array.isArray(msgs) ? msgs[0] : String(msgs);
        }
        setErros(mapeado);
      } else {
        setGeral("Não foi possível criar a conta. Tente novamente.");
      }
      setOcupado(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-12">
      <h1 className="text-2xl font-bold text-ink">Criar conta</h1>
      <p className="mt-1 text-sm text-muted">Leva menos de um minuto.</p>

      <form onSubmit={enviar} className="mt-6 space-y-4">
        {geral && <Alert tone="danger">{geral}</Alert>}

        <Field
          label="Nome completo"
          name="full_name"
          autoComplete="name"
          required
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          error={erros.full_name}
        />
        <Field
          label="E-mail"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={erros.email}
        />
        <Field
          label="Senha"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          error={erros.password}
          hint="Mínimo de 8 caracteres, e não pode ser só números."
        />

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-ink">
            Como você vai usar a plataforma?
          </legend>
          <div className="space-y-2">
            {PAPEIS.map((p) => (
              <label
                key={p.valor}
                className={`flex cursor-pointer items-start gap-3 rounded border p-3
                  ${
                    role === p.valor
                      ? "border-brand bg-brand/4"
                      : "border-line-strong bg-white hover:border-brand/40"
                  }`}
              >
                <input
                  type="radio"
                  name="role"
                  value={p.valor}
                  checked={role === p.valor}
                  onChange={() => setRole(p.valor)}
                  className="mt-0.5 accent-brand"
                />
                <span>
                  <span className="block text-sm font-semibold text-ink">{p.titulo}</span>
                  <span className="block text-xs text-muted">{p.texto}</span>
                </span>
              </label>
            ))}
          </div>
          {erros.role && <p className="mt-1.5 text-xs font-medium text-danger">{erros.role}</p>}
        </fieldset>

        <Button type="submit" size="lg" className="w-full" loading={ocupado}>
          Criar conta
        </Button>
      </form>

      <p className="mt-4 text-center text-sm text-muted">
        Já tem conta?{" "}
        <Link href="/entrar" className="font-semibold text-brand hover:underline">
          Entrar
        </Link>
      </p>
    </div>
  );
}
