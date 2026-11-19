import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';

export function LoginPage() {
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const user = await login({ login: loginId, password });
      if (!user.has_wallet) {
        navigate('/setup');
      } else {
        navigate('/');
      }
    } catch (err: any) {
      setError(err.message || 'Invalid credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-bg">
      <Card className="w-full max-w-sm border-border bg-surface shadow-lg">
        <CardHeader className="text-center">
          <div className="mx-auto h-9 w-9 rounded-control bg-accent flex items-center justify-center text-accent-text font-bold text-base mb-2">
            ₹
          </div>
          <CardTitle className="text-lg">Welcome back</CardTitle>
          <CardDescription>Sign in to your Expense Tracker account</CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {error && (
            <div className="p-2.5 rounded-control bg-expense/10 border border-expense/20 text-expense text-xs">
              {error}
            </div>
          )}

          <Input
            label="Email or Username"
            type="text"
            required
            autoFocus
            placeholder="name@example.com or username"
            value={loginId}
            onChange={(e) => setLoginId(e.target.value)}
          />

          <Input
            label="Password"
            type="password"
            required
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <Button type="submit" className="w-full mt-2" isLoading={loading}>
            Sign In
          </Button>
        </form>

        <div className="mt-5 text-center text-xs text-text-muted">
          Don't have an account?{' '}
          <Link to="/register" className="text-accent hover:underline font-medium">
            Create account
          </Link>
        </div>
      </Card>
    </div>
  );
}

export default LoginPage;
