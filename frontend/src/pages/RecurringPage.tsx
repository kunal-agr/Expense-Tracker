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
  Repeat,
  Plus,
  Play,
  Pause,
  Trash2,
  Calendar,
  AlertCircle,
  ArrowUpRight,
  ArrowDownLeft
} from 'lucide-react';

interface RecurringRule {
  id: string;
  type: 'income' | 'expense';
  amount: number;
  category_id: string;
  category_name?: string;
  description: string | null;
  day_of_month: number;
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
}

interface CategoryItem {
  id: string;
  name: string;
  parent_id: string | null;
  subcategories?: CategoryItem[];
}

export default function RecurringPage() {
  const queryClient = useQueryClient();

  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [deletingRule, setDeletingRule] = useState<RecurringRule | null>(null);

  // Form states
  const [type, setType] = useState<'income' | 'expense'>('expense');
  const [amount, setAmount] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [description, setDescription] = useState('');
  const [dayOfMonth, setDayOfMonth] = useState('1');
  const [formError, setFormError] = useState('');

  const { data: rules = [], isLoading } = useQuery<RecurringRule[]>({
    queryKey: ['recurring-rules'],
    queryFn: async () => {
      const res = await api.get('/recurring');
      return res.data;
    },
  });

  const { data: categories = [] } = useQuery<CategoryItem[]>({
    queryKey: ['categories'],
    queryFn: async () => {
      const res = await api.get('/categories');
      return res.data;
    },
  });

  const allCategories = React.useMemo(() => {
    const list: { id: string; name: string }[] = [];
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

  const createRuleMutation = useMutation({
    mutationFn: async (payload: any) => {
      return api.post('/recurring', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recurring-rules'] });
      closeModals();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || 'Failed to create recurring rule');
    },
  });

  const toggleRuleMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) => {
      return api.patch(`/recurring/${id}`, { is_active });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recurring-rules'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to update rule status');
    },
  });

  const deleteRuleMutation = useMutation({
    mutationFn: async (id: string) => {
      return api.delete(`/recurring/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recurring-rules'] });
      setDeletingRule(null);
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to delete rule');
      setDeletingRule(null);
    },
  });

  const closeModals = () => {
    setIsAddModalOpen(false);
    setDeletingRule(null);
    setType('expense');
    setAmount('');
    setCategoryId('');
    setDescription('');
    setDayOfMonth('1');
    setFormError('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseInt(amount, 10);
    const day = parseInt(dayOfMonth, 10);

    if (isNaN(val) || val <= 0) {
      setFormError('Amount must be a positive whole rupee value');
      return;
    }
    if (!categoryId) {
      setFormError('Please select a category');
      return;
    }
    if (isNaN(day) || day < 1 || day > 31) {
      setFormError('Day of month must be between 1 and 31');
      return;
    }

    createRuleMutation.mutate({
      type,
      amount: val,
      category_id: categoryId,
      description: description.trim() || null,
      day_of_month: day,
    });
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">Recurring Rules</h1>
          <p className="text-sm text-text-secondary mt-1">
            Automate monthly recurring expenses and incomes (e.g. rent, SIP, salary, subscriptions).
          </p>
        </div>
        <Button onClick={() => setIsAddModalOpen(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Create Rule
        </Button>
      </div>

      {/* Rules List */}
      <Card>
        {isLoading ? (
          <div className="p-4 space-y-4">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : rules.length === 0 ? (
          <div className="p-12 text-center text-text-secondary">
            <Repeat className="w-12 h-12 mx-auto mb-3 opacity-40" />
            <h3 className="text-base font-semibold text-text-primary">No recurring rules configured</h3>
            <p className="text-sm mt-1 mb-4">
              Add rules to automatically record monthly bills, subscriptions, or salaries on specific days.
            </p>
            <Button onClick={() => setIsAddModalOpen(true)}>Create Your First Rule</Button>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {rules.map((rule) => {
              const isExpense = rule.type === 'expense';

              return (
                <div
                  key={rule.id}
                  className={`p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition ${
                    !rule.is_active ? 'opacity-60 bg-surface/30' : 'hover:bg-surface-elevated/40'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <div
                      className={`p-2.5 rounded-xl ${
                        isExpense ? 'bg-accent-expense/10 text-accent-expense' : 'bg-accent-income/10 text-accent-income'
                      }`}
                    >
                      {isExpense ? <ArrowDownLeft className="w-5 h-5" /> : <ArrowUpRight className="w-5 h-5" />}
                    </div>

                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-text-primary">
                          {rule.description || rule.category_name || 'Recurring Rule'}
                        </span>
                        <Badge variant={rule.is_active ? 'income' : 'neutral'}>
                          {rule.is_active ? 'Active' : 'Paused'}
                        </Badge>
                      </div>
                      <div className="flex items-center space-x-3 text-xs text-text-secondary mt-0.5">
                        <span>Category: {rule.category_name}</span>
                        <span>•</span>
                        <span className="flex items-center">
                          <Calendar className="w-3 h-3 mr-1" /> Every {rule.day_of_month}th of month
                        </span>
                        {rule.last_run_at && (
                          <>
                            <span>•</span>
                            <span>Last run: {new Date(rule.last_run_at).toLocaleDateString()}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-4 self-end sm:self-auto">
                    <div className="text-right">
                      <span
                        className={`text-lg font-bold ${
                          isExpense ? 'text-accent-expense' : 'text-accent-income'
                        }`}
                      >
                        {isExpense ? '-' : '+'}
                        {formatINR(rule.amount)}
                      </span>
                    </div>

                    <div className="flex items-center space-x-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          toggleRuleMutation.mutate({ id: rule.id, is_active: !rule.is_active })
                        }
                        title={rule.is_active ? 'Pause Rule' : 'Resume Rule'}
                      >
                        {rule.is_active ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 text-accent-income" />}
                      </Button>

                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-accent-expense hover:bg-accent-expense/10"
                        onClick={() => setDeletingRule(rule)}
                        title="Delete Rule"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Create Rule Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={closeModals}
        title="Create Monthly Recurring Rule"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          {formError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {formError}
            </div>
          )}

          {/* Type Selector */}
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">Type</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setType('expense')}
                className={`py-2 text-sm font-medium rounded-lg border transition ${
                  type === 'expense'
                    ? 'border-accent-expense bg-accent-expense/10 text-accent-expense'
                    : 'border-border text-text-secondary hover:bg-surface-elevated'
                }`}
              >
                Expense
              </button>
              <button
                type="button"
                onClick={() => setType('income')}
                className={`py-2 text-sm font-medium rounded-lg border transition ${
                  type === 'income'
                    ? 'border-accent-income bg-accent-income/10 text-accent-income'
                    : 'border-border text-text-secondary hover:bg-surface-elevated'
                }`}
              >
                Income
              </button>
            </div>
          </div>

          <Input
            label="Amount (₹)"
            type="number"
            min="1"
            placeholder="e.g. 15000"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
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
              {allCategories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <Input
            label="Day of Month (1 - 31)"
            type="number"
            min="1"
            max="31"
            value={dayOfMonth}
            onChange={(e) => setDayOfMonth(e.target.value)}
            required
          />
          <p className="text-[11px] text-text-muted">
            For months with fewer days (e.g. Feb 28/29, April 30), runs are clamped automatically to the last day of that month.
          </p>

          <Input
            label="Description (Optional)"
            placeholder="e.g. Apartment Rent, Netflix, SIP"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={closeModals}>
              Cancel
            </Button>
            <Button type="submit" isLoading={createRuleMutation.isPending}>
              Create Rule
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deletingRule}
        onClose={() => setDeletingRule(null)}
        title="Delete Recurring Rule"
      >
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">
            Are you sure you want to delete this recurring rule? Existing transactions generated by past runs will not be affected.
          </p>

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" onClick={() => setDeletingRule(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              className="bg-accent-expense hover:bg-accent-expense/90"
              isLoading={deleteRuleMutation.isPending}
              onClick={() => deletingRule && deleteRuleMutation.mutate(deletingRule.id)}
            >
              Confirm Delete
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
