import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus,
  Search,
  Filter,
  ArrowUpDown,
  Edit2,
  Trash2,
  Receipt,
  Download,
  AlertCircle,
} from 'lucide-react';
import { api } from '../lib/api';
import { formatINR, formatDate } from '../lib/utils';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Modal } from '../components/ui/Modal';
import { Badge } from '../components/ui/Badge';
import { Skeleton } from '../components/ui/Skeleton';

interface TransactionItem {
  id: number;
  user_id: number;
  wallet_id: number;
  type: 'income' | 'expense';
  amount: number;
  date: string;
  category_id: number;
  category_name: string;
  subcategory_id?: number;
  subcategory_name?: string;
  payment_method: string;
  note?: string;
  source: string;
  read_only: boolean;
  created_at: string;
}

export function TransactionsPage() {
  const queryClient = useQueryClient();

  // Filters & Pagination State
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [paymentFilter, setPaymentFilter] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [sortBy, setSortBy] = useState<'date' | 'amount'>('date');
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc');
  const [page, setPage] = useState(1);

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingTx, setEditingTx] = useState<TransactionItem | null>(null);
  const [deletingTx, setDeletingTx] = useState<TransactionItem | null>(null);
  const [formError, setFormError] = useState('');

  // Form inputs
  const [formType, setFormType] = useState<'income' | 'expense'>('expense');
  const [formAmount, setFormAmount] = useState('');
  const [formDate, setFormDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [formCategory, setFormCategory] = useState('');
  const [formSubcategory, setFormSubcategory] = useState('');
  const [formPaymentMethod, setFormPaymentMethod] = useState('UPI');
  const [formNote, setFormNote] = useState('');

  // 1. Fetch categories for filters and form
  const { data: categories = [] } = useQuery<any[]>({
    queryKey: ['categories'],
    queryFn: () => api.get('/categories'),
  });

  // 2. Fetch Transactions
  const queryParams = new URLSearchParams({
    page: String(page),
    limit: '20',
    sort_by: sortBy,
    sort_dir: sortDir,
  });
  if (search) queryParams.set('search', search);
  if (typeFilter) queryParams.set('type', typeFilter);
  if (categoryFilter) queryParams.set('category_id', categoryFilter);
  if (paymentFilter) queryParams.set('payment_method', paymentFilter);
  if (fromDate) queryParams.set('from_date', fromDate);
  if (toDate) queryParams.set('to_date', toDate);

  const { data: txData, isLoading } = useQuery<{
    items: TransactionItem[];
    total: number;
    pages: number;
  }>({
    queryKey: ['transactions', queryParams.toString()],
    queryFn: () => api.get(`/transactions?${queryParams.toString()}`),
  });

  // Create Mutation
  const createMutation = useMutation({
    mutationFn: (newTx: any) => api.post('/transactions', newTx),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['wallet-balance'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setIsCreateOpen(false);
      resetForm();
    },
    onError: (err: any) => setFormError(err.message || 'Failed to create transaction.'),
  });

  // Update Mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) =>
      api.patch(`/transactions/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['wallet-balance'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setEditingTx(null);
      resetForm();
    },
    onError: (err: any) => setFormError(err.message || 'Failed to update transaction.'),
  });

  // Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.del(`/transactions/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['wallet-balance'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setDeletingTx(null);
    },
    onError: (err: any) => alert(err.message || 'Failed to delete transaction.'),
  });

  const resetForm = () => {
    setFormAmount('');
    setFormDate(new Date().toISOString().split('T')[0]);
    setFormCategory('');
    setFormSubcategory('');
    setFormPaymentMethod('UPI');
    setFormNote('');
    setFormError('');
  };

  const handleOpenCreate = () => {
    resetForm();
    setIsCreateOpen(true);
  };

  const handleOpenEdit = (tx: TransactionItem) => {
    setEditingTx(tx);
    setFormType(tx.type);
    setFormAmount(String(tx.amount));
    setFormDate(tx.date);
    setFormCategory(String(tx.category_id));
    setFormSubcategory(tx.subcategory_id ? String(tx.subcategory_id) : '');
    setFormPaymentMethod(tx.payment_method);
    setFormNote(tx.note || '');
    setFormError('');
  };

  const handleSaveCreate = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    const amt = parseInt(formAmount, 10);
    if (isNaN(amt) || amt < 1) {
      setFormError('Amount must be a whole rupee value of at least ₹1.');
      return;
    }
    if (!formCategory) {
      setFormError('Please select a category.');
      return;
    }

    createMutation.mutate({
      type: formType,
      amount: amt,
      date: formDate,
      category_id: parseInt(formCategory, 10),
      subcategory_id: formSubcategory ? parseInt(formSubcategory, 10) : undefined,
      payment_method: formPaymentMethod,
      note: formNote ? formNote.trim() : undefined,
    });
  };

  const handleSaveEdit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTx) return;
    setFormError('');

    const amt = parseInt(formAmount, 10);
    if (isNaN(amt) || amt < 1) {
      setFormError('Amount must be a whole rupee value of at least ₹1.');
      return;
    }

    updateMutation.mutate({
      id: editingTx.id,
      data: {
        amount: amt,
        date: formDate,
        category_id: formCategory ? parseInt(formCategory, 10) : undefined,
        subcategory_id: formSubcategory ? parseInt(formSubcategory, 10) : null,
        payment_method: formPaymentMethod,
        note: formNote ? formNote.trim() : null,
      },
    });
  };

  const activeCategoryObj = categories.find((c) => String(c.id) === formCategory);
  const filteredCategories = categories.filter((c) => c.type === formType);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-text">Transactions</h1>
          <p className="text-xs text-text-muted">Manage your income and expenses</p>
        </div>
        <Button onClick={handleOpenCreate} size="sm">
          <Plus className="h-3.5 w-3.5" /> Add Transaction
        </Button>
      </div>

      {/* Filter Toolbar */}
      <Card className="p-3 space-y-2.5">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
          {/* Search text */}
          <div className="sm:col-span-2 relative">
            <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-text-muted" />
            <input
              type="text"
              placeholder="Search notes..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="h-8 w-full rounded-control border border-border bg-surface pl-8 pr-2.5 text-xs text-text placeholder:text-text-muted/60 focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>

          {/* Type Filter */}
          <Select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Types</option>
            <option value="income">Income</option>
            <option value="expense">Expense</option>
          </Select>

          {/* Category Filter */}
          <Select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>

          {/* Payment Method Filter */}
          <Select
            value={paymentFilter}
            onChange={(e) => {
              setPaymentFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Methods</option>
            <option value="UPI">UPI</option>
            <option value="Card">Card</option>
            <option value="Cash">Cash</option>
          </Select>

          {/* Sort By */}
          <Select
            value={`${sortBy}-${sortDir}`}
            onChange={(e) => {
              const [sb, sd] = e.target.value.split('-');
              setSortBy(sb as any);
              setSortDir(sd as any);
            }}
          >
            <option value="date-desc">Newest First</option>
            <option value="date-asc">Oldest First</option>
            <option value="amount-desc">Highest Amount</option>
            <option value="amount-asc">Lowest Amount</option>
          </Select>
        </div>
      </Card>

      {/* Transactions Table */}
      <Card className="p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-border bg-surface-2/60 text-text-muted font-medium">
                <th className="py-2.5 px-3">Date</th>
                <th className="py-2.5 px-3">Category</th>
                <th className="py-2.5 px-3">Note</th>
                <th className="py-2.5 px-3">Method</th>
                <th className="py-2.5 px-3 text-right">Amount</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                [...Array(6)].map((_, i) => (
                  <tr key={i}>
                    <td colSpan={6} className="py-3 px-3">
                      <Skeleton className="h-4 w-full" />
                    </td>
                  </tr>
                ))
              ) : txData?.items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-xs text-text-muted">
                    No transactions found.
                  </td>
                </tr>
              ) : (
                txData?.items.map((tx) => (
                  <tr key={tx.id} className="hover:bg-surface-2/40 transition-colors">
                    <td className="py-2.5 px-3 whitespace-nowrap text-text font-medium">
                      {formatDate(tx.date)}
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-1.5">
                        <span className="text-text">{tx.category_name}</span>
                        {tx.subcategory_name && (
                          <span className="text-text-muted">/ {tx.subcategory_name}</span>
                        )}
                        {tx.source === 'split' && (
                          <Badge variant="default" className="text-[9px]">
                            Split
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-text-muted truncate max-w-xs">
                      {tx.note || '-'}
                    </td>
                    <td className="py-2.5 px-3 text-text-muted whitespace-nowrap">
                      {tx.payment_method}
                    </td>
                    <td
                      className={`py-2.5 px-3 text-right font-mono-num font-semibold whitespace-nowrap ${
                        tx.type === 'income' ? 'text-income' : 'text-text'
                      }`}
                    >
                      {tx.type === 'income' ? '+' : '-'}
                      {formatINR(tx.amount)}
                    </td>
                    <td className="py-2.5 px-3 text-right whitespace-nowrap">
                      {tx.read_only ? (
                        <span className="text-[10px] text-text-muted/60 italic">Read-only</span>
                      ) : (
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => handleOpenEdit(tx)}
                            className="p-1 rounded text-text-muted hover:text-text hover:bg-surface-2 transition-colors"
                            title="Edit transaction"
                          >
                            <Edit2 className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => setDeletingTx(tx)}
                            className="p-1 rounded text-text-muted hover:text-expense hover:bg-surface-2 transition-colors"
                            title="Delete transaction"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Toolbar */}
        {txData && txData.pages > 1 && (
          <div className="p-3 border-t border-border flex items-center justify-between text-xs">
            <span className="text-text-muted">
              Showing page {page} of {txData.pages} ({txData.total} total)
            </span>
            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= txData.pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Create Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Record Transaction"
        description="Add a new income or expense entry"
      >
        <form onSubmit={handleSaveCreate} className="space-y-3 pt-1">
          {formError && (
            <div className="p-2 rounded bg-expense/10 text-expense text-xs">{formError}</div>
          )}

          {/* Income / Expense Toggle */}
          <div className="flex rounded-control border border-border p-0.5 bg-surface-2">
            <button
              type="button"
              onClick={() => {
                setFormType('expense');
                setFormCategory('');
                setFormSubcategory('');
              }}
              className={`flex-1 py-1 rounded text-xs font-semibold transition-colors ${
                formType === 'expense' ? 'bg-surface text-expense shadow-sm' : 'text-text-muted'
              }`}
            >
              Expense
            </button>
            <button
              type="button"
              onClick={() => {
                setFormType('income');
                setFormCategory('');
                setFormSubcategory('');
              }}
              className={`flex-1 py-1 rounded text-xs font-semibold transition-colors ${
                formType === 'income' ? 'bg-surface text-income shadow-sm' : 'text-text-muted'
              }`}
            >
              Income
            </button>
          </div>

          <Input
            label="Amount (INR)"
            type="number"
            step="1"
            min="1"
            required
            autoFocus
            className="font-mono-num font-semibold"
            placeholder="0"
            value={formAmount}
            onChange={(e) => setFormAmount(e.target.value)}
          />

          <Input
            label="Date"
            type="date"
            max={new Date().toISOString().split('T')[0]}
            required
            value={formDate}
            onChange={(e) => setFormDate(e.target.value)}
          />

          <Select
            label="Category"
            required
            value={formCategory}
            onChange={(e) => {
              setFormCategory(e.target.value);
              setFormSubcategory('');
            }}
          >
            <option value="">Select category</option>
            {filteredCategories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>

          {activeCategoryObj?.subcategories?.length > 0 && (
            <Select
              label="Subcategory (optional)"
              value={formSubcategory}
              onChange={(e) => setFormSubcategory(e.target.value)}
            >
              <option value="">None</option>
              {activeCategoryObj.subcategories.map((sub: any) => (
                <option key={sub.id} value={sub.id}>
                  {sub.name}
                </option>
              ))}
            </Select>
          )}

          <Select
            label="Payment Method"
            value={formPaymentMethod}
            onChange={(e) => setFormPaymentMethod(e.target.value)}
          >
            <option value="UPI">UPI</option>
            <option value="Card">Card</option>
            <option value="Cash">Cash</option>
          </Select>

          <Input
            label="Note (optional)"
            type="text"
            placeholder="Lunch with team, fuel..."
            value={formNote}
            onChange={(e) => setFormNote(e.target.value)}
          />

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={createMutation.isPending}>
              Save Transaction
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Modal */}
      <Modal
        isOpen={!!editingTx}
        onClose={() => setEditingTx(null)}
        title="Edit Transaction"
      >
        <form onSubmit={handleSaveEdit} className="space-y-3 pt-1">
          {formError && (
            <div className="p-2 rounded bg-expense/10 text-expense text-xs">{formError}</div>
          )}

          <Input
            label="Amount (INR)"
            type="number"
            step="1"
            min="1"
            required
            className="font-mono-num font-semibold"
            value={formAmount}
            onChange={(e) => setFormAmount(e.target.value)}
          />

          <Input
            label="Date"
            type="date"
            max={new Date().toISOString().split('T')[0]}
            required
            value={formDate}
            onChange={(e) => setFormDate(e.target.value)}
          />

          <Select
            label="Category"
            required
            value={formCategory}
            onChange={(e) => {
              setFormCategory(e.target.value);
              setFormSubcategory('');
            }}
          >
            {filteredCategories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>

          {activeCategoryObj?.subcategories?.length > 0 && (
            <Select
              label="Subcategory (optional)"
              value={formSubcategory}
              onChange={(e) => setFormSubcategory(e.target.value)}
            >
              <option value="">None</option>
              {activeCategoryObj.subcategories.map((sub: any) => (
                <option key={sub.id} value={sub.id}>
                  {sub.name}
                </option>
              ))}
            </Select>
          )}

          <Select
            label="Payment Method"
            value={formPaymentMethod}
            onChange={(e) => setFormPaymentMethod(e.target.value)}
          >
            <option value="UPI">UPI</option>
            <option value="Card">Card</option>
            <option value="Cash">Cash</option>
          </Select>

          <Input
            label="Note"
            type="text"
            value={formNote}
            onChange={(e) => setFormNote(e.target.value)}
          />

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setEditingTx(null)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={updateMutation.isPending}>
              Update
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deletingTx}
        onClose={() => setDeletingTx(null)}
        title="Delete Transaction"
        maxWidth="sm"
      >
        <div className="space-y-3 pt-1 text-xs">
          <p className="text-text-muted">
            Are you sure you want to delete this {deletingTx?.type} transaction of{' '}
            <strong className="text-text font-mono-num">{formatINR(deletingTx?.amount || 0)}</strong>?
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setDeletingTx(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              isLoading={deleteMutation.isPending}
              onClick={() => deletingTx && deleteMutation.mutate(deletingTx.id)}
            >
              Delete
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default TransactionsPage;
