import type { ComponentPropsWithoutRef, ReactNode } from 'react';
import { Link } from 'react-router-dom';

export const cx = (...classes: (string | false | null | undefined)[]) => classes.filter(Boolean).join(' ');

/* Radios del sistema: controles 10px, tarjetas 16px, píldoras completas. */

const BUTTON_BASE =
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[10px] text-[15px] font-medium ' +
  'transition-[transform,background-color,border-color,opacity] duration-200 ease-[var(--ease-out-expo)] ' +
  'active:translate-y-px disabled:pointer-events-none disabled:opacity-40';

const VARIANTS = {
  primary: 'bg-fog-100 text-ink-900 hover:bg-white',
  accent: 'bg-accent text-ink-900 hover:bg-accent-bright',
  surface: 'bg-ink-700 text-fog-100 border border-white/10 hover:border-white/20 hover:bg-ink-600',
  ghost: 'text-fog-300 hover:text-fog-100 hover:bg-white/5',
} as const;

const SIZES = {
  sm: 'h-9 px-3.5',
  md: 'h-11 px-5',
} as const;

type ButtonProps = ComponentPropsWithoutRef<'button'> & {
  variant?: keyof typeof VARIANTS;
  size?: keyof typeof SIZES;
};

export function Button({ variant = 'primary', size = 'md', className, ...props }: ButtonProps) {
  return <button className={cx(BUTTON_BASE, VARIANTS[variant], SIZES[size], className)} {...props} />;
}

type LinkButtonProps = {
  to: string;
  variant?: keyof typeof VARIANTS;
  size?: keyof typeof SIZES;
  className?: string;
  children: ReactNode;
};

export function LinkButton({ to, variant = 'primary', size = 'md', className, children }: LinkButtonProps) {
  return (
    <Link to={to} className={cx(BUTTON_BASE, VARIANTS[variant], SIZES[size], className)}>
      {children}
    </Link>
  );
}

export function ExternalButton({
  href,
  variant = 'surface',
  size = 'sm',
  className,
  children,
}: Omit<LinkButtonProps, 'to'> & { href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={cx(BUTTON_BASE, VARIANTS[variant], SIZES[size], className)}
    >
      {children}
    </a>
  );
}

export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cx('rounded-[16px] border border-white/8 bg-ink-850 hairline-top', className)}>{children}</div>
  );
}

export function Pill({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-2 rounded-full border border-white/10 bg-ink-800/80 px-3 py-1',
        'font-mono text-[11px] tracking-wide text-fog-300 backdrop-blur',
        className,
      )}
    >
      {children}
    </span>
  );
}
