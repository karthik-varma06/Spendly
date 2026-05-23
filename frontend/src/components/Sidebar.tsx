import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Upload, PlusCircle, Settings, UserRound } from 'lucide-react';

const items = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/upload', label: 'Upload', icon: Upload },
  { to: '/add', label: 'Add Expense', icon: PlusCircle },
  { to: '/profile', label: 'Profile', icon: UserRound },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const location = useLocation();
  return (
    <aside className="hidden w-64 border-r border-white/10 bg-white/5 p-4 lg:block">
      <div className="mb-6 rounded-3xl bg-gradient-to-br from-white to-slate-300 p-5 text-slate-950 shadow-soft">
        <div className="text-lg font-bold">Finance OS</div>
        <div className="text-sm opacity-70">AI expense tracker</div>
      </div>
      <div className="space-y-2">
        {items.map(({ to, label, icon: Icon }) => {
          const active = location.pathname === to;
          return (
            <Link
              key={to}
              to={to}
              className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm transition ${active ? 'bg-white text-slate-950' : 'text-slate-300 hover:bg-white/5 hover:text-white'}`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </div>
    </aside>
  );
}
