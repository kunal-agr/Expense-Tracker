import React from 'react';
import { cn } from '../../lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'danger' | 'warning' | 'outline' | 'income' | 'neutral' | 'primary';
}

export function Badge({
  className,
  variant = 'default',
  children,
  ...props
}: BadgeProps) {
  const variants = {
    default: 'bg-surface-2 text-text-muted border-border',
    success: 'bg-income/10 text-income border-income/30',
    danger: 'bg-expense/10 text-expense border-expense/30',
    warning: 'bg-warning/10 text-warning border-warning/30',
    outline: 'bg-transparent text-text border-border',
    income: 'bg-income/10 text-income border-income/30',
    neutral: 'bg-surface-2 text-text-muted border-border',
    primary: 'bg-accent/10 text-accent border-accent/30',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium border select-none',
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export default Badge;
