import React from 'react';
import { cn } from '../../lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = 'text', label, error, helperText, id, ...props }, ref) => {
    const inputId = id || props.name;

    return (
      <div className="w-full space-y-1">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-xs font-medium text-text-muted select-none"
          >
            {label}
          </label>
        )}
        <input
          id={inputId}
          type={type}
          ref={ref}
          className={cn(
            'flex h-8 w-full rounded-control border border-border bg-surface px-2.5 py-1 text-xs text-text placeholder:text-text-muted/60 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50',
            error && 'border-expense focus-visible:ring-expense',
            className
          )}
          {...props}
        />
        {error && <p className="text-[11px] text-expense">{error}</p>}
        {helperText && !error && (
          <p className="text-[11px] text-text-muted">{helperText}</p>
        )}
      </div>
    );
  }
);
Input.displayName = 'Input';

export default Input;
