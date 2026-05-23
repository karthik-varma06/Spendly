import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { api, AuthMeResponse, User } from '../lib/api';

type AuthResponseWithExpiry = AuthMeResponse & {
  expires_at?: string | null;
  session_expires_at?: string | null;
  access_token_expires_at?: string | null;
};

type AuthContextType = {
  user: User | null;
  loading: boolean;
  refreshUser: () => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: User | null) => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const AUTO_REFRESH_MS = 60_000;
const EXPIRY_BUFFER_MS = 5_000;

function parseExpiryMs(value: unknown): number | null {
  if (typeof value !== 'string' || !value.trim()) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

function extractExpiryMs(data: AuthResponseWithExpiry): number | null {
  return (
    parseExpiryMs(data.expires_at) ??
    parseExpiryMs(data.session_expires_at) ??
    parseExpiryMs(data.access_token_expires_at)
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const expiryTimerRef = useRef<number | null>(null);

  const clearExpiryTimer = useCallback(() => {
    if (expiryTimerRef.current !== null) {
      window.clearTimeout(expiryTimerRef.current);
      expiryTimerRef.current = null;
    }
  }, []);

  const logout = useCallback(async () => {
    clearExpiryTimer();

    try {
      await api.post('/auth/logout');
    } catch {
      // Ignore logout failures; local auth state still gets cleared.
    } finally {
      setUser(null);
      setLoading(false);
    }
  }, [clearExpiryTimer]);

  const scheduleExpiryLogout = useCallback(
    (expiresAtMs: number | null) => {
      clearExpiryTimer();

      if (!expiresAtMs) return;

      const delay = expiresAtMs - Date.now() - EXPIRY_BUFFER_MS;

      if (delay <= 0) {
        void logout();
        return;
      }

      expiryTimerRef.current = window.setTimeout(() => {
        void logout();
      }, delay);
    },
    [clearExpiryTimer, logout],
  );

  const refreshUser = useCallback(async () => {
    try {
      const res = await api.get<AuthResponseWithExpiry>('/auth/me');
      const data = res.data;

      if (data.authenticated && data.user) {
        setUser(data.user);
        scheduleExpiryLogout(extractExpiryMs(data));
      } else {
        setUser(null);
        clearExpiryTimer();
      }
    } catch {
      setUser(null);
      clearExpiryTimer();
    } finally {
      setLoading(false);
    }
  }, [clearExpiryTimer, scheduleExpiryLogout]);

  useEffect(() => {
    let mounted = true;

    const runRefresh = () => {
      if (!mounted) return;
      void refreshUser();
    };

    runRefresh();

    const intervalId = window.setInterval(runRefresh, AUTO_REFRESH_MS);

    const onFocus = () => runRefresh();
    const onVisibilityChange = () => {
      if (!document.hidden) runRefresh();
    };

    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      clearExpiryTimer();
    };
  }, [clearExpiryTimer, refreshUser]);

  const value = useMemo(
    () => ({
      user,
      loading,
      refreshUser,
      logout,
      setUser,
    }),
    [user, loading, refreshUser, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}