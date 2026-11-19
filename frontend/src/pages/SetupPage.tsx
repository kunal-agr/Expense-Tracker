import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import { Card, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';

export function SetupPage() {
  const [openingBalance, setOpeningBalance] = useState('5000');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { setWalletInitialized } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const amt = parseInt(openingBalance, 10);
    if (isNaN(amt) || amt < 100) {
      setError('Opening balance must be at least ₹100 in whole rupees.');
      return;
    }

    setLoading(true);
    try {
      await api.put('/me/opening-balance', { opening_balance: amt });
      setWalletInitialized();
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Failed to setup opening balance.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-bg">
      <Card className="w-full max-w-sm border-border bg-surface shadow-xl">
        <CardHeader className="text-center">
          <div className="mx-auto h-10 w-10 rounded-full bg-accent/15 border border-accent/30 flex items-center justify-center text-accent font-bold text-lg mb-2">
            ₹
          </div>
          <CardTitle className="text-lg">Set Up Your Wallet</CardTitle>
          <CardDescription>
            Enter your current account or cash balance to start tracking. (Minimum ₹100)
          </CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-2.5 rounded-control bg-expense/10 border border-expense/20 text-expense text-xs">
              {error}
            </div>
          )}

          <div className="relative">
            <span className="absolute left-3 top-7 text-xs font-semibold text-text-muted">
              ₹
            </span>
            <Input
              label="Opening Balance"
              type="number"
              step="1"
              min="100"
              required
              autoFocus
              className="pl-7 font-mono-num font-semibold text-sm h-9"
              placeholder="5000"
              value={openingBalance}
              onChange={(e) => setOpeningBalance(e.target.value)}
              helperText="Whole rupees only. You can adjust this later in settings."
            />
          </div>

          <Button type="submit" className="w-full mt-2 h-9" isLoading={loading}>
            Start Tracking
          </Button>
        </form>
      </Card>
    </div>
  );
}

export default SetupPage;
