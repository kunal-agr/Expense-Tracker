import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
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
  id: string;
  username: string;
  share_amount: number;
  status: 'pending' | 'accepted' | 'rejected';
  accepted_at: string | null;
  rejected_at: string | null;
}

interface SplitItem {
  id: string;
  transaction_id: string;
  total_amount: number;
  calculation_mode: 'exact' | 'percentage' | 'shares';
  description: string | null;
  creator_username: string;
  is_creator: boolean;
  status: 'pending' | 'completed' | 'cancelled' | 'expired';
  created_at: string;
  expires_at: string;
  participants: SplitParticipant[];
}

interface TransactionItem {
  id: string;
  type: string;
  amount: number;
  description: string | null;
  category_name?: string;
  date: string;
  is_readonly?: boolean;
}

export default function SplitsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'all' | 'pending' | 'created' | 'participating'>('all');

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedSplitDetail, setSelectedSplitDetail] = useState<SplitItem | null>(null);

  // Form states for Create Split
  const [selectedTxId, setSelectedTxId] = useState('');
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
      const res = await api.get(`/splits?filter=${activeTab}`);
      return res.data;
    },
  });

  // Fetch expense transactions for create split
  const { data: recentTxs = [] } = useQuery<TransactionItem[]>({
    queryKey: ['recent-expenses-for-split'],
    queryFn: async () => {
      const res = await api.get('/transactions?type=expense&limit=30');
      return res.data.items || [];
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
      closeCreateModal();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || 'Failed to create split');
    },
  });

  const acceptMutation = useMutation({
    mutationFn: async (splitId: string) => {
      return api.post(`/splits/${splitId}/accept`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['splits'] });
      queryClient.invalidateQueries({ queryKey: ['wallet'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to accept split');
    },
  });

  const rejectMutation = useMutation({
    mutationFn: async (splitId: string) => {
      return api.post(`/splits/${splitId}/reject`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['splits'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to reject split');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: async (splitId: string) => {
      return api.post(`/splits/${splitId}/cancel`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['splits'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to cancel split (a participant may have already accepted)');
    },
  });

  const closeCreateModal = () => {
    setIsCreateModalOpen(false);
    setSelectedTxId('');
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

  const selectedTransaction = recentTxs.find((t) => t.id === selectedTxId);

  const handleCreateSplit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTxId) {
      setFormError('Please select an expense transaction to split');
      return;
    }

    const cleanedParticipants = participantsList
      .map((p) => ({
        username: p.username.trim().toLowerCase(),
        value: parseFloat(p.value),
      }))
      .filter((p) => p.username && !isNaN(p.value) && p.value > 0);

    if (cleanedParticipants.length === 0) {
      setFormError('At least one valid participant is required');
      return;
    }

    createSplitMutation.mutate({
      transaction_id: selectedTxId,
      calculation_mode: calcMode,
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
          Split an Expense
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border space-x-6 text-sm font-medium">
        {(['all', 'pending', 'created', 'participating'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-3 capitalize transition relative ${
              activeTab === tab
                ? 'text-primary-500 font-semibold'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {tab} Splits
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
              {activeTab === 'pending'
                ? 'No pending split requests awaiting your action.'
                : 'Create a split from any of your expense transactions.'}
            </p>
            <Button onClick={() => setIsCreateModalOpen(true)}>Split an Expense</Button>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {splits.map((split) => {
              const myParticipantRecord = !split.is_creator
                ? split.participants.find((p) => p.status === 'pending')
                : null;
              const isExpired = split.status === 'expired';
              const isCompleted = split.status === 'completed';
              const isCancelled = split.status === 'cancelled';

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
                            {split.description || 'Split Bill'}
                          </span>
                          <Badge
                            variant={
                              isCompleted
                                ? 'income'
                                : isCancelled || isExpired
                                ? 'neutral'
                                : 'neutral'
                            }
                          >
                            {split.status.toUpperCase()}
                          </Badge>
                          <span className="text-xs text-text-muted capitalize">
                            ({split.calculation_mode} split)
                          </span>
                        </div>
                        <p className="text-xs text-text-secondary mt-0.5">
                          {split.is_creator ? 'Initiated by You' : `Initiated by @${split.creator_username}`} • Total:{' '}
                          <span className="font-semibold text-text-primary">{formatINR(split.total_amount)}</span>
                        </p>
                      </div>
                    </div>

                    {/* Actions for Participant */}
                    {!split.is_creator && myParticipantRecord && split.status === 'pending' && (
                      <div className="flex items-center space-x-2">
                        <Button
                          size="sm"
                          className="bg-accent-income hover:bg-accent-income/90 text-white"
                          isLoading={acceptMutation.isPending}
                          onClick={() => acceptMutation.mutate(split.id)}
                        >
                          <CheckCircle className="w-4 h-4 mr-1.5" />
                          Pay {formatINR(myParticipantRecord.share_amount)}
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
                    {split.is_creator && split.status === 'pending' && (
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
                          p.status === 'accepted'
                            ? 'bg-accent-income/10 border-accent-income/30 text-accent-income'
                            : p.status === 'rejected'
                            ? 'bg-accent-expense/10 border-accent-expense/30 text-accent-expense line-through'
                            : 'bg-surface border-border text-text-secondary'
                        }`}
                      >
                        <span>@{p.username}: {formatINR(p.share_amount)}</span>
                        <span className="ml-1.5 capitalize text-[10px] opacity-80">
                          ({p.status})
                        </span>
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
        title="Split an Expense"
      >
        <form onSubmit={handleCreateSplit} className="space-y-4">
          {formError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {formError}
            </div>
          )}

          {/* Select Transaction */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">
              Select Expense Transaction
            </label>
            <select
              value={selectedTxId}
              onChange={(e) => setSelectedTxId(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:border-primary-500 focus:outline-none"
              required
            >
              <option value="">-- Choose Expense --</option>
              {recentTxs.map((t) => (
                <option key={t.id} value={t.id}>
                  {formatINR(t.amount)} — {t.description || t.category_name || 'Expense'} ({t.date})
                </option>
              ))}
            </select>
            {selectedTransaction && (
              <p className="text-xs text-text-secondary mt-1">
                Selected amount: <span className="font-semibold">{formatINR(selectedTransaction.amount)}</span>
              </p>
            )}
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
              Participants & Shares
            </label>
            {participantsList.map((p, idx) => (
              <div key={idx} className="flex items-center space-x-2">
                <Input
                  placeholder="Username (e.g. alice)"
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

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={closeCreateModal}>
              Cancel
            </Button>
            <Button type="submit" isLoading={createSplitMutation.isPending}>
              Send Split Request
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
