import { useEffect, useMemo, useState } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { api, getApiErrorMessage, DashboardSummary } from '../lib/api';

type BudgetItem = {
  id: string;
  category_id: number | null;
  category_name: string;
  budget_limit: number;
  spent_amount: number;
  progress_percent?: number;
  period: 'weekly' | 'monthly' | 'custom';
  start_date?: string | null;
  end_date?: string | null;
  notify_percentage?: number;
  is_active?: boolean;
};

type SummaryCategory = {
  name: string;
  value: number;
};

const CATEGORY_OPTIONS = [
  'FOOD',
  'TRAVEL',
  'SHOPPING',
  'ELECTRONICS',
  'HEALTH',
  'UTILITIES',
  'ENTERTAINMENT',
  'SUBSCRIPTIONS',
  'EDUCATION',
  'TRANSPORT',
  'OTHER',
] as const;

type BudgetMode = 'weekly' | 'monthly' | 'custom';

type FormState = {
  category_name: string;
  amount: string;
  mode: BudgetMode;
  start_date: string;
  end_date: string;
};

function getTodayISO() {
  return new Date().toISOString().slice(0, 10);
}

function getWeekBoundsISO() {
  const now = new Date();
  const day = now.getDay();
  const diffToMonday = day === 0 ? -6 : 1 - day;
  const start = new Date(now);
  start.setDate(now.getDate() + diffToMonday);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return {
    start_date: start.toISOString().slice(0, 10),
    end_date: end.toISOString().slice(0, 10),
  };
}

function getMonthBoundsISO() {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return {
    start_date: start.toISOString().slice(0, 10),
    end_date: end.toISOString().slice(0, 10),
  };
}

function getPeriodDefaults(mode: BudgetMode) {
  if (mode === 'weekly') return getWeekBoundsISO();
  if (mode === 'monthly') return getMonthBoundsISO();
  return { start_date: getTodayISO(), end_date: '' };
}

function formatMoney(value: number) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function formatTinyPercent(value: number) {
  if (!Number.isFinite(value) || value <= 0) return '<0.1%';
  if (value < 0.1) return '<0.1%';
  if (value >= 100) return '100%';
  return `${Math.round(value * 10) / 10}%`;
}

function periodLabel(period: BudgetItem['period']) {
  if (period === 'weekly') return 'Weekly';
  if (period === 'monthly') return 'Monthly';
  return 'Custom';
}

export default function Settings() {
  const [budgets, setBudgets] = useState<BudgetItem[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingBudgets, setLoadingBudgets] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<FormState>({
    category_name: 'FOOD',
    amount: '',
    mode: 'monthly',
    ...getPeriodDefaults('monthly'),
  });

  const loadData = async () => {
    setLoadingBudgets(true);
    setError(null);
    try {
      const [budRes, sumRes] = await Promise.all([
        api.get<BudgetItem[]>('/budgets'),
        api.get<DashboardSummary>('/dashboard/summary').catch(() => ({ data: null })),
      ]);
      setBudgets(Array.isArray(budRes.data) ? budRes.data : []);
      setSummary(sumRes.data || null);
    } catch (err) {
      setBudgets([]);
      setSummary(null);
      setError(getApiErrorMessage(err));
    } finally {
      setLoadingBudgets(false);
    }
  };

  useEffect(() => {
    void loadData();

    const refresh = () => void loadData();
    window.addEventListener('notifications:refresh', refresh);
    return () => window.removeEventListener('notifications:refresh', refresh);
  }, []);

  const selectedPeriodHint = useMemo(() => {
    if (form.mode === 'weekly') return 'This budget runs for the current week unless you override the dates.';
    if (form.mode === 'monthly') return 'This budget runs for the current month unless you override the dates.';
    return 'Pick the end date for a custom budget. Start date defaults to today.';
  }, [form.mode]);

  const liveCategoryMap = useMemo(() => {
    const rows: SummaryCategory[] = summary?.category_breakdown || [];
    return Object.fromEntries(rows.map((c) => [String(c.name).toUpperCase(), Number(c.value || 0)]));
  }, [summary]);

  const resolveSpent = (budget: BudgetItem) => {
    const liveSpent = Number(liveCategoryMap[String(budget.category_name || '').toUpperCase()] || 0);
    const apiSpent = Number(budget.spent_amount || 0);
    return liveSpent > 0 ? liveSpent : apiSpent;
  };

  const resolveProgress = (budget: BudgetItem, spent: number) => {
    const limit = Number(budget.budget_limit || 0);
    const apiProgress = Number(budget.progress_percent || 0);
    const computed = limit > 0 ? (spent / limit) * 100 : 0;
    const value = apiProgress > 0 ? apiProgress : computed;
    return limit > 0 ? Math.min(100, Math.max(0, value)) : 0;
  };

  const submit = async () => {
    setLoading(true);
    setError(null);

    const defaults = getPeriodDefaults(form.mode);

    try {
      await api.post('/budgets', {
        category_name: form.category_name,
        amount: Number(form.amount || 0),
        period: form.mode,
        start_date: form.start_date || defaults.start_date,
        end_date: form.mode === 'custom' ? (form.end_date || null) : (form.end_date || defaults.end_date),
        is_active: true,
      });

      setForm({
        category_name: 'FOOD',
        amount: '',
        mode: 'monthly',
        ...getPeriodDefaults('monthly'),
      });

      await loadData();
      window.dispatchEvent(new Event('notifications:refresh'));
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const deleteBudget = async (id: string) => {
    setLoadingBudgets(true);
    setError(null);
    try {
      await api.delete(`/budgets/${id}`);
      await loadData();
      window.dispatchEvent(new Event('notifications:refresh'));
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoadingBudgets(false);
    }
  };

  const updateMode = (mode: BudgetMode) => {
    setForm({
      ...form,
      mode,
      ...getPeriodDefaults(mode),
    });
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-2xl font-semibold">Budget settings</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Create weekly, monthly, or custom-date budgets. Delete any running budget anytime.
          </p>

          {error && (
            <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
              {error}
            </div>
          )}

          <div className="mt-6 grid gap-4">
            <div className="grid gap-2 md:grid-cols-2">
              <select
                className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none"
                value={form.category_name}
                onChange={(e) => setForm({ ...form, category_name: e.target.value })}
              >
                {CATEGORY_OPTIONS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>

              <input
                className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none"
                type="text"
                inputMode="decimal"
                placeholder="Budget amount"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
              />
            </div>

            <select
              className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none"
              value={form.mode}
              onChange={(e) => updateMode(e.target.value as BudgetMode)}
            >
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="custom">Custom date</option>
            </select>

            <div className="grid gap-4 md:grid-cols-2">
              <input
                className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none"
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              />

              <input
                className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none"
                type="date"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                disabled={form.mode !== 'custom'}
              />
            </div>

            <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)]">
              {selectedPeriodHint}
            </div>

            <Button loading={loading} onClick={submit} className="w-fit">
              Save budget
            </Button>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xl font-semibold">Saved budgets</h3>
            <Button variant="secondary" loading={loadingBudgets} onClick={loadData}>
              Refresh
            </Button>
          </div>

          <div className="mt-4 space-y-3">
            {budgets.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[var(--border)] p-4 text-sm text-[var(--muted)]">
                No budgets set yet.
              </div>
            ) : (
              budgets.map((b) => {
                const spent = resolveSpent(b);
                const limit = Number(b.budget_limit || 0);
                const progress = resolveProgress(b, spent);
                const safeWidth = progress > 0 && progress < 0.1 ? 2 : Math.max(2, Math.min(100, progress));
                const danger = progress >= 100;
                const warn = progress >= 80 && progress < 100;

                return (
                  <div key={b.id} className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-semibold">{b.category_name}</div>
                        <div className="mt-1 text-sm text-[var(--muted)]">
                          {periodLabel(b.period)} · Limit {formatMoney(limit)}
                        </div>
                        <div className="mt-1 text-sm text-[var(--muted)]">
                          Spent {formatMoney(spent)}
                          {b.start_date ? ` · Starts ${String(b.start_date).slice(0, 10)}` : ''}
                          {b.end_date ? ` · Ends ${String(b.end_date).slice(0, 10)}` : ''}
                        </div>
                      </div>

                      <button
                        onClick={() => deleteBudget(b.id)}
                        className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200 hover:bg-rose-500/15"
                      >
                        Delete
                      </button>
                    </div>

                    <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
                      <div
                        className={`h-full rounded-full ${
                          danger ? 'bg-rose-500' : warn ? 'bg-amber-400' : 'bg-emerald-400'
                        }`}
                        style={{ width: `${safeWidth}%` }}
                      />
                    </div>
                    <div className="mt-2 text-xs text-[var(--muted)]">{formatTinyPercent(progress)} used</div>
                  </div>
                );
              })
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
