import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Receipt,
  Tags,
  PieChart,
  Target,
  Repeat,
  Users2,
  FolderGit2,
  Settings,
  LogOut,
  Wallet as WalletIcon,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { cn } from '../../lib/utils';

const navItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Transactions', path: '/transactions', icon: Receipt },
  { name: 'Categories', path: '/categories', icon: Tags },
  { name: 'Budgets', path: '/budgets', icon: PieChart },
  { name: 'Goals', path: '/goals', icon: Target },
  { name: 'Recurring', path: '/recurring', icon: Repeat },
  { name: 'Bill Splits', path: '/splits', icon: Users2 },
  { name: 'Groups', path: '/groups', icon: FolderGit2 },
  { name: 'Settings', path: '/settings', icon: Settings },
];

export function Sidebar({ onCloseMobile }: { onCloseMobile?: () => void }) {
  const { user, logout } = useAuth();

  return (
    <aside className="w-56 flex flex-col h-full bg-surface border-r border-border select-none">
      {/* Brand / Logo */}
      <div className="h-12 flex items-center px-4 border-b border-border gap-2">
        <div className="h-6 w-6 rounded-control bg-accent flex items-center justify-center text-accent-text font-bold text-xs">
          ₹
        </div>
        <div className="flex flex-col">
          <span className="text-xs font-semibold tracking-tight text-text">
            Expense Tracker
          </span>
          <span className="text-[10px] text-text-muted leading-none">Personal Edition</span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={onCloseMobile}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 px-2.5 py-1.5 rounded-control text-xs font-medium transition-colors duration-150',
                isActive
                  ? 'bg-surface-2 text-accent font-semibold'
                  : 'text-text-muted hover:text-text hover:bg-surface-2/60'
              )
            }
          >
            <item.icon className="h-4 w-4 flex-shrink-0" />
            <span>{item.name}</span>
          </NavLink>
        ))}
      </nav>

      {/* User profile & Logout */}
      <div className="p-3 border-t border-border flex items-center justify-between">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="h-7 w-7 rounded-full bg-surface-2 border border-border flex items-center justify-center text-xs font-semibold text-text uppercase">
            {user?.username?.[0] || 'U'}
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-xs font-medium text-text truncate">
              {user?.username}
            </span>
            <span className="text-[10px] text-text-muted truncate">
              {user?.email}
            </span>
          </div>
        </div>
        <button
          onClick={logout}
          className="p-1 rounded-control text-text-muted hover:text-expense hover:bg-surface-2 transition-colors"
          title="Log out"
        >
          <LogOut className="h-3.5 w-3.5" />
        </button>
      </div>
    </aside>
  );
}
