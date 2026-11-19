import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  ArrowUpRight,
  ArrowDownRight,
  Calendar,
  AlertCircle,
  Plus,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { api } from '../lib/api';
import { formatINR, formatDate } from '../lib/utils';
import { Card, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Skeleton } from '../components/ui/Skeleton';

const CATEGORY_COLORS = [
  '#D98A1F', // Accent Saffron
  '#2E8B57', // Income Green
  '#4A90E2', // Blue
  '#E5A93B', // Warm Yellow
  '#8E44AD', // Purple
  '#E67E22', // Orange
  '#16A085', // Teal
  '#7F8C8D', // Neutral Gray
];

export function DashboardPage() {
  const [selectedMonth, setSelectedMonth] = useState<string>(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', selectedMonth],
    queryFn: () => api.get(`/dashboard?month=${selectedMonth}`),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Skeleton className="h-72 lg:col-span-2" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 text-center text-xs text-expense">
        Failed to load dashboard data. Please try again.
      </div>
    );
  }

  const {
    current_balance,
    this_month,
    category_spending,
    budget_progress,
    recent_transactions,
    goals_progress,
    trend_6_months,
  } = data;

  return (
    <div className="space-y-5">
      {/* Top Banner: Month Filter & Quick CTA */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-text">Dashboard</h1>
          <p className="text-xs text-text-muted">Overview of your finances and monthly spending</p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-control bg-surface border border-border text-xs">
            <Calendar className="h-3.5 w-3.5 text-text-muted" />
            <input
              type="month"
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              className="bg-transparent border-none text-xs text-text focus:outline-none cursor-pointer"
            />
          </div>
          <Link to="/transactions">
            <Button size="sm">
              <Plus className="h-3.5 w-3.5" /> Add Transaction
            </Button>
          </Link>
        </div>
      </div>

      {/* 4 Key Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Wallet Balance */}
        <Card className="p-3.5">
          <div className="flex items-center justify-between text-text-muted text-xs mb-1.5">
            <span>Wallet Balance</span>
            <Wallet className="h-3.5 w-3.5 text-accent" />
          </div>
          <div className="font-mono-num text-xl font-bold text-text">
            {formatINR(current_balance)}
          </div>
          <span className="text-[10px] text-text-muted">Available funds</span>
        </Card>

        {/* Month Income */}
        <Card className="p-3.5">
          <div className="flex items-center justify-between text-text-muted text-xs mb-1.5">
            <span>Income ({selectedMonth})</span>
            <ArrowUpRight className="h-3.5 w-3.5 text-income" />
          </div>
          <div className="font-mono-num text-xl font-bold text-income">
            +{formatINR(this_month.income)}
          </div>
          <span className="text-[10px] text-text-muted">Total credited</span>
        </Card>

        {/* Month Expenses */}
        <Card className="p-3.5">
          <div className="flex items-center justify-between text-text-muted text-xs mb-1.5">
            <span>Expenses ({selectedMonth})</span>
            <ArrowDownRight className="h-3.5 w-3.5 text-expense" />
          </div>
          <div className="font-mono-num text-xl font-bold text-expense">
            -{formatINR(this_month.expense)}
          </div>
          <span className="text-[10px] text-text-muted">Total debited</span>
        </Card>

        {/* Net Savings */}
        <Card className="p-3.5">
          <div className="flex items-center justify-between text-text-muted text-xs mb-1.5">
            <span>Net Savings</span>
            {this_month.net >= 0 ? (
              <TrendingUp className="h-3.5 w-3.5 text-income" />
            ) : (
              <TrendingDown className="h-3.5 w-3.5 text-expense" />
            )}
          </div>
          <div
            className={`font-mono-num text-xl font-bold ${
              this_month.net >= 0 ? 'text-income' : 'text-expense'
            }`}
          >
            {this_month.net >= 0 ? '+' : ''}
            {formatINR(this_month.net)}
          </div>
          <span className="text-[10px] text-text-muted">Income minus expenses</span>
        </Card>
      </div>

      {/* 2-Pane: Trend Chart (Left) + Category Donut (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Income vs Expense 6-Month Trend */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Income vs Expense Trend</CardTitle>
            <CardDescription>Chronological overview of the last 6 months</CardDescription>
          </CardHeader>
          <div className="h-60 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trend_6_months} margin={{ top: 5, right: 10, left: -15, bottom: 5 }}>
                <XAxis dataKey="month" stroke="var(--text-muted)" fontSize={11} tickLine={false} />
                <YAxis
                  stroke="var(--text-muted)"
                  fontSize={11}
                  tickLine={false}
                  tickFormatter={(val) => `₹${val / 1000}k`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--surface)',
                    borderColor: 'var(--border)',
                    borderRadius: '6px',
                    fontSize: '11px',
                  }}
                  formatter={(value: any) => [formatINR(Number(value)), '']}
                />
                <Bar dataKey="income" name="Income" fill="var(--income)" radius={[3, 3, 0, 0]} maxBarSize={28} />
                <Bar dataKey="expense" name="Expense" fill="var(--expense)" radius={[3, 3, 0, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Category Spending Donut */}
        <Card>
          <CardHeader>
            <CardTitle>Category Spending</CardTitle>
            <CardDescription>Breakdown for {selectedMonth}</CardDescription>
          </CardHeader>
          {category_spending.length === 0 ? (
            <div className="h-60 flex items-center justify-center text-xs text-text-muted">
              No expenses recorded for this month.
            </div>
          ) : (
            <div className="flex flex-col items-center">
              <div className="h-44 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={category_spending}
                      dataKey="amount"
                      nameKey="category_name"
                      innerRadius={45}
                      outerRadius={68}
                      paddingAngle={3}
                    >
                      {category_spending.map((entry: any, index: number) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--surface)',
                        borderColor: 'var(--border)',
                        borderRadius: '6px',
                        fontSize: '11px',
                      }}
                      formatter={(val: any) => [formatINR(Number(val)), 'Spent']}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Legend List */}
              <div className="w-full space-y-1.5 mt-2 max-h-36 overflow-y-auto px-1">
                {category_spending.map((c: any, idx: number) => (
                  <div key={c.category_id} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span
                        className="h-2 w-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: CATEGORY_COLORS[idx % CATEGORY_COLORS.length] }}
                      />
                      <span className="text-text-muted truncate">{c.category_name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono-num font-medium text-text">{formatINR(c.amount)}</span>
                      <span className="text-[10px] text-text-muted/70 w-8 text-right">{c.percentage}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* 2-Pane: Budget Progress & Savings Goals (Left) + Recent Transactions (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Budget & Goals Column */}
        <div className="space-y-4">
          {/* Budget Status Widget */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <div>
                <CardTitle>Budget Progress</CardTitle>
                <CardDescription>Base + carry-forward status</CardDescription>
              </div>
              <Link to="/budgets" className="text-xs text-accent hover:underline">
                Manage
              </Link>
            </div>

            {budget_progress.overall.has_budget ? (
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-medium text-text">Overall Monthly Budget</span>
                    <span className="font-mono-num text-text-muted">
                      {formatINR(budget_progress.overall.spent)} / {formatINR(budget_progress.overall.effective_budget)}
                    </span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-surface-2 overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        budget_progress.overall.percentage >= 100
                          ? 'bg-expense'
                          : budget_progress.overall.percentage >= 80
                          ? 'bg-warning'
                          : 'bg-accent'
                      }`}
                      style={{ width: `${Math.min(budget_progress.overall.percentage, 100)}%` }}
                    />
                  </div>
                  {budget_progress.overall.carry_forward > 0 && (
                    <span className="text-[10px] text-text-muted block mt-1">
                      Includes +{formatINR(budget_progress.overall.carry_forward)} carry-forward from previous month.
                    </span>
                  )}
                </div>

                {/* Categories mini bars */}
                {budget_progress.categories.length > 0 && (
                  <div className="pt-2 border-t border-border space-y-2">
                    <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider block">
                      Category Budgets
                    </span>
                    {budget_progress.categories.slice(0, 3).map((cb: any) => (
                      <div key={cb.category_id}>
                        <div className="flex justify-between text-xs mb-0.5">
                          <span className="text-text-muted">{cb.category_name}</span>
                          <span className="font-mono-num text-[11px]">
                            {formatINR(cb.spent)} / {formatINR(cb.budget_amount)}
                          </span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-surface-2 overflow-hidden">
                          <div
                            className={`h-full ${
                              cb.percentage >= 100
                                ? 'bg-expense'
                                : cb.percentage >= 80
                                ? 'bg-warning'
                                : 'bg-accent'
                            }`}
                            style={{ width: `${Math.min(cb.percentage, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="p-4 text-center text-xs text-text-muted">
                No overall budget set.{' '}
                <Link to="/budgets" className="text-accent underline">
                  Set a budget
                </Link>
              </div>
            )}
          </Card>

          {/* Savings Goals Widget */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <div>
                <CardTitle>Savings Goals</CardTitle>
                <CardDescription>Track progress towards your milestones</CardDescription>
              </div>
              <Link to="/goals" className="text-xs text-accent hover:underline">
                View all
              </Link>
            </div>

            {goals_progress.length === 0 ? (
              <div className="p-4 text-center text-xs text-text-muted">
                No savings goals created yet.{' '}
                <Link to="/goals" className="text-accent underline">
                  Create a goal
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {goals_progress.slice(0, 3).map((g: any) => (
                  <div key={g.id} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-text">{g.name}</span>
                      <span className="font-mono-num text-text-muted">
                        {formatINR(g.saved_amount)} / {formatINR(g.target_amount)} ({g.percentage}%)
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-surface-2 overflow-hidden">
                      <div
                        className="h-full bg-income transition-all duration-300"
                        style={{ width: `${g.percentage}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Recent Transactions Column */}
        <Card>
          <div className="flex items-center justify-between mb-3">
            <div>
              <CardTitle>Recent Transactions</CardTitle>
              <CardDescription>Latest spending and credits</CardDescription>
            </div>
            <Link to="/transactions" className="text-xs text-accent hover:underline">
              View all
            </Link>
          </div>

          {recent_transactions.length === 0 ? (
            <div className="p-8 text-center text-xs text-text-muted">
              No transactions recorded yet.
            </div>
          ) : (
            <div className="divide-y divide-border">
              {recent_transactions.map((tx: any) => (
                <div key={tx.id} className="py-2.5 flex items-center justify-between text-xs">
                  <div className="min-w-0 pr-2">
                    <div className="font-medium text-text truncate">
                      {tx.note || tx.category_name}
                    </div>
                    <div className="text-[10px] text-text-muted flex items-center gap-1.5">
                      <span>{formatDate(tx.date)}</span>
                      <span>•</span>
                      <span>{tx.category_name}</span>
                      <span>•</span>
                      <span>{tx.payment_method}</span>
                    </div>
                  </div>
                  <div
                    className={`font-mono-num font-semibold text-xs flex-shrink-0 ${
                      tx.type === 'income' ? 'text-income' : 'text-text'
                    }`}
                  >
                    {tx.type === 'income' ? '+' : '-'}
                    {formatINR(tx.amount)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

export default DashboardPage;
