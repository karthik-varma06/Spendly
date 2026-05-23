import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { api, getApiErrorMessage } from '../lib/api';

type Category = {
  id: number;
  name: string;
  icon?: string | null;
  color?: string | null;
};

const ENTRY_TYPE_OPTIONS = [
  { value: 'expense', label: 'Expense' },
  { value: 'income', label: 'Savings / Income' },
] as const;

export default function AddExpense() {
  const nav = useNavigate();

  const [categories, setCategories] = useState<Category[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(true);
  const [loading, setLoading] = useState(false);
  const [entryType, setEntryType] = useState<'expense' | 'income'>('expense');
  const [error, setError] = useState<string | null>(null);

  const today = new Date().toISOString().split('T')[0];

  const [form, setForm] = useState({
    category_id: '',
    title: '',
    vendor_name: '',
    source: '',
    amount: '',
    entry_date: today,
    payment_method: '',
    notes: '',
  });

  const loadCategories = async () => {
    setLoadingCategories(true);
    setError(null);

    try {
      const res = await api.get<Category[]>('/categories');
      setCategories(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      setCategories([]);
      setError(getApiErrorMessage(err));
    } finally {
      setLoadingCategories(false);
    }
  };

  useEffect(() => {
    void loadCategories();
  }, []);

  const selectedLabel = useMemo(
    () =>
      entryType === 'expense'
        ? 'Expense name / merchant'
        : 'Income / savings title',
    [entryType],
  );

  const resetForm = () => {
    setForm({
      category_id: '',
      title: '',
      vendor_name: '',
      source: '',
      amount: '',
      entry_date: today,
      payment_method: '',
      notes: '',
    });
  };

  const submit = async () => {
    setLoading(true);
    setError(null);

    try {
      const amount = Number(form.amount);

      if (!amount || amount <= 0) {
        throw new Error('Please enter a valid amount');
      }

      if (entryType === 'expense') {
        const name = form.title || form.vendor_name || 'Expense';

        const category = categories.find(
          (c) => String(c.id) === String(form.category_id),
        );

        await api.post('/expenses', {
          name,
          title: name,
          expense_name: name,
          merchant_name: name,
          vendor_name: form.vendor_name || name,
          category_id: form.category_id
            ? Number(form.category_id)
            : null,
          category_name: category?.name || null,
          total_amount: amount,
          expense_date: form.entry_date || today,
          payment_method: form.payment_method || null,
          notes: form.notes || null,
          items: [],
          is_manual: true,
        });
      } else {
        await api.post('/income', {
          source:
            form.source ||
            form.title ||
            form.vendor_name ||
            'Income',
          amount,
          income_date: form.entry_date || today,
          notes: form.notes || null,
        });
      }

      window.dispatchEvent(new Event('notifications:refresh'));

      alert(
        entryType === 'expense'
          ? 'Expense added successfully'
          : 'Income / savings added successfully',
      );

      resetForm();

      nav('/dashboard');
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <div className="mb-5">
          <div className="inline-flex rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs font-medium tracking-[0.18em] text-[var(--muted)]">
            Manual Entry
          </div>

          <h2 className="mt-4 text-3xl font-semibold">
            Add entry
          </h2>

          <p className="mt-2 text-sm text-[var(--muted)]">
            Create either an expense or a savings / income record.
          </p>
        </div>

        <Card className="overflow-hidden p-0">
          <div className="border-b border-[var(--border)] bg-[var(--surface-strong)] px-6 py-5">
            <div className="flex flex-wrap gap-2">
              {ENTRY_TYPE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setEntryType(opt.value)}
                  className={`rounded-2xl px-4 py-2 text-sm font-medium transition-all duration-200 ${
                    entryType === opt.value
                      ? 'bg-[var(--text)] text-[var(--bg)] shadow-md'
                      : 'bg-[var(--surface)] text-[var(--text)] hover:bg-[var(--surface-strong)]'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="p-6">
            {error && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-5 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-700 dark:text-rose-200"
              >
                {error}
              </motion.div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              <input
                className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none transition focus:border-[var(--accent)]"
                placeholder={selectedLabel}
                value={form.title}
                onChange={(e) =>
                  setForm({ ...form, title: e.target.value })
                }
              />

              <input
                className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none transition focus:border-[var(--accent)]"
                type="text"
                inputMode="decimal"
                placeholder="Amount"
                value={form.amount}
                onChange={(e) =>
                  setForm({ ...form, amount: e.target.value })
                }
              />

              <input
                className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none transition focus:border-[var(--accent)]"
                type="date"
                value={form.entry_date}
                onChange={(e) =>
                  setForm({ ...form, entry_date: e.target.value })
                }
                required
              />

              {entryType === 'expense' ? (
                <select
                  className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none transition focus:border-[var(--accent)]"
                  value={form.category_id}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      category_id: e.target.value,
                    })
                  }
                  disabled={loadingCategories}
                >
                  <option value="">
                    {loadingCategories
                      ? 'Loading categories...'
                      : 'Select category'}
                  </option>

                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none transition focus:border-[var(--accent)]"
                  placeholder="Source / account"
                  value={form.source}
                  onChange={(e) =>
                    setForm({ ...form, source: e.target.value })
                  }
                />
              )}

              {entryType === 'expense' && (
                <input
                  className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none transition focus:border-[var(--accent)]"
                  placeholder="Payment method"
                  value={form.payment_method}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      payment_method: e.target.value,
                    })
                  }
                />
              )}

              <textarea
                className="min-h-[110px] rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none transition focus:border-[var(--accent)] md:col-span-2"
                placeholder="Notes"
                value={form.notes}
                onChange={(e) =>
                  setForm({ ...form, notes: e.target.value })
                }
              />
            </div>

            <div className="mt-6 flex items-center gap-3">
              <Button loading={loading} onClick={submit}>
                Save
              </Button>

              <Button
                variant="secondary"
                onClick={loadCategories}
                loading={loadingCategories}
              >
                Reload categories
              </Button>
            </div>
          </div>
        </Card>
      </motion.div>
    </div>
  );
}