import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail, UserRound } from 'lucide-react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import { api, getApiErrorMessage } from '../lib/api';
import { useAuth } from '../context/AuthContext';

const pageVariants = {
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
    transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] },
  },
};

export default function Signup() {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nav = useNavigate();
  const { refreshUser } = useAuth();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (fullName.trim().length < 2) return setError('Full name must be at least 2 characters.');
    if (!email.trim()) return setError('Email is required.');
    if (password.length < 8) return setError('Password must be at least 8 characters.');

    setLoading(true);
    try {
      await api.post('/auth/register', {
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      });
      await refreshUser();
      nav('/dashboard');
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-[calc(100vh-88px)] overflow-hidden px-4 py-8">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(168,85,247,0.16),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(34,197,94,0.12),_transparent_30%)]" />

      <div className="mx-auto grid min-h-[calc(100vh-104px)] max-w-7xl items-center lg:grid-cols-[0.95fr_1.05fr]">
        <div className="hidden pr-6 lg:block">
          <motion.div
            variants={pageVariants}
            initial="hidden"
            animate="show"
            className="space-y-5"
          >
            <motion.div
              variants={itemVariants}
              className="inline-flex rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs font-medium tracking-[0.18em] text-[var(--muted)]"
            >
              Create account
            </motion.div>

            <motion.h1 variants={itemVariants} className="max-w-xl text-5xl font-semibold leading-tight">
              Start tracking expenses with a clean, modern workflow
            </motion.h1>

            <motion.p variants={itemVariants} className="max-w-xl text-base leading-7 text-[var(--muted)]">
              Sign up to upload bills, use AI chat, manage categories, and keep your financial data organized in one place.
            </motion.p>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.985 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          className="mx-auto w-full max-w-md"
        >
          <Card className="overflow-hidden p-0 shadow-2xl">
            

            <div className="px-8 py-7">
              <motion.form
                variants={pageVariants}
                initial="hidden"
                animate="show"
                className="space-y-4"
                onSubmit={submit}
              >
                <motion.div variants={itemVariants} className="space-y-2">
                  <label className="text-sm text-[var(--muted)]">Full name</label>
                  <div className="relative">
                    <UserRound className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
                    <input
                      className="w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] py-3.5 pl-11 pr-4 outline-none transition duration-200 focus:border-[var(--text)] focus:ring-2 focus:ring-[var(--text)]/10"
                      placeholder="Your full name"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      autoComplete="name"
                    />
                  </div>
                </motion.div>

                <motion.div variants={itemVariants} className="space-y-2">
                  <label className="text-sm text-[var(--muted)]">Email</label>
                  <div className="relative">
                    <Mail className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
                    <input
                      className="w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] py-3.5 pl-11 pr-4 outline-none transition duration-200 focus:border-[var(--text)] focus:ring-2 focus:ring-[var(--text)]/10"
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      autoComplete="email"
                    />
                  </div>
                </motion.div>

                <motion.div variants={itemVariants} className="space-y-2">
                  <label className="text-sm text-[var(--muted)]">Password</label>
                  <div className="relative">
                    <LockKeyhole className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
                    <input
                      className="w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] py-3.5 pl-11 pr-12 outline-none transition duration-200 focus:border-[var(--text)] focus:ring-2 focus:ring-[var(--text)]/10"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="At least 8 characters"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 rounded-xl px-2 py-1 text-[var(--muted)] transition hover:bg-[var(--surface)] hover:text-[var(--text)]"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  <p className="text-xs text-[var(--muted)]">Use a strong password to keep your account secure.</p>
                </motion.div>

                {error && (
                  <motion.div
                    variants={itemVariants}
                    className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200"
                  >
                    {error}
                  </motion.div>
                )}

                <motion.div variants={itemVariants} className="pt-1">
                  <Button loading={loading} className="flex w-full items-center justify-center gap-2 py-3.5" type="submit">
                    Sign up
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </motion.div>
              </motion.form>

              <motion.p variants={itemVariants} initial="hidden" animate="show" className="mt-5 text-sm text-[var(--muted)]">
                Already have an account?{' '}
                <Link
                  className="font-medium text-[var(--text)] underline decoration-[var(--border)] underline-offset-4 transition hover:opacity-80"
                  to="/login"
                >
                  Log in
                </Link>
              </motion.p>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}