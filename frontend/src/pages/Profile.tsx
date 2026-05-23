import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ChevronDown,
  Download,
  FileSpreadsheet,
  FileText,
  Mail,
  Sparkles,
  UserRound,
  Clock3,
  Wallet,
  ShieldCheck,
} from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { api, AuthMeResponse } from '../lib/api';

type ExportFormat = 'xlsx' | 'pdf';

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.04 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] },
  },
};

export default function Profile() {
  const [profile, setProfile] = useState<AuthMeResponse | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api
      .get<AuthMeResponse>('/auth/me')
      .then((res) => setProfile(res.data))
      .catch(() => setProfile(null));
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setExportOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const user = profile?.user;

  const exportHint = useMemo(
    () => 'Export your full dashboard data as a PDF report or Excel workbook.',
    [],
  );

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
  };

  const handleExport = async (format: ExportFormat) => {
    setError(null);
    setExporting(format);

    try {
      const endpoint = format === 'pdf' ? '/export/dashboard/pdf' : '/export/dashboard/xlsx';
      const response = await api.get(endpoint, { responseType: 'blob' });

      const blob = new Blob([response.data], {
        type:
          format === 'pdf'
            ? 'application/pdf'
            : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });

      downloadBlob(blob, `spendly_dashboard_export.${format}`);
      setExportOpen(false);
    } catch {
      setError('Export failed. Please try again.');
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="relative mx-auto max-w-5xl px-4 py-8">
      <motion.div variants={containerVariants} initial="hidden" animate="show" className="space-y-6">
        <motion.div
          variants={itemVariants}
          className="flex flex-col gap-4 rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-sm md:flex-row md:items-center md:justify-between"
        >
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-strong)] px-3 py-1 text-xs font-medium tracking-[0.18em] text-[var(--muted)]">
              <Sparkles className="h-3.5 w-3.5" />
              Spendly profile
            </div>
            <h2 className="mt-3 text-3xl font-semibold">Profile</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
              View your account details and export the full dashboard in a clean PDF or Excel format.
            </p>
          </div>

          <div ref={menuRef} className="relative">
            <Button
              variant="secondary"
              onClick={() => setExportOpen((v) => !v)}
              className="flex items-center gap-2"
            >
              <Download className="h-4 w-4" />
              Export dashboard
              <ChevronDown className="h-4 w-4" />
            </Button>

            <AnimatePresence>
              {exportOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -8, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.98 }}
                  transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
                  className="absolute right-0 top-12 z-30 w-72 overflow-hidden rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)] p-2 shadow-2xl"
                >
                  <button
                    type="button"
                    onClick={() => void handleExport('pdf')}
                    disabled={exporting !== null}
                    className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm transition hover:bg-[var(--surface)] disabled:opacity-60"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-500">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="font-medium">Export as PDF</div>
                      <div className="text-xs text-[var(--muted)]">Beautiful multi-page report</div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => void handleExport('xlsx')}
                    disabled={exporting !== null}
                    className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm transition hover:bg-[var(--surface)] disabled:opacity-60"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-500">
                      <FileSpreadsheet className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="font-medium">Export as Excel</div>
                      <div className="text-xs text-[var(--muted)]">Styled workbook file</div>
                    </div>
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {error && (
          <motion.div
            variants={itemVariants}
            className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-700 dark:text-rose-200"
          >
            {error}
          </motion.div>
        )}

        <motion.div variants={itemVariants}>
          <Card className="overflow-hidden p-0">
            <div className="border-b border-[var(--border)] bg-[var(--surface-strong)] px-6 py-5">
              <h3 className="text-xl font-semibold">Account details</h3>
              <p className="mt-1 text-sm text-[var(--muted)]">{exportHint}</p>
            </div>

            {user ? (
              <div className="p-6">
                <div className="grid gap-4 md:grid-cols-2">
                  <InfoCard icon={UserRound} label="Name" value={user.full_name} />
                  <InfoCard icon={Mail} label="Email" value={user.email} />
                  <InfoCard icon={Wallet} label="Currency" value={user.currency || 'INR'} />
                  <InfoCard icon={Clock3} label="Timezone" value={user.timezone || 'Asia/Kolkata'} />
                  <InfoCard icon={ShieldCheck} label="Verified" value={user.is_verified ? 'Yes' : 'No'} />
                  <InfoCard icon={ShieldCheck} label="Active" value={user.is_active ? 'Yes' : 'No'} />
                </div>
              </div>
            ) : (
              <div className="p-6 text-sm text-[var(--muted)]">Loading profile...</div>
            )}
          </Card>
        </motion.div>
      </motion.div>
    </div>
  );
}

function InfoCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)] p-5 shadow-sm"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
          <Icon className="h-5 w-5 text-[var(--accent)]" />
        </div>
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-[0.16em] text-[var(--muted)]">{label}</div>
          <div className="mt-2 break-all text-sm font-semibold">{value}</div>
        </div>
      </div>
    </motion.div>
  );
}