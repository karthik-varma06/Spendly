import { AnimatePresence, motion } from 'framer-motion';
import {
  Bell,
  ChevronDown,
  LayoutDashboard,
  LogOut,
  PlusCircle,
  Sparkles,
  Settings,
  Upload,
  UserRound,
} from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, Notification } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import Button from './ui/Button';

export default function Navbar() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [markingRead, setMarkingRead] = useState(false);
  const [loadingNotifications, setLoadingNotifications] = useState(false);

  const navRef = useRef<HTMLDivElement | null>(null);

  const unreadCount = useMemo(() => notifications.filter((n) => !n.is_read).length, [notifications]);

  const loadNotifications = useCallback(async (): Promise<Notification[]> => {
    if (!user) {
      setNotifications([]);
      return [];
    }

    setLoadingNotifications(true);
    try {
      const res = await api.get('/notifications');
      const list = Array.isArray(res.data) ? (res.data as Notification[]) : [];
      setNotifications(list);
      return list;
    } catch {
      setNotifications([]);
      return [];
    } finally {
      setLoadingNotifications(false);
    }
  }, [user]);

  const markAllAsRead = useCallback(
    async (items: Notification[] = notifications) => {
      if (!user) return 0;

      const unreadIds = items.filter((n) => !n.is_read).map((n) => n.id);
      if (unreadIds.length === 0) return 0;

      try {
        setMarkingRead(true);
        await api.post('/notifications/mark-all-read');
        setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
        window.dispatchEvent(new Event('notifications:refresh'));
        return unreadIds.length;
      } catch {
        return 0;
      } finally {
        setMarkingRead(false);
      }
    },
    [notifications, user],
  );

  const syncAndMarkNotifications = useCallback(async () => {
    const latest = await loadNotifications();
    if (latest.some((n) => !n.is_read)) {
      await markAllAsRead(latest);
      await loadNotifications();
    }
  }, [loadNotifications, markAllAsRead]);

  const clearUnreadAndRefresh = useCallback(async () => {
    const latest = notifications.length > 0 ? notifications : await loadNotifications();
    await markAllAsRead(latest);
    await loadNotifications();
  }, [loadNotifications, markAllAsRead, notifications]);

  const handleBellClick = useCallback(() => {
    setShowProfile(false);

    if (showNotifications) {
      setShowNotifications(false);
      return;
    }

    setShowNotifications(true);
    void syncAndMarkNotifications();
  }, [showNotifications, syncAndMarkNotifications]);

  useEffect(() => {
    void loadNotifications();

    const refresh = () => void loadNotifications();
    const interval = window.setInterval(refresh, 30000);

    window.addEventListener('focus', refresh);
    window.addEventListener('notifications:refresh', refresh as EventListener);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener('focus', refresh);
      window.removeEventListener('notifications:refresh', refresh as EventListener);
    };
  }, [loadNotifications]);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (!navRef.current?.contains(e.target as Node)) {
        setShowNotifications(false);
        setShowProfile(false);
      }
    };

    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const navItems = user
    ? [
        { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
        { to: '/upload', label: 'Upload', icon: Upload },
        { to: '/add', label: 'Add', icon: PlusCircle },
      ]
    : [];

  return (
    <header
      ref={navRef}
      className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--surface)] backdrop-blur-xl"
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-4">
          <Link
            to="/"
            className="flex items-center gap-2 rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-2 text-sm font-bold shadow-sm"
          >
            <Sparkles className="h-4 w-4" />
            <span>Spendly</span>
          </Link>

          {user && (
            <nav className="hidden items-center gap-1 md:flex">
              {navItems.map(({ to, label, icon: Icon }) => {
                const active = location.pathname === to;
                return (
                  <Link
                    key={to}
                    to={to}
                    className={`flex items-center gap-2 rounded-2xl px-4 py-2 text-sm transition-all ${
                      active
                        ? 'bg-[var(--text)] text-[var(--bg)] shadow-soft'
                        : 'text-[var(--muted)] hover:bg-[var(--surface-strong)] hover:text-[var(--text)]'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </Link>
                );
              })}
            </nav>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={toggleTheme} className="px-3">
            {theme === 'dark' ? '🌙' : '☀️'}
            <span className="hidden sm:inline">{theme === 'dark' ? 'Dark' : 'Light'}</span>
          </Button>

          {user && (
            <div className="relative">
              <Button variant="ghost" onClick={handleBellClick} className="relative px-3">
                <Bell className="h-4 w-4" />
                {unreadCount > 0 && (
                  <span className="ml-1 rounded-full bg-rose-500 px-2 py-0.5 text-[10px] font-semibold text-white">
                    {unreadCount}
                  </span>
                )}
              </Button>

              <AnimatePresence>
                {showNotifications && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -8, scale: 0.98 }}
                    className="absolute right-0 top-12 w-[360px] rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)] p-4 shadow-2xl"
                  >
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <div>
                        <div className="font-semibold">Notifications</div>
                        <div className="text-xs text-[var(--muted)]">
                          {loadingNotifications ? 'Refreshing…' : `${unreadCount} unread`}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          onClick={clearUnreadAndRefresh}
                          className="h-8 px-3 text-xs"
                          loading={markingRead}
                        >
                          Clear unread
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => setShowNotifications(false)}
                          className="h-8 px-2"
                        >
                          Close
                        </Button>
                      </div>
                    </div>

                    <div className="max-h-80 space-y-3 overflow-y-auto pr-1 overscroll-contain">
                      {notifications.length === 0 ? (
                        <div className="rounded-2xl border border-dashed border-[var(--border)] p-4 text-sm text-[var(--muted)]">
                          No notifications right now.
                        </div>
                      ) : (
                        notifications.map((n) => (
                          <div
                            key={n.id}
                            className={`rounded-2xl border p-3 text-sm transition ${
                              n.is_read
                                ? 'border-[var(--border)] bg-[var(--surface)]'
                                : 'border-emerald-400/30 bg-emerald-400/10'
                            }`}
                          >
                            <div className="flex items-start gap-2">
                              <span
                                className={`mt-1 h-2.5 w-2.5 rounded-full ${
                                  n.is_read ? 'bg-[var(--border)]' : 'bg-emerald-500'
                                }`}
                              />
                              <div className="min-w-0 flex-1">
                                <div className="font-medium">{n.title}</div>
                                <div className="mt-1 text-[var(--muted)]">{n.message}</div>
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          {user ? (
            <div className="relative">
              <Button
                variant="ghost"
                onClick={() => {
                  setShowNotifications(false);
                  setShowProfile((v) => !v);
                }}
                className="rounded-full px-3"
              >
                <CircleUserAvatar name={user.full_name} />
                <span className="ml-2 hidden sm:inline">{user.full_name}</span>
                <ChevronDown className="ml-2 h-4 w-4" />
              </Button>

              <AnimatePresence>
                {showProfile && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -8, scale: 0.98 }}
                    className="absolute right-0 top-12 w-56 rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)] p-2 shadow-2xl"
                  >
                    <button
                      onClick={() => navigate('/profile')}
                      className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm hover:bg-[var(--surface)]"
                    >
                      <UserRound className="h-4 w-4" />
                      Profile
                    </button>
                    <button
                      onClick={() => navigate('/settings')}
                      className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm hover:bg-[var(--surface)]"
                    >
                      <Settings className="h-4 w-4" />
                      Settings
                    </button>
                    <button
                      onClick={logout}
                      className="flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm text-rose-400 hover:bg-rose-500/10"
                    >
                      <LogOut className="h-4 w-4" />
                      Logout
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Button variant="secondary" onClick={() => navigate('/login')}>
                Login
              </Button>
              <Button onClick={() => navigate('/signup')}>Get started</Button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function CircleUserAvatar({ name }: { name: string }) {
  const initials = name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[var(--text)] text-xs font-semibold text-[var(--bg)]">
      {initials}
    </span>
  );
}