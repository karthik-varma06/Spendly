import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import ChatDock from '../components/ChatDock';
import { RefreshCw, Sparkles, Wallet, TrendingUp, Package2 } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { api, DashboardSummary, HealthStatus, Budget } from '../lib/api';
import { useAuth } from '../context/AuthContext';

function money(value: number) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function count(value: number) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(Number(value || 0));
}

function formatTinyPercent(value: number) {
  if (!Number.isFinite(value) || value <= 0) return '<0.1%';
  if (value < 0.1) return '<0.1%';
  if (value >= 100) return '100%';
  return `${Math.round(value * 10) / 10}%`;
}

function pct(part: number, total: number) {
  if (!total || !Number.isFinite(part) || !Number.isFinite(total)) return 0;
  return (part / total) * 100;
}

const CHART_AXIS_COLOR = 'rgba(51, 65, 85, 0.95)';
const CHART_TICK_COLOR = 'rgba(71, 85, 105, 0.95)';
const CHART_GRID_COLOR = 'rgba(100, 116, 139, 0.42)';
const CHART_CURSOR_COLOR = 'rgba(148, 163, 184, 0.12)';

const pageStagger = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.04,
    },
  },
};

const cardRise = {
  hidden: { opacity: 0, y: 18, scale: 0.985 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] },
  },
};

const chartReveal = {
  hidden: { opacity: 0, y: 18, scale: 0.98 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.55, ease: [0.16, 1, 0.3, 1] },
  },
};

function TooltipCard({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  const amount = Number(payload[0].value || p?.value || p?.amount || 0);

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 shadow-2xl">
      <div className="text-xs text-[var(--muted)]">{label || p?.name || p?.month}</div>
      <div className="mt-1 font-semibold">{money(amount)}</div>
      {typeof p?.share === 'number' && (
        <div className="mt-1 text-xs text-[var(--muted)]">{formatTinyPercent(p.share)} of total</div>
      )}
      {p?.avg != null && <div className="mt-1 text-xs text-[var(--muted)]">Average {money(Number(p.avg || 0))}</div>}
    </div>
  );
}

type BudgetView = Budget & {
  spent_amount?: number;
  progress_percent?: number;
  spent?: number;
  progress?: number;
};

function ChartShell({
  title,
  children,
  className = '',
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={`overflow-hidden p-5 ${className}`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="font-semibold">{title}</div>
      </div>
      <div className="min-w-0">{children}</div>
    </Card>
  );
}

function CategoryLegendItem({
  name,
  amount,
  share,
  color,
  index,
}: {
  name: string;
  amount: number;
  share: number;
  color: string;
  index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 10 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, amount: 0.35 }}
      transition={{ duration: 0.35, delay: Math.min(index * 0.04, 0.24), ease: [0.16, 1, 0.3, 1] }}
      className="flex items-start gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
    >
      <span className="mt-1 h-3.5 w-3.5 shrink-0 rounded-sm border border-black/10" style={{ backgroundColor: color }} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0 truncate text-sm font-medium">{name}</div>
          <div className="shrink-0 text-sm font-semibold">{money(amount)}</div>
        </div>
        <div className="mt-1 text-xs text-[var(--muted)]">{formatTinyPercent(share)} of total</div>
      </div>
    </motion.div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [budgets, setBudgets] = useState<BudgetView[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [sum, bud, h] = await Promise.all([
        api.get('/dashboard/summary'),
        api.get('/budgets').catch(() => ({ data: [] })),
        api.get('/health').catch(() => ({ data: null })),
      ]);
      setSummary(sum.data);
      setBudgets(Array.isArray(bud.data) ? bud.data : []);
      setHealth(h.data || null);
    } catch {
      setSummary({
        monthly_expense: 0,
        yearly_expense: 0,
        savings: 0,
        top_items: [],
        top_merchants: [],
        category_breakdown: [],
        spending_trends: [],
        income_vs_expense: { income: 0, expense: 0 },
        most_expensive_month: null,
      });
      setBudgets([]);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAll();

    const refresh = () => void loadAll();
    window.addEventListener('notifications:refresh', refresh);
    return () => window.removeEventListener('notifications:refresh', refresh);
  }, []);

  const categoryColors = ['#60a5fa', '#34d399', '#f472b6', '#f59e0b', '#a78bfa', '#22c55e', '#f87171', '#38bdf8', '#fb7185', '#c084fc'];
  const pieData = summary?.category_breakdown || [];
  const trendData = summary?.spending_trends || [];
  const merchantData = summary?.top_merchants || [];
  const itemData = summary?.top_items || [];

  const spendVsIncome = [
    { name: 'Income', amount: summary?.income_vs_expense?.income || 0 },
    { name: 'Expense', amount: summary?.income_vs_expense?.expense || 0 },
  ];

  const totalCategorySpend = pieData.reduce((sum, x) => sum + Number(x.value || 0), 0);
  const categorySpendMap = Object.fromEntries(pieData.map((c) => [String(c.name).toUpperCase(), Number(c.value || 0)]));

  const budgetInsights = useMemo(() => {
    return budgets.map((b) => {
      const limit = Number(b.budget_limit || 0);
      const apiSpent = Number(b.spent_amount || 0);
      const liveSpent = Number(categorySpendMap[String(b.category_name || '').toUpperCase()] ?? 0) || apiSpent || 0;

      const rawProgress = Number(b.progress_percent ?? b.progress ?? 0) || (limit > 0 ? (liveSpent / limit) * 100 : 0);
      const progress = limit > 0 ? Math.min(100, Math.max(0, rawProgress)) : 0;

      return {
        ...b,
        budget_limit: limit,
        spent_amount: liveSpent,
        progress_percent: progress,
        progress,
      };
    });
  }, [budgets, categorySpendMap]);

  return (
    <>
      <style>{`
        .scrollbar-hidden-hover {
          scrollbar-width: none;
          -ms-overflow-style: none;
        }

        .scrollbar-hidden-hover::-webkit-scrollbar {
          width: 0px;
          height: 0px;
        }

        .scrollbar-hidden-hover:hover {
          scrollbar-width: thin;
          scrollbar-color: rgba(148, 163, 184, 0.55) transparent;
        }

        .scrollbar-hidden-hover:hover::-webkit-scrollbar {
          width: 6px;
        }

        .scrollbar-hidden-hover:hover::-webkit-scrollbar-track {
          background: transparent;
        }

        .scrollbar-hidden-hover:hover::-webkit-scrollbar-thumb {
          background: rgba(148, 163, 184, 0.45);
          border-radius: 9999px;
        }

        .scrollbar-hidden-hover:hover::-webkit-scrollbar-thumb:hover {
          background: rgba(148, 163, 184, 0.75);
        }
      `}</style>

      <motion.div
        className="mx-auto max-w-7xl px-4 py-6"
        variants={pageStagger}
        initial="hidden"
        animate="show"
      >
        <motion.div
          variants={cardRise}
          className="mb-6 flex flex-wrap items-center justify-between gap-4"
        >
          <div>
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <Sparkles className="h-4 w-4" />
              <span>Hi 👋 {user?.full_name || 'there'}</span>
            </div>
            <h1 className="mt-1 text-3xl font-semibold">Dashboard</h1>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge label="DB" ok={!!health?.database_connected} />
            <StatusBadge label="OpenRouter" ok={!!health?.openrouter_configured} />
            <Button variant="secondary" onClick={loadAll} loading={loading}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </motion.div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <motion.div variants={cardRise}>
            <MetricCard label="Monthly expense" value={money(summary?.monthly_expense || 0)} icon={Wallet} />
          </motion.div>
          <motion.div variants={cardRise}>
            <MetricCard label="Yearly expense" value={money(summary?.yearly_expense || 0)} icon={TrendingUp} />
          </motion.div>
          <motion.div variants={cardRise}>
            <MetricCard label="Savings" value={money(summary?.savings || 0)} icon={Sparkles} />
          </motion.div>
          <motion.div variants={cardRise}>
            <MetricCard label="Top items" value={count(itemData.length)} icon={Package2} compact />
          </motion.div>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-2">
          <motion.div variants={chartReveal}>
            <ChartShell title="Income vs Expense">
              <div className="h-[360px] min-h-0 w-full min-w-0 overflow-hidden">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={spendVsIncome}
                    margin={{ top: 8, right: 12, left: 0, bottom: 8 }}
                  >
                    <defs>
                      <linearGradient id="incomeBar" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#22c55e" stopOpacity={0.95} />
                        <stop offset="100%" stopColor="#22c55e" stopOpacity={0.25} />
                      </linearGradient>
                      <linearGradient id="expenseBar" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#60a5fa" stopOpacity={0.95} />
                        <stop offset="100%" stopColor="#60a5fa" stopOpacity={0.25} />
                      </linearGradient>
                    </defs>

                    <CartesianGrid strokeDasharray="4 4" stroke={CHART_GRID_COLOR} opacity={0.95} vertical={false} />
                    <XAxis
                      dataKey="name"
                      stroke={CHART_AXIS_COLOR}
                      tick={{ fill: CHART_TICK_COLOR, fontSize: 12, fontWeight: 500 }}
                      axisLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                      tickLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                    />
                    <YAxis
                      stroke={CHART_AXIS_COLOR}
                      tick={{ fill: CHART_TICK_COLOR, fontSize: 12, fontWeight: 500 }}
                      axisLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                      tickLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                    />
                    <Tooltip content={<TooltipCard />} cursor={{ fill: CHART_CURSOR_COLOR }} />
                    <Bar
                      dataKey="amount"
                      radius={[14, 14, 0, 0]}
                      barSize={70}
                      isAnimationActive
                      animationBegin={150}
                      animationDuration={1100}
                      animationEasing="ease-out"
                    >
                      {spendVsIncome.map((entry, index) => (
                        <Cell key={entry.name} fill={index === 0 ? 'url(#incomeBar)' : 'url(#expenseBar)'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartShell>
          </motion.div>

          <motion.div variants={chartReveal}>
            <ChartShell title="Category breakdown">
              <div className="grid gap-4 lg:grid-cols-[1.08fr_0.92fr]">
                <div className="h-[360px] min-h-0 min-w-0 overflow-hidden">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData.map((d) => ({
                          ...d,
                          share: totalCategorySpend > 0 ? pct(Number(d.value || 0), totalCategorySpend) : 0,
                        }))}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={72}
                        outerRadius={118}
                        paddingAngle={4}
                        stroke="none"
                        startAngle={90}
                        endAngle={-270}
                        isAnimationActive
                        animationBegin={120}
                        animationDuration={1200}
                        animationEasing="ease-out"
                      >
                        {pieData.map((_, idx) => (
                          <Cell key={idx} fill={categoryColors[idx % categoryColors.length]} />
                        ))}
                      </Pie>
                      <Tooltip content={<TooltipCard />} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>

                <div className="max-h-[360px] overflow-y-auto pr-1 scrollbar-hidden-hover">
                  <div className="space-y-2">
                    {pieData.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-[var(--border)] p-4 text-sm text-[var(--muted)]">
                        No category data yet.
                      </div>
                    ) : (
                      pieData.map((item, idx) => {
                        const amount = Number(item.value || 0);
                        const share = totalCategorySpend > 0 ? pct(amount, totalCategorySpend) : 0;
                        return (
                          <CategoryLegendItem
                            key={item.name}
                            index={idx}
                            name={String(item.name)}
                            amount={amount}
                            share={share}
                            color={categoryColors[idx % categoryColors.length]}
                          />
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            </ChartShell>
          </motion.div>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-2">
          <motion.div variants={chartReveal}>
            <ChartShell title="Spending trends">
              <div className="h-[360px] min-h-0 w-full min-w-0 overflow-hidden">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trendData} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
                    <defs>
                      <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.45} />
                        <stop offset="100%" stopColor="#a78bfa" stopOpacity={0.04} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 4" stroke={CHART_GRID_COLOR} opacity={0.95} vertical={false} />
                    <XAxis
                      dataKey="month"
                      stroke={CHART_AXIS_COLOR}
                      tick={{ fill: CHART_TICK_COLOR, fontSize: 12, fontWeight: 500 }}
                      axisLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                      tickLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                    />
                    <YAxis
                      stroke={CHART_AXIS_COLOR}
                      tick={{ fill: CHART_TICK_COLOR, fontSize: 12, fontWeight: 500 }}
                      axisLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                      tickLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                    />
                    <Tooltip content={<TooltipCard />} cursor={{ fill: CHART_CURSOR_COLOR }} />
                    <Area
                      type="monotone"
                      dataKey="amount"
                      stroke="#a78bfa"
                      strokeWidth={3}
                      fill="url(#trendFill)"
                      isAnimationActive
                      animationBegin={150}
                      animationDuration={1100}
                      animationEasing="ease-out"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </ChartShell>
          </motion.div>

          <motion.div variants={chartReveal}>
            <ChartShell title="Top merchants">
              <div className="h-[360px] min-h-0 w-full min-w-0 overflow-hidden">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={merchantData}
                    layout="vertical"
                    margin={{ top: 8, right: 16, left: 24, bottom: 8 }}
                  >
                    <CartesianGrid strokeDasharray="4 4" stroke={CHART_GRID_COLOR} opacity={0.95} horizontal={false} />
                    <XAxis
                      type="number"
                      stroke={CHART_AXIS_COLOR}
                      tick={{ fill: CHART_TICK_COLOR, fontSize: 12, fontWeight: 500 }}
                      axisLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                      tickLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      stroke={CHART_AXIS_COLOR}
                      tick={{ fill: CHART_TICK_COLOR, fontSize: 12, fontWeight: 500 }}
                      axisLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                      tickLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                      width={120}
                    />
                    <Tooltip content={<TooltipCard />} cursor={{ fill: CHART_CURSOR_COLOR }} />
                    <Bar
                      dataKey="value"
                      radius={[0, 14, 14, 0]}
                      barSize={18}
                      isAnimationActive
                      animationBegin={120}
                      animationDuration={1000}
                      animationEasing="ease-out"
                    >
                      {merchantData.map((_: any, idx: number) => (
                        <Cell key={idx} fill={categoryColors[idx % categoryColors.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartShell>
          </motion.div>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-2">
          <motion.div variants={chartReveal}>
            <ChartShell title="Most spent items">
              <div className="h-[360px] min-h-0 w-full min-w-0 overflow-hidden">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={itemData}
                    layout="vertical"
                    margin={{ top: 8, right: 16, left: 24, bottom: 8 }}
                  >
                    <CartesianGrid strokeDasharray="4 4" stroke={CHART_GRID_COLOR} opacity={0.95} horizontal={false} />
                    <XAxis
                      type="number"
                      stroke={CHART_AXIS_COLOR}
                      tick={{ fill: CHART_TICK_COLOR, fontSize: 12, fontWeight: 500 }}
                      axisLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                      tickLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      stroke={CHART_AXIS_COLOR}
                      tick={{ fill: CHART_TICK_COLOR, fontSize: 12, fontWeight: 500 }}
                      axisLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                      tickLine={{ stroke: CHART_AXIS_COLOR, strokeWidth: 1 }}
                      width={130}
                    />
                    <Tooltip content={<TooltipCard />} cursor={{ fill: CHART_CURSOR_COLOR }} />
                    <Bar
                      dataKey="value"
                      radius={[0, 14, 14, 0]}
                      barSize={18}
                      isAnimationActive
                      animationBegin={120}
                      animationDuration={1000}
                      animationEasing="ease-out"
                    >
                      {itemData.map((_: any, idx: number) => (
                        <Cell key={idx} fill={categoryColors[idx % categoryColors.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartShell>
          </motion.div>

          <motion.div variants={chartReveal}>
            <Card className="overflow-hidden p-5">
              <div className="mb-3 font-semibold">Budget tracker</div>
              <div className="max-h-[460px] space-y-4 overflow-y-auto pr-2 scrollbar-hidden-hover">
                {budgetInsights.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-[var(--border)] p-4 text-sm text-[var(--muted)]">
                    No budgets set yet. Add them in Settings.
                  </div>
                ) : (
                  budgetInsights.map((b) => {
                    const limit = Number(b.budget_limit || 0);
                    const spent = Number(b.spent_amount || 0);
                    const safeProgress = limit > 0 ? Math.min(100, Math.max(0, (spent / limit) * 100)) : 0;
                    const displayProgress = formatTinyPercent(safeProgress);
                    const danger = safeProgress >= 100;
                    const warn = safeProgress >= 80 && safeProgress < 100;

                    return (
                      <motion.div
                        key={b.id}
                        initial={{ opacity: 0, y: 12 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true, amount: 0.25 }}
                        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                        className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] p-4"
                      >
                        <div className="flex items-center justify-between gap-3 text-sm">
                          <div className="min-w-0 truncate font-medium">{b.category_name}</div>
                          <div className="shrink-0 text-[var(--muted)]">{labelPeriod(b.period)}</div>
                        </div>

                        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--muted)]">
                          <span className="min-w-0 truncate">Spent {money(spent)}</span>
                          <span className="shrink-0">Budget {money(limit)}</span>
                        </div>

                        <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
                          <motion.div
                            initial={{ width: 0 }}
                            whileInView={{ width: `${Math.max(2, safeProgress)}%` }}
                            viewport={{ once: true, amount: 0.25 }}
                            transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
                            className={`h-full rounded-full ${
                              danger ? 'bg-rose-500' : warn ? 'bg-amber-400' : 'bg-emerald-400'
                            }`}
                          />
                        </div>
                        <div className="mt-2 text-xs text-[var(--muted)]">{displayProgress} used</div>
                      </motion.div>
                    );
                  })
                )}
              </div>
            </Card>
          </motion.div>
        </div>

        <div className="mt-6 grid gap-4">
          <motion.div variants={cardRise}>
            <Card className="p-5">
              <div className="mb-2 font-semibold">Most expensive month</div>
              <div className="text-sm text-[var(--muted)]">
                {summary?.most_expensive_month
                  ? `${summary.most_expensive_month.month} — ${money(summary.most_expensive_month.amount)}`
                  : 'No data yet'}
              </div>
            </Card>
          </motion.div>
        </div>

        <ChatDock />
      </motion.div>
    </>
  );
}

function MetricCard({
  label,
  value,
  icon: Icon,
  compact = false,
}: {
  label: string;
  value: string;
  icon: any;
  compact?: boolean;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm text-[var(--muted)]">{label}</div>
          <div className={`mt-2 ${compact ? 'text-2xl' : 'text-3xl'} font-semibold`}>{value}</div>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] p-3">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </Card>
  );
}

function StatusBadge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm">
      <span className={`mr-2 inline-block h-2.5 w-2.5 rounded-full ${ok ? 'bg-emerald-400' : 'bg-rose-400'}`} />
      {label} {ok ? 'Connected' : 'Disconnected'}
    </div>
  );
}

function labelPeriod(period: string) {
  if (period === 'weekly') return 'Weekly';
  if (period === 'monthly') return 'Monthly';
  return 'Custom';
}