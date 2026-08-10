/**
 * Primitivos de interface.
 *
 * Sem biblioteca de componentes: o projeto usa poucos elementos e cada um
 * precisa de comportamento específico (estado de carregando no botão, erro
 * ligado ao input por aria-describedby). Uma dependência a mais não pagaria.
 */

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
};

const VARIANTES = {
  primary:
    "bg-accent text-white hover:bg-accent-dark disabled:bg-line-strong disabled:text-muted",
  secondary:
    "bg-white text-ink border border-line-strong hover:bg-canvas disabled:text-muted",
  ghost: "text-brand hover:bg-canvas disabled:text-muted",
  danger:
    "bg-white text-danger border border-danger/30 hover:bg-danger-soft disabled:text-muted",
} as const;

const TAMANHOS = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-[15px]",
} as const;

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      // aria-busy: leitor de tela anuncia que a ação está em andamento.
      aria-busy={loading || undefined}
      className={`inline-flex items-center justify-center gap-2 rounded font-semibold
        transition-colors disabled:cursor-not-allowed
        ${VARIANTES[variant]} ${TAMANHOS[size]} ${className}`}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block size-4 shrink-0 animate-spin rounded-full
        border-2 border-current border-r-transparent opacity-70 ${className}`}
    />
  );
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string | null;
  hint?: string;
};

export function Field({ label, error, hint, id, className = "", ...props }: FieldProps) {
  const inputId = id ?? props.name ?? label;
  const errorId = `${inputId}-erro`;
  const hintId = `${inputId}-dica`;

  return (
    <div className={className}>
      <label htmlFor={inputId} className="mb-1.5 block text-sm font-medium text-ink">
        {label}
      </label>
      <input
        {...props}
        id={inputId}
        aria-invalid={error ? true : undefined}
        // Liga o texto do erro ao campo: o leitor de tela lê os dois juntos,
        // em vez de anunciar um input "inválido" sem dizer por quê.
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        className={`h-10 w-full rounded border bg-white px-3 text-sm text-ink
          placeholder:text-muted
          ${error ? "border-danger" : "border-line-strong"}`}
      />
      {hint && !error && (
        <p id={hintId} className="mt-1.5 text-xs text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="mt-1.5 text-xs font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

type AlertProps = {
  tone?: "info" | "ok" | "warn" | "danger";
  title?: string;
  children: ReactNode;
};

const TONS = {
  info: "bg-white border-line-strong text-body",
  ok: "bg-ok-soft border-ok/25 text-ok",
  warn: "bg-warn-soft border-warn/25 text-warn",
  danger: "bg-danger-soft border-danger/25 text-danger",
} as const;

export function Alert({ tone = "info", title, children }: AlertProps) {
  return (
    <div
      // role=alert faz o leitor de tela anunciar na hora que a mensagem aparece.
      role={tone === "danger" ? "alert" : "status"}
      className={`rounded border px-4 py-3 text-sm ${TONS[tone]}`}
    >
      {title && <p className="mb-0.5 font-semibold">{title}</p>}
      {children}
    </div>
  );
}

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "ok" | "warn" | "danger" | "brand";
  children: ReactNode;
}) {
  const tons = {
    neutral: "bg-canvas text-muted border-line",
    ok: "bg-ok-soft text-ok border-ok/20",
    warn: "bg-warn-soft text-warn border-warn/20",
    danger: "bg-danger-soft text-danger border-danger/20",
    brand: "bg-brand/8 text-brand border-brand/20",
  } as const;
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5
        text-[11px] font-semibold uppercase tracking-wide ${tons[tone]}`}
    >
      {children}
    </span>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-card border border-dashed border-line-strong bg-white px-6 py-12 text-center">
      <p className="font-semibold text-ink">{title}</p>
      {children && <p className="mx-auto mt-1 max-w-md text-sm text-muted">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** Placeholder de carregamento com a mesma forma do conteúdo real. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-line ${className}`} />;
}
