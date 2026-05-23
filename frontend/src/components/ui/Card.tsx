// frontend/src/components/ui/Card.tsx
export default function Card({ className = '', children }: { className?: string; children: React.ReactNode }) {
  return <div className={`rounded-3xl border border-[var(--border)] bg-[var(--surface)] shadow-xl backdrop-blur ${className}`}>{children}</div>;
}