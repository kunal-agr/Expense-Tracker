import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Menu, Sun, Moon, Wallet as WalletIcon } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { api } from '../../lib/api';
import { formatINR } from '../../lib/utils';
import { NotificationDropdown } from './NotificationDropdown';

interface TopBarProps {
  onOpenMobileMenu: () => void;
}

export function TopBar({ onOpenMobileMenu }: TopBarProps) {
  const { theme, toggleTheme } = useTheme();

  const { data: wallet } = useQuery<{ current_balance: number }>({
    queryKey: ['wallet-balance'],
    queryFn: () => api.get('/wallet'),
    refetchInterval: 15000,
  });

  return (
    <header className="h-12 border-b border-border bg-surface px-4 flex items-center justify-between z-10 select-none">
      {/* Mobile Hamburger */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobileMenu}
          className="md:hidden p-1 rounded-control text-text-muted hover:text-text hover:bg-surface-2"
        >
          <Menu className="h-4 w-4" />
        </button>
      </div>

      {/* Right Tools */}
      <div className="flex items-center gap-2.5">
        {/* Wallet Balance Pill */}
        {wallet && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-control bg-surface-2 border border-border text-xs">
            <WalletIcon className="h-3.5 w-3.5 text-accent" />
            <span className="text-[11px] text-text-muted">Balance:</span>
            <span className="font-mono-num font-semibold text-text">
              {formatINR(wallet.current_balance)}
            </span>
          </div>
        )}

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-1.5 rounded-control text-text-muted hover:text-text hover:bg-surface-2 transition-colors"
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </button>

        {/* Notifications Dropdown (FR-080, FR-082) */}
        <NotificationDropdown />
      </div>
    </header>
  );
}
