// frontend/src/components/ui/Button.tsx
import { ButtonHTMLAttributes } from 'react';

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
  variant?: 'primary' | 'secondary' | 'ghost';
};

export default function Button({ loading = false, variant = 'primary', className = '', children, disabled, ...props }: Props) {
  const styles = {
    primary: 'bg-[var(--text)] text-[var(--bg)] hover:opacity-90',
    secondary: 'bg-[var(--surface-strong)] text-[var(--text)] border border-[var(--border)]',
    ghost: 'bg-transparent text-[var(--text)] hover:bg-[var(--surface)]',
  }[variant];

  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-60 ${styles} ${className}`}
    >
      {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  );
}