/** Minimal component primitives. Kept inline-and-typed rather than pulling in
 * the full ShadCN scaffold — cheaper, same spirit. */
import { type PropsWithChildren, type ReactNode } from 'react';
import clsx from 'clsx';

export function Card({
  title,
  step,
  children,
  className,
}: PropsWithChildren<{ title: string; step?: number; className?: string }>) {
  return (
    <div
      className={clsx(
        'flex flex-col rounded border border-border bg-white shadow-sm',
        className,
      )}
    >
      <div className="flex items-baseline justify-between border-b border-border bg-surface px-4 py-2.5">
        <h3 className="font-serif text-base">
          {step !== undefined ? (
            <span className="mr-2 text-muted">{step}.</span>
          ) : null}
          {title}
        </h3>
      </div>
      <div className="flex-1 overflow-auto p-4">{children}</div>
    </div>
  );
}

export function Badge({
  children,
  variant = 'default',
}: PropsWithChildren<{ variant?: 'default' | 'accent' | 'good' | 'warn' }>) {
  const styles: Record<typeof variant, string> = {
    default: 'bg-surface text-muted',
    accent: 'bg-accent-soft text-accent',
    good: 'bg-good-soft text-good',
    warn: 'bg-warn-soft text-warn',
  };
  return (
    <span
      className={clsx(
        'inline-block rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
        styles[variant],
      )}
    >
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  disabled,
  className,
}: PropsWithChildren<{
  onClick?: () => void;
  type?: 'button' | 'submit';
  variant?: 'primary' | 'secondary' | 'ghost';
  disabled?: boolean;
  className?: string;
}>) {
  const styles: Record<typeof variant, string> = {
    primary: 'bg-accent text-white hover:bg-accent/90 disabled:bg-accent/40',
    secondary:
      'bg-surface text-ink hover:bg-border disabled:text-muted disabled:bg-surface/50',
    ghost:
      'text-muted hover:text-ink hover:bg-surface disabled:text-muted/40',
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'rounded px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed',
        styles[variant],
        className,
      )}
    >
      {children}
    </button>
  );
}

export function CodeBlock({
  children,
  className,
}: PropsWithChildren<{ className?: string }>) {
  return (
    <pre
      className={clsx(
        'overflow-auto whitespace-pre-wrap break-words rounded bg-code-bg p-3 font-mono text-[12px] leading-snug text-code-ink',
        className,
      )}
    >
      {children}
    </pre>
  );
}

export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={clsx(
          'relative h-5 w-9 shrink-0 rounded-full transition',
          checked ? 'bg-accent' : 'bg-border',
        )}
      >
        <span
          className={clsx(
            'absolute top-0.5 h-4 w-4 rounded-full bg-white transition',
            checked ? 'left-[18px]' : 'left-0.5',
          )}
        />
      </button>
      <span>{label}</span>
    </label>
  );
}
