import { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Upload as UploadIcon,
  RefreshCcw,
  FileText,
  Image as ImageIcon,
  ReceiptText,
  CircleAlert,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';
import {
  api,
  ExpenseDraft,
  ExpenseItemDraft,
  HealthStatus,
  UploadAnalysisResponse,
  getApiErrorMessage,
} from '../lib/api';

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
];

const emptyItem: ExpenseItemDraft = {
  item_name: '',
  quantity: 1,
  unit_price: 0,
  total_price: 0,
  item_category: 'OTHER',
};

const emptyDraft: ExpenseDraft = {
  vendor_name: '',
  invoice_number: '',
  date: '',
  time: '',
  phone: '',
  email: '',
  address: '',
  items: [{ ...emptyItem }],
  subtotal: 0,
  cgst: 0,
  sgst: 0,
  igst: 0,
  discount: 0,
  total_amount: 0,
  payment_method: '',
  category: 'OTHER',
  llm_provider: '',
  llm_model: '',
  llm_error: '',
  extraction_mode: '',
};

const quickTypes = [
  { label: 'Receipt', icon: ReceiptText },
  { label: 'Invoice', icon: FileText },
  { label: 'Bill', icon: CircleAlert },
  { label: 'Image', icon: ImageIcon },
];

function safeNumber(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function normalizeDateForInput(value?: string | null): string {
  if (!value) return '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const m1 = value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (m1) return `${m1[3]}-${m1[2]}-${m1[1]}`;
  const m2 = value.match(/^(\d{2})-(\d{2})-(\d{4})$/);
  if (m2) return `${m2[3]}-${m2[2]}-${m2[1]}`;
  return value;
}

function normalizeDraft(d: ExpenseDraft): ExpenseDraft {
  const items = (d.items?.length ? d.items : [{ ...emptyItem }]).map((item) => ({
    item_name: item.item_name || '',
    quantity: safeNumber(item.quantity || 1) || 1,
    unit_price: safeNumber(item.unit_price),
    total_price: safeNumber(item.total_price),
    item_category: item.item_category || 'OTHER',
  }));

  return {
    ...emptyDraft,
    ...d,
    date: normalizeDateForInput(d.date || ''),
    items,
    subtotal: safeNumber(d.subtotal),
    cgst: safeNumber(d.cgst),
    sgst: safeNumber(d.sgst),
    igst: safeNumber(d.igst),
    discount: safeNumber(d.discount),
    total_amount: safeNumber(d.total_amount),
    category: (d.category || 'OTHER').toUpperCase(),
  };
}

export default function Upload() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const nav = useNavigate();

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [analysis, setAnalysis] = useState<UploadAnalysisResponse | null>(null);
  const [draft, setDraft] = useState<ExpenseDraft>(emptyDraft);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadHealth = async () => {
    try {
      const res = await api.get<HealthStatus>('/health');
      setHealth(res.data);
    } catch {
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    void loadHealth();
  }, []);

  const canSave = useMemo(() => !!analysis?.uploaded_file_id, [analysis]);

  const handleFile = (file: File | null) => {
    setSelectedFile(file);
    setError(null);
    setMessage(null);
  };

  const onPickFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFile(e.target.files?.[0] || null);
  };

  const onBrowse = () => fileInputRef.current?.click();

  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const onDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const onDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0] || null;
    handleFile(file);
  };

  const analyze = async () => {
    if (!selectedFile) return setError('Please choose a file first.');

    setAnalyzing(true);
    setError(null);
    setMessage(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const res = await api.post<UploadAnalysisResponse>('/uploads/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setAnalysis(res.data);
      setDraft(normalizeDraft(res.data.structured_data));
      setMessage(`${res.data.message} (${res.data.extraction_mode})`);
      await loadHealth();
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setAnalyzing(false);
    }
  };

  const saveDraft = async () => {
    if (!analysis?.uploaded_file_id) return setError('Analyze a file before saving.');
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      await api.post('/uploads/save', {
        uploaded_file_id: analysis.uploaded_file_id,
        draft,
      });
      setMessage('Saved successfully. Redirecting to dashboard...');
      setAnalysis(null);
      setDraft(emptyDraft);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadHealth();
      nav('/dashboard');
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const updateItem = (index: number, key: keyof ExpenseItemDraft, value: string | number) => {
    setDraft((prev) => {
      const items = [...prev.items];
      items[index] = { ...items[index], [key]: value } as ExpenseItemDraft;
      if (key === 'unit_price' || key === 'quantity') {
        const q = safeNumber(items[index].quantity || 1) || 1;
        const p = safeNumber(items[index].unit_price);
        items[index].total_price = q * p;
      }
      return { ...prev, items };
    });
  };

  const addItem = () =>
    setDraft((prev) => ({
      ...prev,
      items: [...prev.items, { ...emptyItem }],
    }));

  const removeItem = (index: number) =>
    setDraft((prev) => ({
      ...prev,
      items: prev.items.filter((_, i) => i !== index) || [{ ...emptyItem }],
    }));

  const syncTotals = (nextDraft: ExpenseDraft) => {
    const subtotalAuto = nextDraft.items.reduce(
      (sum, item) =>
        sum + (safeNumber(item.total_price) || safeNumber(item.unit_price) * safeNumber(item.quantity || 1)),
      0,
    );
    const subtotal = safeNumber(nextDraft.subtotal) || subtotalAuto;
    const total =
      safeNumber(nextDraft.total_amount) ||
      subtotal +
        safeNumber(nextDraft.cgst) +
        safeNumber(nextDraft.sgst) +
        safeNumber(nextDraft.igst) -
        safeNumber(nextDraft.discount);

    return { ...nextDraft, subtotal, total_amount: total };
  };

  const setField = (key: keyof ExpenseDraft, value: string | number) =>
    setDraft((prev) => syncTotals({ ...prev, [key]: value } as ExpenseDraft));

  useEffect(() => {
    if (analysis) setDraft((prev) => syncTotals(prev));
  }, [analysis]);

  return (
    <>
      <style>{`
        .review-scroll {
          scrollbar-width: none;
          -ms-overflow-style: none;
          scroll-behavior: smooth;
        }

        .review-scroll::-webkit-scrollbar {
          width: 0px;
          height: 0px;
        }

        .review-scroll:hover {
          scrollbar-width: thin;
          scrollbar-color: rgba(120, 130, 150, 0.55) transparent;
        }

        .review-scroll:hover::-webkit-scrollbar {
          width: 6px;
        }

        .review-scroll:hover::-webkit-scrollbar-track {
          background: transparent;
        }

        .review-scroll:hover::-webkit-scrollbar-thumb {
          background: rgba(120, 130, 150, 0.45);
          border-radius: 9999px;
          border: 1px solid transparent;
          background-clip: padding-box;
        }

        .review-scroll:hover::-webkit-scrollbar-thumb:hover {
          background: rgba(120, 130, 150, 0.7);
          background-clip: padding-box;
        }
      `}</style>

      <div className="mx-auto max-w-7xl px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="mb-6 flex flex-wrap items-center justify-between gap-4"
        >
          <div>
            <div className="inline-flex rounded-full border border-[var(--border)] bg-[var(--surface-strong)] px-3 py-1 text-xs font-medium tracking-[0.18em] text-[var(--muted)]">
              Upload and Review
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Badge label={`DB ${health?.database_connected ? 'Connected' : 'Disconnected'}`} ok={!!health?.database_connected} />
            <Badge
              label={`OpenRouter ${health?.openrouter_configured ? 'Configured' : 'Disconnected'}`}
              ok={!!health?.openrouter_configured}
            />
            <Button variant="secondary" onClick={() => void loadHealth()} loading={healthLoading}>
              Refresh status
            </Button>
          </div>
        </motion.div>

        <div className="grid gap-6 lg:grid-cols-[1.02fr_1.48fr]">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.04 }}
            className="min-w-0"
          >
            <Card className="overflow-hidden p-0">
              <div className="border-b border-[var(--border)] bg-[var(--surface-strong)] px-6 py-5">
                <h2 className="text-xl font-semibold">Drop your file here</h2>
              </div>

              <div className="p-6">
                <div
                  onClick={onBrowse}
                  onDragOver={onDragOver}
                  onDragEnter={onDragEnter}
                  onDragLeave={onDragLeave}
                  onDrop={onDrop}
                  className={`group cursor-pointer rounded-[28px] border-2 border-dashed p-6 transition-all duration-300 ${
                    dragActive
                      ? 'border-[var(--text)] bg-[var(--surface)] shadow-lg'
                      : 'border-[var(--border)] bg-[var(--surface-strong)] hover:bg-[var(--surface)]'
                  }`}
                >
                  <motion.div
                    animate={{ scale: dragActive ? 1.02 : 1 }}
                    transition={{ type: 'spring', stiffness: 260, damping: 20 }}
                    className="flex flex-col items-center text-center"
                  >
                    <div className="flex h-16 w-16 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface)]">
                      <UploadIcon className="h-7 w-7 text-[var(--text)]" />
                    </div>
                    <div className="mt-4 text-lg font-semibold">
                      {dragActive ? 'Release to upload' : 'Drag & drop or click to browse'}
                    </div>
                    <div className="mt-2 max-w-md text-sm leading-6 text-[var(--muted)]">
                      PDF, CSV, PNG, JPG, JPEG, WEBP, BMP, or TIFF
                    </div>
                  </motion.div>
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.csv,.png,.jpg,.jpeg,.webp,.bmp,.tiff"
                  onChange={onPickFile}
                  className="hidden"
                />

                <div className="mt-4 flex flex-wrap gap-2">
                  {quickTypes.map(({ label, icon: Icon }) => (
                    <span
                      key={label}
                      className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-medium text-[var(--text)]"
                    >
                      <Icon className="h-3.5 w-3.5 text-[var(--muted)]" />
                      {label}
                    </span>
                  ))}
                </div>

                {selectedFile && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="text-sm text-[var(--muted)]">Selected file</div>
                        <div className="mt-1 truncate font-medium">{selectedFile.name}</div>
                        <div className="mt-1 text-xs text-[var(--muted)]">
                          {Math.max(1, Math.round(selectedFile.size / 1024))} KB
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          handleFile(null);
                          if (fileInputRef.current) fileInputRef.current.value = '';
                        }}
                        className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600 transition hover:bg-rose-100 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                      >
                        Remove
                      </button>
                    </div>
                  </motion.div>
                )}

                {message && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-4 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-200"
                  >
                    {message}
                  </motion.div>
                )}

                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-700 dark:text-rose-200"
                  >
                    {error}
                  </motion.div>
                )}

                <div className="mt-5 flex flex-wrap gap-3">
                  <Button loading={analyzing} onClick={analyze}>
                    Analyze file
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setSelectedFile(null);
                      setAnalysis(null);
                      setDraft(emptyDraft);
                      setMessage(null);
                      setError(null);
                      if (fileInputRef.current) fileInputRef.current.value = '';
                    }}
                  >
                    Reset
                  </Button>
                </div>
              </div>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.08 }}
            className="min-w-0"
          >
            <Card className="max-h-[calc(100vh-160px)] overflow-y-auto p-0 review-scroll">
              <div className="border-b border-[var(--border)] bg-[var(--surface-strong)] px-6 py-5">
                <h2 className="text-xl font-semibold">Review the extracted details</h2>
                <p className="mt-1 text-sm text-[var(--muted)]">Edit any field before saving to your dashboard.</p>
              </div>

              <div className="space-y-6 p-6">
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Vendor Name" value={draft.vendor_name || ''} onChange={(v) => setField('vendor_name', v)} />
                  <Field
                    label="Invoice / Receipt No"
                    value={draft.invoice_number || ''}
                    onChange={(v) => setField('invoice_number', v)}
                  />
                  <Field label="Date" type="date" value={draft.date || ''} onChange={(v) => setField('date', v)} />
                  <Field label="Time" value={draft.time || ''} onChange={(v) => setField('time', v)} placeholder="14:30" />
                  <Field label="Phone" value={draft.phone || ''} onChange={(v) => setField('phone', v)} />
                  <Field label="Email" value={draft.email || ''} onChange={(v) => setField('email', v)} />
                  <div className="md:col-span-2">
                    <Field label="Address" textarea value={draft.address || ''} onChange={(v) => setField('address', v)} />
                  </div>
                  <Field
                    label="Payment Method"
                    value={draft.payment_method || ''}
                    onChange={(v) => setField('payment_method', v)}
                  />
                  <Field
                    label="Category"
                    select
                    value={draft.category || 'OTHER'}
                    onChange={(v) => setField('category', v.toUpperCase())}
                    options={CATEGORY_OPTIONS}
                  />
                  <Field label="Subtotal" value={draft.subtotal} onChange={(v) => setField('subtotal', safeNumber(v))} />
                  <Field
                    label="Total Amount"
                    value={draft.total_amount}
                    onChange={(v) => setField('total_amount', safeNumber(v))}
                  />
                  <Field label="CGST" value={draft.cgst} onChange={(v) => setField('cgst', safeNumber(v))} />
                  <Field label="SGST" value={draft.sgst} onChange={(v) => setField('sgst', safeNumber(v))} />
                  <Field label="IGST" value={draft.igst} onChange={(v) => setField('igst', safeNumber(v))} />
                  <Field label="Discount" value={draft.discount} onChange={(v) => setField('discount', safeNumber(v))} />
                </div>

                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-lg font-medium">Items</h3>
                    <Button variant="secondary" onClick={addItem}>
                      Add item
                    </Button>
                  </div>

                  <div className="space-y-3">
                    {draft.items.map((item, index) => (
                      <motion.div
                        key={index}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] p-4"
                      >
                        <div className="grid gap-3 md:grid-cols-4">
                          <input
                            value={item.item_name}
                            onChange={(e) => updateItem(index, 'item_name', e.target.value)}
                            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 outline-none md:col-span-2"
                            placeholder="Item name"
                          />
                          <input
                            type="text"
                            inputMode="decimal"
                            value={item.quantity}
                            onChange={(e) => updateItem(index, 'quantity', safeNumber(e.target.value))}
                            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 outline-none"
                            placeholder="Qty"
                          />
                          <input
                            type="text"
                            inputMode="decimal"
                            value={item.unit_price}
                            onChange={(e) => updateItem(index, 'unit_price', safeNumber(e.target.value))}
                            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 outline-none"
                            placeholder="Unit price"
                          />
                        </div>

                        <div className="mt-3 flex items-center justify-between gap-3">
                          <select
                            value={item.item_category || 'OTHER'}
                            onChange={(e) => updateItem(index, 'item_category', e.target.value)}
                            className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 outline-none"
                          >
                            {CATEGORY_OPTIONS.map((cat) => (
                              <option key={cat} value={cat}>
                                {cat}
                              </option>
                            ))}
                          </select>

                          <button
                            type="button"
                            onClick={() => removeItem(index)}
                            className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-600 transition hover:bg-rose-100 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                          >
                            Remove
                          </button>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-end">
                  <Button
                    loading={saving}
                    onClick={saveDraft}
                    disabled={!canSave}
                    className="bg-emerald-400 text-slate-950"
                  >
                    Save changes
                  </Button>
                </div>
              </div>
            </Card>
          </motion.div>
        </div>
      </div>
    </>
  );
}

function Badge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm">
      <span className={`mr-2 inline-block h-2.5 w-2.5 rounded-full ${ok ? 'bg-emerald-400' : 'bg-rose-400'}`} />
      {label}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = 'text',
  textarea = false,
  select = false,
  options = [],
  placeholder,
}: {
  label: string;
  value: any;
  onChange: (v: any) => void;
  type?: string;
  textarea?: boolean;
  select?: boolean;
  options?: string[];
  placeholder?: string;
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm text-[var(--muted)]">{label}</span>
      {textarea ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="min-h-[92px] w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none"
          placeholder={placeholder}
        />
      ) : select ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none"
        >
          {options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      ) : (
        <input
          type={type}
          inputMode={type === 'date' ? undefined : 'decimal'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 outline-none"
          placeholder={placeholder}
        />
      )}
    </label>
  );
}