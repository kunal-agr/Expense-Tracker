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
  PieChart,
  Calendar,
  AlertTriangle,
  Plus,
  Edit2,
  Trash2,
  TrendingUp,
  CheckCircle2,
  Info
} from 'lucide-react';

interface CategoryBudgetStatus {
  category_id: number;
  category_name: string;
  budget_amount: number;
  spent: number;
  remaining: number;
  percentage: number;
}

interface OverallBudgetStatus {
  has_budget: boolean;
  base_budget: number;
  effective_budget: number;
  carry_forward: number;
  spent: number;
  remaining: number;
  percentage: number;
}

interface BudgetStatusResponse {
  month: string;
  overall: OverallBudgetStatus;
  categories: CategoryBudgetStatus[];
  sum_category_budgets: number;
}

interface CategoryItem {
  id: number;
  name: string;
  is_protected: boolean;
  parent_id: number | null;
  subcategories?: CategoryItem[];
}

export default function BudgetsPage() {
  const queryClient = useQueryClient();
  const currentMonth = new Date().toISOString().slice(0, 7);
  const [selectedMonth, setSelectedMonth] = useState(currentMonth);

  // Modals
  const [isOverallModalOpen, setIsOverallModalOpen] = useState(false);
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<{ id: number; name: string; amount: number } | null>(null);

  // Form states
  const [overallAmount, setOverallAmount] = useState('');
  const [selectedCatId, setSelectedCatId] = useState('');
  const [catAmount, setCatAmount] = useState('');
  const [formError, setFormError] = useState('');

  const { data: status, isLoading } = useQuery<BudgetStatusResponse>({
    queryKey: ['budgets-status', selectedMonth],
    queryFn: async () => {
      const res = await api.get(`/budgets/status?month=${selectedMonth}`);
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

  // Flatten categories for select dropdown
  const allCategories = React.useMemo(() => {
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

  // Overall budget mutation
  const overallMutation = useMutation({
    mutationFn: async (amount: number) => {
      return api.put('/budgets/overall', { amount });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets-status'] });
      setIsOverallModalOpen(false);
      setFormError('');
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || err.message || 'Failed to update overall budget');
    },
  });

  // Category budget mutation
  const categoryMutation = useMutation({
    mutationFn: async ({ category_id, amount }: { category_id: number; amount: number }) => {
      return api.put(`/budgets/categories/${category_id}`, { amount });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets-status'] });
      setIsCategoryModalOpen(false);
      setEditingCategory(null);
      setFormError('');
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || err.message || 'Failed to update category budget');
    },
  });

  // Delete category budget mutation
  const deleteCategoryMutation = useMutation({
    mutationFn: async (category_id: number) => {
      return api.delete(`/budgets/categories/${category_id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['budgets-status'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || err.message || 'Failed to delete category budget');
    },
  });

  const handleSaveOverall = (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseInt(overallAmount, 10);
    if (isNaN(val) || val <= 0) {
      setFormError('Please enter a valid positive whole rupee amount');
      return;
    }
    overallMutation.mutate(val);
  };

  const handleSaveCategory = (e: React.FormEvent) => {
    e.preventDefault();
    const catId = editingCategory ? editingCategory.id : parseInt(selectedCatId, 10);
    const val = parseInt(catAmount, 10);
    if (!catId || isNaN(catId)) {
      setFormError('Please select a category');
      return;
    }
    if (isNaN(val) || val <= 0) {
      setFormError('Please enter a valid positive whole rupee amount');
      return;
    }
    categoryMutation.mutate({ category_id: catId, amount: val });
  };

  const openEditCat = (cat: CategoryBudgetStatus) => {
    setEditingCategory({ id: cat.category_id, name: cat.category_name, amount: cat.budget_amount });
    setCatAmount(cat.budget_amount.toString());
    setFormError('');
    setIsCategoryModalOpen(true);
  };

  const openAddCat = () => {
    setEditingCategory(null);
    setSelectedCatId('');
    setCatAmount('');
    setFormError('');
    setIsCategoryModalOpen(true);
  };

  const overall = status?.overall;
  const hasOverall = overall?.has_budget === true;
  const catBudgets = status?.categories || [];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">Budgets</h1>
          <p className="text-sm text-text-secondary mt-1">
            Track monthly base limits with chained carry-forward and category constraints.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 bg-surface px-3 py-1.5 rounded-lg border border-border">
            <Calendar className="w-4 h-4 text-text-secondary" />
            <input
              type="month"
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              className="bg-transparent text-sm font-medium text-text-primary focus:outline-none"
            />
          </div>
          <Button onClick={() => {
            setOverallAmount(hasOverall && overall ? overall.base_budget.toString() : '');
            setFormError('');
            setIsOverallModalOpen(true);
          }}>
            <Edit2 className="w-4 h-4 mr-2" />
            {hasOverall ? 'Edit Overall Budget' : 'Set Overall Budget'}
          </Button>
        </div>
      </div>

      {/* Overall Budget Banner / Card */}
      {isLoading ? (
        <Skeleton className="h-44 w-full" />
      ) : !hasOverall || !overall ? (
        <Card className="p-8 text-center bg-primary-500/5 border-dashed border-2 border-primary-500/30">
          <PieChart className="w-12 h-12 mx-auto mb-3 text-primary-500" />
          <h3 className="text-lg font-semibold text-text-primary">No Overall Budget Set</h3>
          <p className="text-sm text-text-secondary max-w-md mx-auto mt-1 mb-4">
            Setting an overall monthly budget enables carry-forward tracking, alerts at 80% and 100%, and category budget limits.
          </p>
          <Button onClick={() => {
            setOverallAmount('');
            setIsOverallModalOpen(true);
          }}>
            Set Monthly Budget Now
          </Button>
        </Card>
      ) : (
        <Card className="p-6 relative overflow-hidden">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
                Overall Budget • {selectedMonth}
              </span>
              <div className="flex items-baseline space-x-3 mt-1">
                <span className="text-3xl font-extrabold text-text-primary">
                  {formatINR(overall.effective_budget)}
                </span>
                {overall.carry_forward > 0 && (
                  <span className="text-xs font-medium text-accent-income bg-accent-income/10 px-2 py-0.5 rounded-full">
                    +{formatINR(overall.carry_forward)} carry-forward
                  </span>
                )}
              </div>
              <p className="text-xs text-text-muted mt-1">
                Base limit: {formatINR(overall.base_budget)}
              </p>
            </div>

            <div className="flex items-center space-x-6 text-sm">
              <div>
                <span className="text-text-secondary block text-xs">Spent</span>
                <span className="font-bold text-accent-expense text-lg">
                  {formatINR(overall.spent)}
                </span>
              </div>
              <div>
                <span className="text-text-secondary block text-xs">Remaining</span>
                <span className={`font-bold text-lg ${overall.remaining < 0 ? 'text-accent-expense' : 'text-accent-income'}`}>
                  {formatINR(overall.remaining)}
                </span>
              </div>
              <div>
                <span className="text-text-secondary block text-xs">Usage</span>
                <span className="font-bold text-text-primary text-lg">
                  {Math.round(overall.percentage)}%
                </span>
              </div>
            </div>
          </div>

          {/* Progress bar */}
          <div className="w-full bg-surface-elevated rounded-full h-3 overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                overall.percentage >= 100
                  ? 'bg-accent-expense'
                  : overall.percentage >= 80
                  ? 'bg-primary-500'
                  : 'bg-accent-income'
              }`}
              style={{ width: `${Math.min(100, Math.max(0, overall.percentage))}%` }}
            />
          </div>

          {overall.percentage >= 100 && (
            <div className="mt-3 flex items-center space-x-2 text-xs text-accent-expense font-medium">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>You have reached or exceeded 100% of your effective monthly budget!</span>
            </div>
          )}
          {overall.percentage >= 80 && overall.percentage < 100 && (
            <div className="mt-3 flex items-center space-x-2 text-xs text-primary-500 font-medium">
              <Info className="w-4 h-4 flex-shrink-0" />
              <span>You have crossed 80% of your monthly budget limit.</span>
            </div>
          )}
        </Card>
      )}

      {/* Category Budgets Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-text-primary">Category Budgets</h2>
            <p className="text-xs text-text-secondary">
              Total assigned: {formatINR(status?.sum_category_budgets || catBudgets.reduce((acc, c) => acc + c.budget_amount, 0))} / {formatINR(overall?.base_budget || 0)}
            </p>
          </div>
          <Button
            size="sm"
            onClick={openAddCat}
            disabled={!hasOverall}
            title={!hasOverall ? 'Set overall budget first' : undefined}
          >
            <Plus className="w-4 h-4 mr-1.5" />
            Add Category Budget
          </Button>
        </div>

        {catBudgets.length === 0 ? (
          <Card className="p-8 text-center text-text-secondary">
            <p className="text-sm font-medium">No category budgets created yet</p>
            <p className="text-xs text-text-muted mt-1">
              Assign category limits to keep close control on specific expenses.
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {catBudgets.map((cat) => {
              const remaining = cat.remaining;
              const isOver = cat.percentage >= 100;
              const isWarning = cat.percentage >= 80 && !isOver;

              return (
                <Card key={cat.category_id} className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-text-primary">{cat.category_name}</h4>
                      <span className="text-xs text-text-secondary">
                        Limit: {formatINR(cat.budget_amount)}
                      </span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <Button variant="ghost" size="sm" onClick={() => openEditCat(cat)}>
                        <Edit2 className="w-3.5 h-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteCategoryMutation.mutate(cat.category_id)}
                        className="text-accent-expense hover:bg-accent-expense/10"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </div>

                  <div className="flex justify-between items-baseline text-xs">
                    <span className="text-text-secondary">
                      Spent: <span className="font-bold text-text-primary">{formatINR(cat.spent)}</span>
                    </span>
                    <span className={remaining < 0 ? 'text-accent-expense font-bold' : 'text-text-secondary'}>
                      {remaining < 0 ? `Over by ${formatINR(Math.abs(remaining))}` : `Remaining: ${formatINR(remaining)}`}
                    </span>
                  </div>

                  <div className="w-full bg-surface-elevated rounded-full h-2 overflow-hidden">
                    <div
                      className={`h-full ${
                        isOver ? 'bg-accent-expense' : isWarning ? 'bg-primary-500' : 'bg-accent-income'
                      }`}
                      style={{ width: `${Math.min(100, Math.max(0, cat.percentage))}%` }}
                    />
                  </div>

                  <div className="flex justify-between items-center text-[11px] text-text-muted">
                    <span>{Math.round(cat.percentage)}% consumed</span>
                    {isOver && <span className="text-accent-expense font-semibold">Exceeded</span>}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Overall Budget Modal */}
      <Modal
        isOpen={isOverallModalOpen}
        onClose={() => setIsOverallModalOpen(false)}
        title="Set Overall Monthly Budget"
      >
        <form onSubmit={handleSaveOverall} className="space-y-4">
          {formError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {formError}
            </div>
          )}

          <Input
            label="Base Monthly Budget (₹)"
            type="number"
            min="1"
            placeholder="e.g. 50000"
            value={overallAmount}
            onChange={(e) => setOverallAmount(e.target.value)}
            required
            autoFocus
          />

          <p className="text-xs text-text-muted">
            Unused amounts from prior months automatically carry forward to give your effective budget.
          </p>

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={() => setIsOverallModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={overallMutation.isPending}>
              Save Budget
            </Button>
          </div>
        </form>
      </Modal>

      {/* Category Budget Modal */}
      <Modal
        isOpen={isCategoryModalOpen}
        onClose={() => setIsCategoryModalOpen(false)}
        title={editingCategory ? `Edit Budget: ${editingCategory.name}` : 'Add Category Budget'}
      >
        <form onSubmit={handleSaveCategory} className="space-y-4">
          {formError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {formError}
            </div>
          )}

          {!editingCategory && (
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Select Category</label>
              <select
                value={selectedCatId}
                onChange={(e) => setSelectedCatId(e.target.value)}
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
          )}

          <Input
            label="Monthly Limit (₹)"
            type="number"
            min="1"
            placeholder="e.g. 10000"
            value={catAmount}
            onChange={(e) => setCatAmount(e.target.value)}
            required
            autoFocus
          />

          <p className="text-xs text-text-muted">
            Rule: The sum of all category budgets cannot exceed your overall base budget limit.
          </p>

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={() => setIsCategoryModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={categoryMutation.isPending}>
              Save Limit
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
