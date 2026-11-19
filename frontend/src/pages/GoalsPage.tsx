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
  Target,
  Plus,
  ArrowUpRight,
  ArrowDownLeft,
  CheckCircle2,
  Calendar,
  Trash2,
  Edit2,
  Coins
} from 'lucide-react';

interface Goal {
  id: string;
  name: string;
  target_amount: number;
  saved_amount: number;
  target_date: string | null;
  is_completed: boolean;
  created_at: string;
}

export default function GoalsPage() {
  const queryClient = useQueryClient();

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingGoal, setEditingGoal] = useState<Goal | null>(null);
  const [contributeGoal, setContributeGoal] = useState<Goal | null>(null);
  const [withdrawGoal, setWithdrawGoal] = useState<Goal | null>(null);
  const [deletingGoal, setDeletingGoal] = useState<Goal | null>(null);

  // Form states
  const [name, setName] = useState('');
  const [targetAmount, setTargetAmount] = useState('');
  const [targetDate, setTargetDate] = useState('');
  const [amountInput, setAmountInput] = useState('');
  const [formError, setFormError] = useState('');

  const { data: goals = [], isLoading } = useQuery<Goal[]>({
    queryKey: ['goals'],
    queryFn: async () => {
      const res = await api.get('/goals');
      return res.data;
    },
  });

  const { data: wallet } = useQuery({
    queryKey: ['wallet'],
    queryFn: async () => {
      const res = await api.get('/wallet');
      return res.data;
    },
  });

  const createGoalMutation = useMutation({
    mutationFn: async (payload: { name: string; target_amount: number; target_date?: string | null }) => {
      return api.post('/goals', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      closeModals();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || 'Failed to create goal');
    },
  });

  const updateGoalMutation = useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: any }) => {
      return api.patch(`/goals/${id}`, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      closeModals();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || 'Failed to update goal');
    },
  });

  const contributeMutation = useMutation({
    mutationFn: async ({ id, amount }: { id: string; amount: number }) => {
      return api.post(`/goals/${id}/contribute`, { amount });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      queryClient.invalidateQueries({ queryKey: ['wallet'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      closeModals();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || 'Failed to contribute to goal');
    },
  });

  const withdrawMutation = useMutation({
    mutationFn: async ({ id, amount }: { id: string; amount: number }) => {
      return api.post(`/goals/${id}/withdraw`, { amount });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      queryClient.invalidateQueries({ queryKey: ['wallet'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      closeModals();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || 'Failed to withdraw from goal');
    },
  });

  const deleteGoalMutation = useMutation({
    mutationFn: async (id: string) => {
      return api.delete(`/goals/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      queryClient.invalidateQueries({ queryKey: ['wallet'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setDeletingGoal(null);
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to delete goal');
      setDeletingGoal(null);
    },
  });

  const closeModals = () => {
    setIsAddModalOpen(false);
    setEditingGoal(null);
    setContributeGoal(null);
    setWithdrawGoal(null);
    setName('');
    setTargetAmount('');
    setTargetDate('');
    setAmountInput('');
    setFormError('');
  };

  const handleOpenEdit = (goal: Goal) => {
    setEditingGoal(goal);
    setName(goal.name);
    setTargetAmount(goal.target_amount.toString());
    setTargetDate(goal.target_date ? goal.target_date.slice(0, 10) : '');
    setFormError('');
  };

  const handleSubmitGoal = (e: React.FormEvent) => {
    e.preventDefault();
    const target = parseInt(targetAmount, 10);
    if (!name.trim()) {
      setFormError('Goal name is required');
      return;
    }
    if (isNaN(target) || target <= 0) {
      setFormError('Target amount must be a positive whole rupee value');
      return;
    }

    if (editingGoal) {
      updateGoalMutation.mutate({
        id: editingGoal.id,
        payload: {
          name: name.trim(),
          target_amount: target,
          target_date: targetDate ? targetDate : null,
        },
      });
    } else {
      createGoalMutation.mutate({
        name: name.trim(),
        target_amount: target,
        target_date: targetDate ? targetDate : null,
      });
    }
  };

  const handleContribute = (e: React.FormEvent) => {
    e.preventDefault();
    if (!contributeGoal) return;
    const amount = parseInt(amountInput, 10);
    if (isNaN(amount) || amount <= 0) {
      setFormError('Please enter a valid amount');
      return;
    }
    if (wallet && amount > wallet.current_balance) {
      setFormError(`Insufficient funds in wallet (Available: ${formatINR(wallet.current_balance)})`);
      return;
    }
    contributeMutation.mutate({ id: contributeGoal.id, amount });
  };

  const handleWithdraw = (e: React.FormEvent) => {
    e.preventDefault();
    if (!withdrawGoal) return;
    const amount = parseInt(amountInput, 10);
    if (isNaN(amount) || amount <= 0) {
      setFormError('Please enter a valid amount');
      return;
    }
    if (amount > withdrawGoal.saved_amount) {
      setFormError(`Cannot withdraw more than saved amount (${formatINR(withdrawGoal.saved_amount)})`);
      return;
    }
    withdrawMutation.mutate({ id: withdrawGoal.id, amount });
  };

  const totalSaved = goals.reduce((acc, g) => acc + g.saved_amount, 0);
  const totalTarget = goals.reduce((acc, g) => acc + g.target_amount, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">Savings Goals</h1>
          <p className="text-sm text-text-secondary mt-1">
            Ringfence your money into dedicated goals. Funds can be withdrawn back to your wallet at any time.
          </p>
        </div>
        <Button onClick={() => { closeModals(); setIsAddModalOpen(true); }}>
          <Plus className="w-4 h-4 mr-2" />
          Create Goal
        </Button>
      </div>

      {/* Summary Banner */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 flex items-center space-x-4">
          <div className="p-3 bg-primary-500/10 text-primary-500 rounded-xl">
            <Coins className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-text-secondary">Total Ringfenced</p>
            <p className="text-xl font-bold text-text-primary">{formatINR(totalSaved)}</p>
          </div>
        </Card>

        <Card className="p-4 flex items-center space-x-4">
          <div className="p-3 bg-accent-income/10 text-accent-income rounded-xl">
            <Target className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-text-secondary">Combined Targets</p>
            <p className="text-xl font-bold text-text-primary">{formatINR(totalTarget)}</p>
          </div>
        </Card>

        <Card className="p-4 flex items-center space-x-4">
          <div className="p-3 bg-accent-info/10 text-accent-info rounded-xl">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-text-secondary">Completed Goals</p>
            <p className="text-xl font-bold text-text-primary">
              {goals.filter((g) => g.is_completed).length} / {goals.length}
            </p>
          </div>
        </Card>
      </div>

      {/* Goals Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : goals.length === 0 ? (
        <Card className="p-12 text-center text-text-secondary">
          <Target className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <h3 className="text-base font-semibold text-text-primary">No savings goals yet</h3>
          <p className="text-sm mt-1 mb-4">
            Create goals for vacations, gadgets, emergency funds, or celebrations!
          </p>
          <Button onClick={() => { closeModals(); setIsAddModalOpen(true); }}>
            Start Your First Goal
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {goals.map((goal) => {
            const pct = Math.min(100, Math.round((goal.saved_amount / goal.target_amount) * 100));

            return (
              <Card key={goal.id} className="p-5 flex flex-col justify-between space-y-4">
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-bold text-text-primary text-base">{goal.name}</h3>
                      {goal.target_date && (
                        <div className="flex items-center space-x-1 text-xs text-text-muted mt-0.5">
                          <Calendar className="w-3 h-3" />
                          <span>Target: {new Date(goal.target_date).toLocaleDateString()}</span>
                        </div>
                      )}
                    </div>
                    {goal.is_completed ? (
                      <Badge variant="income">Achieved</Badge>
                    ) : (
                      <Badge variant="neutral">{pct}%</Badge>
                    )}
                  </div>

                  <div className="mt-4">
                    <div className="flex justify-between items-baseline mb-1">
                      <span className="text-2xl font-extrabold text-text-primary">
                        {formatINR(goal.saved_amount)}
                      </span>
                      <span className="text-xs text-text-secondary font-medium">
                        of {formatINR(goal.target_amount)}
                      </span>
                    </div>

                    <div className="w-full bg-surface-elevated rounded-full h-2.5 overflow-hidden">
                      <div
                        className={`h-full transition-all duration-500 ${
                          goal.is_completed ? 'bg-accent-income' : 'bg-primary-500'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Action buttons */}
                <div className="pt-3 border-t border-border flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs h-8 px-2.5"
                      onClick={() => {
                        setContributeGoal(goal);
                        setAmountInput('');
                        setFormError('');
                      }}
                    >
                      <ArrowUpRight className="w-3.5 h-3.5 mr-1 text-accent-income" />
                      Add
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs h-8 px-2.5"
                      disabled={goal.saved_amount === 0}
                      onClick={() => {
                        setWithdrawGoal(goal);
                        setAmountInput('');
                        setFormError('');
                      }}
                    >
                      <ArrowDownLeft className="w-3.5 h-3.5 mr-1 text-accent-expense" />
                      Withdraw
                    </Button>
                  </div>

                  <div className="flex items-center space-x-1">
                    <Button variant="ghost" size="sm" onClick={() => handleOpenEdit(goal)}>
                      <Edit2 className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-accent-expense hover:bg-accent-expense/10"
                      onClick={() => setDeletingGoal(goal)}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Add / Edit Goal Modal */}
      <Modal
        isOpen={isAddModalOpen || !!editingGoal}
        onClose={closeModals}
        title={editingGoal ? `Edit Goal: ${editingGoal.name}` : 'Create Savings Goal'}
      >
        <form onSubmit={handleSubmitGoal} className="space-y-4">
          {formError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {formError}
            </div>
          )}

          <Input
            label="Goal Name"
            placeholder="e.g. New Laptop, Emergency Fund"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
          />

          <Input
            label="Target Amount (₹)"
            type="number"
            min="1"
            placeholder="e.g. 50000"
            value={targetAmount}
            onChange={(e) => setTargetAmount(e.target.value)}
            required
          />

          <Input
            label="Target Date (Optional)"
            type="date"
            value={targetDate}
            onChange={(e) => setTargetDate(e.target.value)}
          />

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={closeModals}>
              Cancel
            </Button>
            <Button
              type="submit"
              isLoading={createGoalMutation.isPending || updateGoalMutation.isPending}
            >
              {editingGoal ? 'Save Changes' : 'Create Goal'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Contribute Modal */}
      <Modal
        isOpen={!!contributeGoal}
        onClose={closeModals}
        title={`Contribute to "${contributeGoal?.name}"`}
      >
        <form onSubmit={handleContribute} className="space-y-4">
          {formError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {formError}
            </div>
          )}

          <p className="text-xs text-text-secondary">
            Wallet balance available: <span className="font-semibold text-text-primary">{formatINR(wallet?.current_balance || 0)}</span>
          </p>

          <Input
            label="Contribution Amount (₹)"
            type="number"
            min="1"
            placeholder="e.g. 2000"
            value={amountInput}
            onChange={(e) => setAmountInput(e.target.value)}
            required
            autoFocus
          />

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={closeModals}>
              Cancel
            </Button>
            <Button type="submit" isLoading={contributeMutation.isPending}>
              Transfer to Goal
            </Button>
          </div>
        </form>
      </Modal>

      {/* Withdraw Modal */}
      <Modal
        isOpen={!!withdrawGoal}
        onClose={closeModals}
        title={`Withdraw from "${withdrawGoal?.name}"`}
      >
        <form onSubmit={handleWithdraw} className="space-y-4">
          {formError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {formError}
            </div>
          )}

          <p className="text-xs text-text-secondary">
            Saved amount available: <span className="font-semibold text-text-primary">{formatINR(withdrawGoal?.saved_amount || 0)}</span>
          </p>

          <Input
            label="Withdrawal Amount (₹)"
            type="number"
            min="1"
            max={withdrawGoal?.saved_amount}
            placeholder="e.g. 1000"
            value={amountInput}
            onChange={(e) => setAmountInput(e.target.value)}
            required
            autoFocus
          />

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={closeModals}>
              Cancel
            </Button>
            <Button type="submit" isLoading={withdrawMutation.isPending}>
              Transfer to Wallet
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Goal Modal */}
      <Modal
        isOpen={!!deletingGoal}
        onClose={() => setDeletingGoal(null)}
        title="Delete Savings Goal"
      >
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">
            Are you sure you want to delete <span className="font-semibold text-text-primary">"{deletingGoal?.name}"</span>?
          </p>
          {deletingGoal && deletingGoal.saved_amount > 0 && (
            <div className="p-3 rounded-lg bg-accent-income/10 border border-accent-income/20 text-xs text-text-primary">
              <span className="font-bold text-accent-income">Refund Guarantee:</span> The saved amount of{' '}
              <span className="font-bold">{formatINR(deletingGoal.saved_amount)}</span> will be automatically refunded
              back to your wallet immediately upon deletion.
            </div>
          )}

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" onClick={() => setDeletingGoal(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              className="bg-accent-expense hover:bg-accent-expense/90"
              isLoading={deleteGoalMutation.isPending}
              onClick={() => deletingGoal && deleteGoalMutation.mutate(deletingGoal.id)}
            >
              Confirm Delete
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
