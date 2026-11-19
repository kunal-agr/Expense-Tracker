import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { formatINR } from '../lib/utils';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Modal from '../components/ui/Modal';
import Badge from '../components/ui/Badge';
import Skeleton from '../components/ui/Skeleton';
import {
  Users2,
  Plus,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  ArrowRight,
  ShieldAlert,
  Percent,
  Coins,
  DollarSign
} from 'lucide-react';

interface SplitParticipant {
  id: number;
  user_id: number | null;
  username: string;
  share_amount: number;
  status: 'pending' | 'accepted' | 'rejected' | 'expired';
  responded_at: string | null;
  is_payer: boolean;
}

interface SplitItem {
  id: number;
  payer_id: number;
  payer_username: string;
  group_id: number | null;
  group_name: string | null;
  total_amount: number;
  split_type: 'exact' | 'percentage' | 'shares';
  note: string | null;
  status: 'pending' | 'locked' | 'cancelled';
  created_at: string;
  expires_at: string;
  participants: SplitParticipant[];
  user_share_status: string | null;
  user_share_amount: number | null;
}

interface CategoryItem {
  id: number;
  name: string;
  type?: string;
  parent_id: number | null;
  subcategories?: CategoryItem[];
}

interface TransactionItem {
  id: number;
  type: string;
  amount: number;
  category_id: number;
  note: string | null;
  category_name?: string;
  date: string;
}

export default function SplitsPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'all' | 'created' | 'participating'>('all');

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Form states for Create Split
  const [totalAmount, setTotalAmount] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [note, setNote] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<'UPI' | 'Card' | 'Cash'>('UPI');
  const [calcMode, setCalcMode] = useState<'exact' | 'percentage' | 'shares'>('exact');
  const [participantsList, setParticipantsList] = useState<{ username: string; value: string }[]>([
    { username: '', value: '' },
  ]);
  const [remainderBearer, setRemainderBearer] = useState('');
  const [formError, setFormError] = useState('');

  // Fetch splits
  const { data: splits = [], isLoading } = useQuery<SplitItem[]>({
    queryKey: ['splits', activeTab],
    queryFn: async () => {
      const param = activeTab === 'all' ? '' : `?filter_type=${activeTab}`;
      const res = await api.get(`/splits${param}`);
      return res.data;
    },
  });

  // Fetch expense categories
  const { data: categories = [] } = useQuery<CategoryItem[]>({
    queryKey: ['categories'],
    queryFn: async () => {
      const res = await api.get('/categories');
      return res.data;
    },
  });

  // Flatten categories
  const expenseCategories = React.useMemo(() => {
    const list: { id: number; name: string }[] = [];
    categories.forEach((cat) => {
      list.push({ id: cat.id, name: cat.name });
      if (cat.subcategories) {
        cat.subcategories.forEach((sub) => {
          list.push({ id: sub.id, name: `— ${sub.name}` });
        });
      }
    });
    return list;
  }, [categories]);

  // Fetch recent expenses to optionally pre-fill
  const { data: recentTxs = [] } = useQuery<TransactionItem[]>({
    queryKey: ['recent-expenses-for-split'],
    queryFn: async () => {
      const res = await api.get('/transactions?type=expense&limit=20');
      return res.data?.items || [];
    },
    enabled: isCreateModalOpen,
  });

  const createSplitMutation = useMutation({
    mutationFn: async (payload: any) => {
      return api.post('/splits', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['splits'] });
      queryClient.invalidateQueries({ queryKey: ['wallet'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      closeCreateModal();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || err.message || 'Failed to create split');
    },
  });

  const acceptMutation = useMutation({
    mutationFn: async (splitId: number) => {
      return api.post(`/splits/${splitId}/accept`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['splits'] });
      queryClient.invalidateQueries({ queryKey: ['wallet'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || err.message || 'Failed to accept split');
    },
  });

  const rejectMutation = useMutation({
    mutationFn: async (splitId: number) => {
      return api.post(`/splits/${splitId}/reject`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['splits'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || err.message || 'Failed to reject split');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: async (splitId: number) => {
      return api.post(`/splits/${splitId}/cancel`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['splits'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || err.message || 'Failed to cancel split (a participant may have already accepted)');
    },
  });

  const closeCreateModal = () => {
    setIsCreateModalOpen(false);
    setTotalAmount('');
    setCategoryId('');
    setNote('');
    setPaymentMethod('UPI');
    setCalcMode('exact');
    setParticipantsList([{ username: '', value: '' }]);
    setRemainderBearer('');
    setFormError('');
  };

  const handleAddParticipantRow = () => {
    setParticipantsList([...participantsList, { username: '', value: '' }]);
  };

  const handleRemoveParticipantRow = (index: number) => {
    setParticipantsList(participantsList.filter((_, i) => i !== index));
  };

  const handleParticipantChange = (index: number, field: 'username' | 'value', val: string) => {
    const updated = [...participantsList];
    updated[index][field] = val;
    setParticipantsList(updated);
  };

  const handleSelectRecentTx = (txIdStr: string) => {
    const tx = recentTxs.find((t) => t.id === parseInt(txIdStr, 10));
    if (tx) {
      setTotalAmount(tx.amount.toString());
      if (tx.category_id) setCategoryId(tx.category_id.toString());
      if (tx.note) setNote(tx.note);
    }
  };

  const handleCreateSplit = (e: React.FormEvent) => {
    e.preventDefault();
    const tot = parseInt(totalAmount, 10);
    const catId = parseInt(categoryId, 10);

    if (isNaN(tot) || tot <= 0) {
      setFormError('Total bill amount must be a positive integer');
      return;
    }
    if (!catId || isNaN(catId)) {
      setFormError('Please select an expense category');
      return;
    }

    const cleanedParticipants = participantsList
      .map((p) => {
        const u = p.username.trim().toLowerCase();
        const v = parseFloat(p.value);
        if (!u || isNaN(v) || v <= 0) return null;

        if (calcMode === 'exact') {
          return { username: u, amount: Math.round(v) };
        } else if (calcMode === 'percentage') {
          return { username: u, percentage: v };
        } else {
          return { username: u, shares: Math.round(v) };
        }
      })
      .filter(Boolean);

    if (cleanedParticipants.length === 0) {
      setFormError('At least one other participant with a valid share is required');
      return;
    }

    createSplitMutation.mutate({
      total_amount: tot,
      split_type: calcMode,
      category_id: catId,
      payment_method: paymentMethod,
      note: note.trim() || undefined,
      participants: cleanedParticipants,
      remainder_bearer_username: remainderBearer.trim().toLowerCase() || undefined,
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">Bill Splits</h1>
          <p className="text-sm text-text-secondary mt-1">
            Split expenses with friends via exact amounts, percentages, or shares with atomic settlement.
          </p>
        </div>
        <Button onClick={() => setIsCreateModalOpen(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Split a Bill
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border space-x-6 text-sm font-medium">
        {(['all', 'created', 'participating'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-3 capitalize transition relative ${
              activeTab === tab
                ? 'text-primary-500 font-semibold'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {tab === 'all' ? 'All Splits' : tab === 'created' ? 'Created by Me' : 'Awaiting / Participating'}
            {activeTab === tab && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-500 rounded-t" />
            )}
          </button>
        ))}
      </div>

      {/* Splits List */}
      <Card>
        {isLoading ? (
          <div className="p-4 space-y-4">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : splits.length === 0 ? (
          <div className="p-12 text-center text-text-secondary">
            <Users2 className="w-12 h-12 mx-auto mb-3 opacity-40" />
            <h3 className="text-base font-semibold text-text-primary">No splits found</h3>
            <p className="text-sm mt-1 mb-4">
              {activeTab === 'participating'
                ? 'No active split bills where you are a participant.'
                : 'Create a split to divide an expense among friends.'}
            </p>
            <Button onClick={() => setIsCreateModalOpen(true)}>Split a Bill</Button>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {splits.map((split) => {
              const isCreator = split.payer_username === user?.username;
              const myParticipant = split.participants.find(
                (p) => p.username === user?.username && !p.is_payer
              );
              const isPendingMyAction = myParticipant && myParticipant.status === 'pending';
              const isCancelled = split.status === 'cancelled';
              const isLocked = split.status === 'locked';

              return (
                <div key={split.id} className="p-5 space-y-3 hover:bg-surface-elevated/40 transition">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center space-x-3">
                      <div className="p-2.5 rounded-xl bg-primary-500/10 text-primary-500">
                        <Users2 className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-text-primary text-base">
                            {split.note || `Bill Split #${split.id}`}
                          </span>
                          <Badge
                            variant={
                              isLocked
                                ? 'income'
                                : isCancelled
                                ? 'danger'
                                : 'neutral'
                            }
                          >
                            {split.status.toUpperCase()}
                          </Badge>
                          <span className="text-xs text-text-muted capitalize">
                            ({split.split_type} split)
                          </span>
                        </div>
                        <p className="text-xs text-text-secondary mt-0.5">
                          {isCreator ? 'Paid by You' : `Paid by @${split.payer_username}`} • Total:{' '}
                          <span className="font-semibold text-text-primary">{formatINR(split.total_amount)}</span>
                        </p>
                      </div>
                    </div>

                    {/* Actions for Participant */}
                    {isPendingMyAction && split.status !== 'cancelled' && (
                      <div className="flex items-center space-x-2">
                        <Button
                          size="sm"
                          className="bg-accent-income hover:bg-accent-income/90 text-white"
                          isLoading={acceptMutation.isPending}
                          onClick={() => acceptMutation.mutate(split.id)}
                        >
                          <CheckCircle className="w-4 h-4 mr-1.5" />
                          Pay {formatINR(myParticipant.share_amount)}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-accent-expense border-accent-expense/30 hover:bg-accent-expense/10"
                          isLoading={rejectMutation.isPending}
                          onClick={() => rejectMutation.mutate(split.id)}
                        >
                          <XCircle className="w-4 h-4 mr-1.5" />
                          Decline
                        </Button>
                      </div>
                    )}

                    {/* Actions for Creator */}
                    {isCreator && split.status === 'pending' && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-accent-expense hover:bg-accent-expense/10"
                        isLoading={cancelMutation.isPending}
                        onClick={() => cancelMutation.mutate(split.id)}
                        title="Cancel this split before any participant accepts"
                      >
                        Cancel Split
                      </Button>
                    )}
                  </div>

                  {/* Participants Row */}
                  <div className="pt-2 pl-12 flex flex-wrap gap-2 text-xs">
                    {split.participants.map((p) => (
                      <div
                        key={p.id}
                        className={`inline-flex items-center px-2.5 py-1 rounded-md border text-xs font-medium ${
                          p.is_payer
                            ? 'bg-primary-500/10 border-primary-500/30 text-primary-500'
                            : p.status === 'accepted'
                            ? 'bg-accent-income/10 border-accent-income/30 text-accent-income'
                            : p.status === 'rejected'
                            ? 'bg-accent-expense/10 border-accent-expense/30 text-accent-expense line-through'
                            : p.status === 'expired'
                            ? 'bg-surface border-border text-text-muted line-through'
                            : 'bg-surface border-border text-text-secondary'
                        }`}
                      >
                        <span>
                          @{p.username}
                          {p.is_payer ? ' (Payer)' : ''}: {formatINR(p.share_amount)}
                        </span>
                        {!p.is_payer && (
                          <span className="ml-1.5 capitalize text-[10px] opacity-80">
                            ({p.status})
                          </span>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Expiry note */}
                  {split.status === 'pending' && (
                    <div className="pl-12 flex items-center space-x-1.5 text-[11px] text-text-muted">
                      <Clock className="w-3 h-3" />
                      <span>Expires on: {new Date(split.expires_at).toLocaleDateString()} (7-day window)</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Create Split Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={closeCreateModal}
        title="Split a Bill"
      >
        <form onSubmit={handleCreateSplit} className="space-y-4">
          {formError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {formError}
            </div>
          )}

          {/* Quick pick from recent expenses */}
          {recentTxs.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">
                Auto-fill from recent expense (Optional)
              </label>
              <select
                onChange={(e) => handleSelectRecentTx(e.target.value)}
                defaultValue=""
                className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-text-primary focus:border-primary-500 focus:outline-none"
              >
                <option value="">-- Or enter bill details below --</option>
                {recentTxs.map((t) => (
                  <option key={t.id} value={t.id}>
                    {formatINR(t.amount)} — {t.note || t.category_name || 'Expense'} ({t.date})
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Total Bill Amount (₹)"
              type="number"
              min="1"
              placeholder="e.g. 1500"
              value={totalAmount}
              onChange={(e) => setTotalAmount(e.target.value)}
              required
              autoFocus
            />

            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Category</label>
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:border-primary-500 focus:outline-none"
                required
              >
                <option value="">-- Choose Category --</option>
                {expenseCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Payment Method */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">Paid Via</label>
            <div className="grid grid-cols-3 gap-2">
              {(['UPI', 'Card', 'Cash'] as const).map((method) => (
                <button
                  key={method}
                  type="button"
                  onClick={() => setPaymentMethod(method)}
                  className={`py-1.5 text-xs font-semibold rounded-lg border transition ${
                    paymentMethod === method
                      ? 'border-primary-500 bg-primary-500/10 text-primary-500'
                      : 'border-border text-text-secondary hover:bg-surface-elevated'
                  }`}
                >
                  {method}
                </button>
              ))}
            </div>
          </div>

          {/* Calculation Mode */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">Calculation Mode</label>
            <div className="grid grid-cols-3 gap-2">
              {(['exact', 'percentage', 'shares'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setCalcMode(m)}
                  className={`py-2 text-xs font-semibold rounded-lg border capitalize transition ${
                    calcMode === m
                      ? 'border-primary-500 bg-primary-500/10 text-primary-500'
                      : 'border-border text-text-secondary hover:bg-surface-elevated'
                  }`}
                >
                  {m === 'exact' ? 'Exact (₹)' : m === 'percentage' ? 'Percentage (%)' : 'Shares (1, 2...)'}
                </button>
              ))}
            </div>
          </div>

          {/* Participants Input */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-text-primary">
              Participants & Shares (excluding yourself)
            </label>
            {participantsList.map((p, idx) => (
              <div key={idx} className="flex items-center space-x-2">
                <Input
                  placeholder="Username (e.g. bob)"
                  value={p.username}
                  onChange={(e) => handleParticipantChange(idx, 'username', e.target.value)}
                  className="flex-1"
                  required
                />
                <Input
                  type="number"
                  min="0.01"
                  step="any"
                  placeholder={calcMode === 'exact' ? 'Amount ₹' : calcMode === 'percentage' ? '%' : 'Shares'}
                  value={p.value}
                  onChange={(e) => handleParticipantChange(idx, 'value', e.target.value)}
                  className="w-28"
                  required
                />
                {participantsList.length > 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-accent-expense"
                    onClick={() => handleRemoveParticipantRow(idx)}
                  >
                    ×
                  </Button>
                )}
              </div>
            ))}

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleAddParticipantRow}
              className="text-xs"
            >
              + Add Participant
            </Button>
          </div>

          {/* Remainder Bearer (FR-062) */}
          {(calcMode === 'percentage' || calcMode === 'shares') && (
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">
                Remainder Bearer (FR-062)
              </label>
              <select
                value={remainderBearer}
                onChange={(e) => setRemainderBearer(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:border-primary-500 focus:outline-none"
              >
                <option value="">You (Payer - Default)</option>
                {participantsList
                  .filter((p) => p.username.trim())
                  .map((p, idx) => (
                    <option key={idx} value={p.username.trim()}>
                      @{p.username.trim()}
                    </option>
                  ))}
              </select>
              <p className="text-[11px] text-text-muted mt-1">
                Whole-rupee rounding remainder will be assigned to this user.
              </p>
            </div>
          )}

          <Input
            label="Bill Note / Description (Optional)"
            placeholder="e.g. Dinner at Olive, Cab to airport"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={closeCreateModal}>
              Cancel
            </Button>
            <Button type="submit" isLoading={createSplitMutation.isPending}>
              Send Split Bill
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
