import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Bot, RotateCcw, Send, Sparkles, X } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../context/AuthContext';

type ChatRole = 'user' | 'assistant';

type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  sql?: string | null;
  createdAt: number;
};

const SUGGESTION_POOL = [
  'Tell me the biggest reason my spending went up.',
  'Which category is overspending right now?',
  'Show me the top 3 merchants by spend.',
  'How much did I spend on food this week?',
  'Give me a small suggestion to save more this month.',
  'What was my most expensive day?',
  'Which item names appear most often in my expenses?',
  'Compare my income and expenses.',
  'Show me a SQL query for monthly category totals.',
  'How close am I to my FOOD budget?',
  'Which merchant is taking most of my money?',
  'Tell me a quick budget health check.',
  'What should I reduce first if I want to save more?',
  'Show a short trend summary for the last few months.',
  'Explain why my budget is over.',
];

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function shufflePick<T>(items: T[], count: number): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy.slice(0, count);
}

function formatTime(ts: number) {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(ts));
}

function renderContent(text: string) {
  return text.split('\n').map((line, idx, arr) => (
    <span key={`${idx}-${line}`}>
      {line}
      {idx < arr.length - 1 ? <br /> : null}
    </span>
  ));
}

function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface-strong)] text-[var(--text)] shadow-sm">
        <Bot className="h-4 w-4" />
      </div>

      <div className="rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 shadow-sm">
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              animate={{ y: [0, -6, 0], opacity: [0.55, 1, 0.55] }}
              transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.14, ease: 'easeInOut' }}
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: 'var(--text)' }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function ChatDock() {
  const { user } = useAuth();
  const storageKey = useMemo(() => `aigeek-chat:${user?.id || 'guest'}`, [user?.id]);

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [quickSuggestions, setQuickSuggestions] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const pickSuggestions = () => shufflePick(SUGGESTION_POOL, 3);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as ChatMessage[];
        if (Array.isArray(parsed)) setMessages(parsed);
      }
    } catch {
      setMessages([]);
    }
    setQuickSuggestions(pickSuggestions());
  }, [storageKey]);

  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(messages));
      setSaved(true);
      const t = window.setTimeout(() => setSaved(false), 700);
      return () => window.clearTimeout(t);
    } catch {
      // ignore localStorage errors
    }
  }, [messages, storageKey]);

  useEffect(() => {
    if (open && messages.length === 0) {
      setQuickSuggestions(pickSuggestions());
    }
  }, [open, messages.length]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [messages, loading, open]);

  const resetChat = () => {
    setMessages([]);
    setInput('');
    setQuickSuggestions(pickSuggestions());
    try {
      window.localStorage.removeItem(storageKey);
    } catch {
      // ignore
    }
    textareaRef.current?.focus();
  };

  const sendMessage = async (messageText?: string) => {
    const text = (messageText ?? input).trim();
    if (!text || loading) return;

    const userMessage: ChatMessage = {
      id: makeId(),
      role: 'user',
      content: text,
      createdAt: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.post('/chat', { message: text });
      const answer = String(res.data?.answer || '').trim() || 'I could not generate a response right now.';
      const sql = res.data?.sql ?? null;

      const botMessage: ChatMessage = {
        id: makeId(),
        role: 'assistant',
        content: answer,
        sql,
        createdAt: Date.now(),
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (err: any) {
      const fallback = err?.response?.data?.detail || err?.message || 'I could not reach the assistant right now.';
      setMessages((prev) => [
        ...prev,
        {
          id: makeId(),
          role: 'assistant',
          content: fallback,
          createdAt: Date.now(),
        },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => textareaRef.current?.focus(), 0);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void sendMessage();
    }
  };

  return (
    <>
      <motion.button
        whileHover={{ scale: 1.06 }}
        whileTap={{ scale: 0.96 }}
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--text)] text-[var(--bg)] shadow-2xl"
        aria-label="Open AI chat"
      >
        <Bot className="h-6 w-6" />
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 14, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 14, scale: 0.98 }}
            className="fixed inset-x-4 bottom-4 top-4 z-50 mx-auto flex w-[min(1100px,calc(100vw-32px))] flex-col overflow-hidden rounded-[28px] border border-[var(--border)] bg-[var(--surface)] shadow-2xl backdrop-blur-xl md:inset-auto md:right-6 md:bottom-6 md:h-[82vh]"
          >
            <div className="flex items-center justify-between border-b border-[var(--border)] bg-gradient-to-r from-[var(--text)] to-[#0f172a] px-5 py-4 text-[var(--bg)]">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-white/10">
                  <Bot className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-sm font-semibold">AI Finance Assistant</div>
                  <div className="text-xs text-white/70">Chat, ask for SQL, summaries, trends, and spending reasons</div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={resetChat}
                  className="inline-flex h-10 items-center gap-2 rounded-2xl border border-white/15 bg-white/10 px-3 text-sm font-medium text-white transition hover:bg-white/15"
                >
                  <RotateCcw className="h-4 w-4" />
                  Reset
                </button>
                <button
                  onClick={() => setOpen(false)}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-white/15 bg-white/10 text-white transition hover:bg-white/15"
                  aria-label="Close chat"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 md:px-6">
              {messages.length === 0 && !loading && (
                <div className="mb-5">
                  <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--muted)]">
                    <Sparkles className="h-4 w-4" />
                    Quick suggestions
                    {saved && <span className="ml-1 text-xs font-normal text-[var(--muted)]/80">(saved)</span>}
                  </div>

                  <div className="grid gap-3 md:grid-cols-3">
                    {quickSuggestions.map((suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() => {
                          setInput(suggestion);
                          textareaRef.current?.focus();
                        }}
                        className="rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)] p-4 text-left text-sm leading-6 text-[var(--text)] transition hover:-translate-y-0.5 hover:bg-[var(--surface)] hover:shadow-md"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-4">
                <AnimatePresence initial={false}>
                  {messages.map((msg) => (
                    <motion.div
                      key={msg.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 8 }}
                      className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div className={`flex max-w-[88%] gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                        <div
                          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border ${
                            msg.role === 'user'
                              ? 'border-transparent bg-[var(--text)] text-[var(--bg)]'
                              : 'border-[var(--border)] bg-[var(--surface-strong)] text-[var(--text)]'
                          }`}
                        >
                          {msg.role === 'user' ? 'Y' : <Bot className="h-4 w-4" />}
                        </div>

                        <div
                          className={`rounded-[28px] px-4 py-3 shadow-sm ${
                            msg.role === 'user'
                              ? 'bg-[var(--text)] text-[var(--bg)]'
                              : 'border border-[var(--border)] bg-[var(--surface-strong)] text-[var(--text)]'
                          }`}
                        >
                          <div className="whitespace-pre-wrap text-sm leading-7">{renderContent(msg.content)}</div>
                          <div className={`mt-2 text-[11px] ${msg.role === 'user' ? 'text-white/70' : 'text-[var(--muted)]'}`}>
                            {formatTime(msg.createdAt)}
                          </div>
                    
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>

                {loading && <TypingIndicator />}
              </div>
            </div>

            <div className="border-t border-[var(--border)] bg-[var(--surface)] p-4 md:p-5">
              <div className="rounded-[28px] bg-[var(--surface-strong)] p-3 shadow-sm">
                <div className="relative">
                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={onKeyDown}
                    rows={2}
                    placeholder="Ask about budgets, spending, SQL, trends..."
                    className="max-h-32 w-full resize-none rounded-[20px] border-0 bg-transparent px-4 py-3 pr-14 text-sm outline-none placeholder:text-[var(--muted)]"
                  />

                  <button
                    onClick={() => void sendMessage()}
                    disabled={!input.trim() || loading}
                    className="absolute right-3 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-2xl bg-[var(--text)] text-[var(--bg)] transition hover:scale-105 disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label="Send message"
                  >
                    <Send className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div className="mt-2 text-[11px] text-[var(--muted)]">
                Press Enter to send. Shift+Enter for a new line. Your chat stays saved until you reset it.
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
