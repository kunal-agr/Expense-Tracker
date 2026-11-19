import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Modal from '../components/ui/Modal';
import Badge from '../components/ui/Badge';
import Skeleton from '../components/ui/Skeleton';
import {
  User,
  Shield,
  Moon,
  Sun,
  Laptop,
  Download,
  UserX,
  Trash2,
  LogOut,
  AlertTriangle,
  FileSpreadsheet,
  FileText,
  FileCheck,
  CheckCircle2
} from 'lucide-react';

interface BlockedUser {
  id: string;
  blocked_user_id: string;
  blocked_username: string;
  blocked_at: string;
}

interface SessionItem {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  is_current: boolean;
  created_at: string;
  last_active_at: string;
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { user, refreshUser, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  // Modals
  const [isChangeUsernameOpen, setIsChangeUsernameOpen] = useState(false);
  const [isBlockUserOpen, setIsBlockUserOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [isDeleteAccountOpen, setIsDeleteAccountOpen] = useState(false);

  // Change username form
  const [newUsername, setNewUsername] = useState('');
  const [usernameError, setUsernameError] = useState('');

  // Block form
  const [blockUsernameInput, setBlockUsernameInput] = useState('');
  const [blockError, setBlockError] = useState('');

  // Export form
  const [exportFormat, setExportFormat] = useState<'csv' | 'xlsx' | 'pdf'>('csv');
  const [exportFrom, setExportFrom] = useState('');
  const [exportTo, setExportTo] = useState('');
  const [exportType, setExportType] = useState('');
  const [isExporting, setIsExporting] = useState(false);

  // Delete account form
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteError, setDeleteError] = useState('');

  // Fetch Blocked Users
  const { data: blockedUsers = [], isLoading: isLoadingBlocked } = useQuery<BlockedUser[]>({
    queryKey: ['blocked-users'],
    queryFn: async () => {
      const res = await api.get('/blocks');
      return res.data;
    },
  });

  // Fetch Sessions
  const { data: sessions = [], isLoading: isLoadingSessions } = useQuery<SessionItem[]>({
    queryKey: ['user-sessions'],
    queryFn: async () => {
      const res = await api.get('/auth/sessions');
      return res.data;
    },
  });

  // Change Username Mutation
  const changeUsernameMutation = useMutation({
    mutationFn: async (username: string) => {
      return api.patch('/auth/me/username', { username });
    },
    onSuccess: async () => {
      await refreshUser();
      setIsChangeUsernameOpen(false);
      setNewUsername('');
      setUsernameError('');
    },
    onError: (err: any) => {
      setUsernameError(err.response?.data?.message || 'Username already taken or invalid');
    },
  });

  // Block User Mutation
  const blockMutation = useMutation({
    mutationFn: async (username: string) => {
      return api.post('/blocks', { username });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['blocked-users'] });
      setIsBlockUserOpen(false);
      setBlockUsernameInput('');
      setBlockError('');
    },
    onError: (err: any) => {
      setBlockError(err.response?.data?.message || 'Failed to block user');
    },
  });

  // Unblock User Mutation
  const unblockMutation = useMutation({
    mutationFn: async (username: string) => {
      return api.delete(`/blocks/${username}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['blocked-users'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to unblock user');
    },
  });

  // Revoke Session Mutation
  const revokeSessionMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      return api.delete(`/auth/sessions/${sessionId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-sessions'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to revoke session');
    },
  });

  // Logout All Devices Mutation
  const logoutAllMutation = useMutation({
    mutationFn: async () => {
      return api.post('/auth/logout-all');
    },
    onSuccess: () => {
      logout();
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to logout from all devices');
    },
  });

  // Delete Account Mutation
  const deleteAccountMutation = useMutation({
    mutationFn: async (password: string) => {
      return api.delete('/auth/me', { data: { password } });
    },
    onSuccess: () => {
      logout();
    },
    onError: (err: any) => {
      setDeleteError(err.response?.data?.message || 'Incorrect password');
    },
  });

  const handleExport = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsExporting(true);
    try {
      const params = new URLSearchParams();
      params.append('format', exportFormat);
      if (exportFrom) params.append('from', exportFrom);
      if (exportTo) params.append('to', exportTo);
      if (exportType) params.append('type', exportType);

      const response = await api.get(`/export/transactions?${params.toString()}`, {
        responseType: 'blob',
      });

      const blob = new Blob([response.data], {
        type:
          exportFormat === 'csv'
            ? 'text/csv'
            : exportFormat === 'xlsx'
            ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            : 'application/pdf',
      });

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `transactions_export.${exportFormat}`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      setIsExportOpen(false);
    } catch (err: any) {
      alert('Failed to export transactions. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Top Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text-primary">Settings</h1>
        <p className="text-sm text-text-secondary mt-1">
          Manage your account profile, privacy, sessions, appearance, and transaction exports.
        </p>
      </div>

      {/* Profile Card */}
      <Card className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="w-14 h-14 rounded-full bg-primary-500/10 text-primary-500 flex items-center justify-center font-bold text-xl uppercase">
              {user?.username.slice(0, 2)}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-lg font-bold text-text-primary">@{user?.username}</h2>
                <Badge variant="neutral">{user?.role || 'user'}</Badge>
              </div>
              <p className="text-sm text-text-secondary">{user?.email}</p>
            </div>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setNewUsername(user?.username || '');
              setUsernameError('');
              setIsChangeUsernameOpen(true);
            }}
          >
            Change Username
          </Button>
        </div>
      </Card>

      {/* Appearance & Preferences */}
      <Card className="p-6 space-y-4">
        <h3 className="text-base font-bold text-text-primary">Appearance & Theme</h3>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-surface-elevated text-primary-500">
              {theme === 'dark' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
            </div>
            <div>
              <p className="text-sm font-semibold text-text-primary">Color Theme</p>
              <p className="text-xs text-text-secondary">
                Currently using {theme === 'dark' ? 'Warm Charcoal Dark' : 'Clean Warm Paper Light'} mode
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={toggleTheme}>
            Switch to {theme === 'dark' ? 'Light' : 'Dark'}
          </Button>
        </div>
      </Card>

      {/* Data Export (FR-091) */}
      <Card className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-accent-income/10 text-accent-income">
              <Download className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-text-primary">Export Transaction Data</h3>
              <p className="text-xs text-text-secondary">
                Download your records as formatted CSV, Excel (XLSX), or PDF reports.
              </p>
            </div>
          </div>
          <Button onClick={() => setIsExportOpen(true)}>
            <Download className="w-4 h-4 mr-2" />
            Export Data
          </Button>
        </div>
      </Card>

      {/* Blocked Users (FR-072) */}
      <Card className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-text-primary">Blocked Users</h3>
            <p className="text-xs text-text-secondary">
              Blocked users cannot invite you to splits or groups, with privacy-preserving generic errors.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setBlockUsernameInput('');
              setBlockError('');
              setIsBlockUserOpen(true);
            }}
          >
            <UserX className="w-4 h-4 mr-1.5" />
            Block User
          </Button>
        </div>

        {isLoadingBlocked ? (
          <Skeleton className="h-16 w-full" />
        ) : blockedUsers.length === 0 ? (
          <p className="text-xs text-text-muted italic">No blocked users</p>
        ) : (
          <div className="divide-y divide-border rounded-lg border border-border overflow-hidden">
            {blockedUsers.map((bu) => (
              <div key={bu.id} className="p-3 flex items-center justify-between bg-surface">
                <span className="text-sm font-semibold text-text-primary">@{bu.blocked_username}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs text-text-secondary hover:text-text-primary"
                  onClick={() => unblockMutation.mutate(bu.blocked_username)}
                >
                  Unblock
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Active Sessions (FR-005, FR-007) */}
      <Card className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-text-primary">Active Sessions</h3>
            <p className="text-xs text-text-secondary">
              Devices currently authenticated with your account.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="text-accent-expense border-accent-expense/30 hover:bg-accent-expense/10"
            onClick={() => logoutAllMutation.mutate()}
            isLoading={logoutAllMutation.isPending}
          >
            <LogOut className="w-4 h-4 mr-1.5" />
            Logout Other Devices
          </Button>
        </div>

        {isLoadingSessions ? (
          <Skeleton className="h-20 w-full" />
        ) : (
          <div className="divide-y divide-border rounded-lg border border-border overflow-hidden">
            {sessions.map((s) => (
              <div key={s.id} className="p-3.5 flex items-center justify-between bg-surface">
                <div className="flex items-center space-x-3">
                  <Laptop className="w-5 h-5 text-text-secondary" />
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-semibold text-text-primary">
                        {s.user_agent ? s.user_agent.slice(0, 40) + '...' : 'Browser Session'}
                      </span>
                      {s.is_current && (
                        <Badge variant="income" className="text-[10px]">
                          Current Session
                        </Badge>
                      )}
                    </div>
                    <p className="text-[11px] text-text-muted">
                      IP: {s.ip_address || 'Unknown'} • Last active:{' '}
                      {new Date(s.last_active_at).toLocaleString()}
                    </p>
                  </div>
                </div>

                {!s.is_current && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs text-accent-expense"
                    onClick={() => revokeSessionMutation.mutate(s.id)}
                  >
                    Revoke
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Danger Zone: Delete Account (FR-011) */}
      <Card className="p-6 border-accent-expense/30 space-y-4 bg-accent-expense/5">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-base font-bold text-accent-expense flex items-center space-x-2">
              <AlertTriangle className="w-5 h-5" />
              <span>Danger Zone: Delete Account</span>
            </h3>
            <p className="text-xs text-text-secondary mt-1 max-w-xl">
              Permanently delete your account, wallet, transactions, budgets, goals, and recurring rules.
              Group creator roles will succeed to the earliest-joined member. This action cannot be undone.
            </p>
          </div>
          <Button
            variant="primary"
            className="bg-accent-expense hover:bg-accent-expense/90"
            onClick={() => {
              setDeletePassword('');
              setDeleteError('');
              setIsDeleteAccountOpen(true);
            }}
          >
            Delete Account
          </Button>
        </div>
      </Card>

      {/* Change Username Modal */}
      <Modal
        isOpen={isChangeUsernameOpen}
        onClose={() => setIsChangeUsernameOpen(false)}
        title="Change Username"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!newUsername.trim()) return;
            changeUsernameMutation.mutate(newUsername.trim());
          }}
          className="space-y-4"
        >
          {usernameError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {usernameError}
            </div>
          )}

          <Input
            label="New Username"
            placeholder="e.g. superhero"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
            required
            autoFocus
          />

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={() => setIsChangeUsernameOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={changeUsernameMutation.isPending}>
              Update Username
            </Button>
          </div>
        </form>
      </Modal>

      {/* Block User Modal */}
      <Modal
        isOpen={isBlockUserOpen}
        onClose={() => setIsBlockUserOpen(false)}
        title="Block User"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!blockUsernameInput.trim()) return;
            blockMutation.mutate(blockUsernameInput.trim().toLowerCase());
          }}
          className="space-y-4"
        >
          {blockError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {blockError}
            </div>
          )}

          <Input
            label="Username to Block"
            placeholder="e.g. charlie"
            value={blockUsernameInput}
            onChange={(e) => setBlockUsernameInput(e.target.value)}
            required
            autoFocus
          />

          <p className="text-xs text-text-muted">
            The blocked user will not receive any notification of the block.
          </p>

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={() => setIsBlockUserOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={blockMutation.isPending}>
              Block User
            </Button>
          </div>
        </form>
      </Modal>

      {/* Export Modal */}
      <Modal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        title="Export Transactions"
      >
        <form onSubmit={handleExport} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-2">Export Format</label>
            <div className="grid grid-cols-3 gap-3">
              {(['csv', 'xlsx', 'pdf'] as const).map((fmt) => (
                <button
                  key={fmt}
                  type="button"
                  onClick={() => setExportFormat(fmt)}
                  className={`p-3 text-center rounded-lg border uppercase text-xs font-bold transition flex flex-col items-center space-y-1.5 ${
                    exportFormat === fmt
                      ? 'border-primary-500 bg-primary-500/10 text-primary-500'
                      : 'border-border text-text-secondary hover:bg-surface-elevated'
                  }`}
                >
                  {fmt === 'csv' ? (
                    <FileText className="w-5 h-5" />
                  ) : fmt === 'xlsx' ? (
                    <FileSpreadsheet className="w-5 h-5" />
                  ) : (
                    <FileCheck className="w-5 h-5" />
                  )}
                  <span>{fmt}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="From Date"
              type="date"
              value={exportFrom}
              onChange={(e) => setExportFrom(e.target.value)}
            />
            <Input
              label="To Date"
              type="date"
              value={exportTo}
              onChange={(e) => setExportTo(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">Filter Type</label>
            <select
              value={exportType}
              onChange={(e) => setExportType(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:border-primary-500 focus:outline-none"
            >
              <option value="">All Transactions</option>
              <option value="expense">Expenses Only</option>
              <option value="income">Incomes Only</option>
            </select>
          </div>

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={() => setIsExportOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isExporting}>
              Download Export
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Account Modal */}
      <Modal
        isOpen={isDeleteAccountOpen}
        onClose={() => setIsDeleteAccountOpen(false)}
        title="Confirm Account Deletion"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!deletePassword) return;
            deleteAccountMutation.mutate(deletePassword);
          }}
          className="space-y-4"
        >
          {deleteError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {deleteError}
            </div>
          )}

          <p className="text-sm text-text-secondary">
            Please enter your current account password to confirm permanent deletion.
          </p>

          <Input
            label="Account Password"
            type="password"
            placeholder="••••••••"
            value={deletePassword}
            onChange={(e) => setDeletePassword(e.target.value)}
            required
            autoFocus
          />

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={() => setIsDeleteAccountOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              className="bg-accent-expense hover:bg-accent-expense/90"
              isLoading={deleteAccountMutation.isPending}
            >
              Permanently Delete
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
