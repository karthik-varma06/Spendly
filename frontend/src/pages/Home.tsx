import { motion, useReducedMotion } from 'framer-motion';
import {
  ArrowRight,
  Sparkles,
  ShieldCheck,
  ChartColumnBig,
  Bot,
  BellRing,
  Upload,
  FileSearch,
  Banknote,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import Card from '../components/ui/Card';

const features = [
  {
    icon: ChartColumnBig,
    title: 'Smart analytics',
    desc: 'Monthly, yearly, category, merchant, and item insights.',
  },
  {
    icon: Bot,
    title: 'AI assistant',
    desc: 'Ask finance questions in natural language.',
  },
  {
    icon: BellRing,
    title: 'Budget alerts',
    desc: 'Weekly and monthly budget warnings by category.',
  },
  {
    icon: ShieldCheck,
    title: 'Safe save flow',
    desc: 'Review every extraction before it reaches PostgreSQL.',
  },
];

const steps = [
  {
    icon: Upload,
    title: 'Upload bills',
    text: 'Add receipts, invoices, and bills in seconds.',
  },
  {
    icon: FileSearch,
    title: 'Review extraction',
    text: 'Check and edit every field before saving.',
  },
  {
    icon: Banknote,
    title: 'Track clearly',
    text: 'Watch spending, savings, and budget health.',
  },
];

export default function Home() {
  const reduceMotion = useReducedMotion();

  return (
    <div className="relative overflow-hidden">
      <AnimatedBackground reduceMotion={!!reduceMotion} />

      <div className="mx-auto max-w-7xl px-4 py-12 lg:py-16">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="relative z-10"
          >
            

            <h1 className="mt-6 max-w-2xl text-5xl font-semibold leading-tight tracking-tight sm:text-6xl">
              Track receipts, budgets, savings, and AI insights in one place.
            </h1>

            <p className="mt-5 max-w-xl text-lg leading-8 text-[var(--muted)]">
              Upload bills, review extraction, save, and ask the chatbot how your money moved this week or this month.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to="/dashboard"
                className="inline-flex items-center gap-2 rounded-2xl bg-[var(--text)] px-5 py-3.5 font-medium text-[var(--bg)] shadow-lg shadow-black/10 transition duration-200 hover:-translate-y-0.5 hover:opacity-95"
              >
                Let’s get started <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                to="/signup"
                className="inline-flex items-center gap-2 rounded-2xl border border-[var(--border)] bg-[color:var(--surface)]/80 px-5 py-3.5 font-medium text-[var(--text)] shadow-sm backdrop-blur transition duration-200 hover:-translate-y-0.5 hover:bg-[var(--surface-strong)]"
              >
                Create account
              </Link>
            </div>

            <div className="mt-10 grid gap-4 sm:grid-cols-3">
              {steps.map((step, index) => (
                <motion.div
                  key={step.title}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.08 * index, ease: [0.16, 1, 0.3, 1] }}
                  className="rounded-3xl border border-[var(--border)] bg-[color:var(--surface)]/75 p-4 shadow-sm backdrop-blur"
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)]">
                    <step.icon className="h-5 w-5 text-[var(--accent)]" />
                  </div>
                  <h3 className="mt-4 text-sm font-semibold">{step.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{step.text}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
            className="relative z-10"
          >
            <div className="grid gap-4 sm:grid-cols-2">
              {features.map(({ icon: Icon, title, desc }, index) => (
                <motion.div
                  key={title}
                  initial={{ opacity: 0, y: 18, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.5, delay: index * 0.08, ease: [0.16, 1, 0.3, 1] }}
                  whileHover={{ y: -4 }}
                >
                  <Card className="group h-full overflow-hidden border border-[var(--border)] bg-[color:var(--surface)]/80 p-5 shadow-lg shadow-black/5 backdrop-blur transition duration-200">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] transition duration-200 group-hover:scale-105">
                      <Icon className="h-6 w-6 text-[var(--accent)]" />
                    </div>
                    <h3 className="mt-4 text-lg font-semibold">{title}</h3>
                    <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{desc}</p>
                  </Card>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

function AnimatedBackground({ reduceMotion }: { reduceMotion: boolean }) {
  return (
    <div className="pointer-events-none absolute inset-0 -z-0 overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(96,165,250,0.10),_transparent_30%),radial-gradient(circle_at_top_right,_rgba(168,85,247,0.10),_transparent_28%),radial-gradient(circle_at_bottom_left,_rgba(34,197,94,0.08),_transparent_26%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(148,163,184,0.06)_1px,transparent_1px),linear-gradient(to_bottom,rgba(148,163,184,0.06)_1px,transparent_1px)] bg-[size:72px_72px] opacity-50" />

      <motion.div
        animate={
          reduceMotion
            ? undefined
            : {
                x: [0, 20, -10, 0],
                y: [0, -12, 10, 0],
              }
        }
        transition={
          reduceMotion
            ? undefined
            : {
                duration: 14,
                repeat: Infinity,
                ease: 'easeInOut',
              }
        }
        className="absolute left-[-80px] top-24 h-72 w-72 rounded-full bg-[rgba(96,165,250,0.16)] blur-3xl"
      />

      <motion.div
        animate={
          reduceMotion
            ? undefined
            : {
                x: [0, -18, 12, 0],
                y: [0, 16, -8, 0],
              }
        }
        transition={
          reduceMotion
            ? undefined
            : {
                duration: 16,
                repeat: Infinity,
                ease: 'easeInOut',
              }
        }
        className="absolute right-[-70px] top-32 h-80 w-80 rounded-full bg-[rgba(168,85,247,0.14)] blur-3xl"
      />

      <motion.div
        animate={
          reduceMotion
            ? undefined
            : {
                x: [0, 14, -8, 0],
                y: [0, -10, 12, 0],
              }
        }
        transition={
          reduceMotion
            ? undefined
            : {
                duration: 18,
                repeat: Infinity,
                ease: 'easeInOut',
              }
        }
        className="absolute bottom-[-90px] left-1/3 h-96 w-96 rounded-full bg-[rgba(34,197,94,0.10)] blur-3xl"
      />

      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-[var(--bg)] to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-[var(--bg)] to-transparent" />
    </div>
  );
}