import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';

export function RegisterPage() {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Username validation check
    const cleanUser = username.trim().toLowerCase();
    if (!/^[a-z0-9_]{3,20}$/.test(cleanUser)) {
      setError('Username must be 3-20 characters long and contain only lowercase letters, digits, and underscores.');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    setLoading(true);
    try {
      await register({
        email: email.trim().toLowerCase(),
        username: cleanUser,
        password,
      });
      // New user always proceeds to opening balance setup (FR-009)
      navigate('/setup');
    } catch (err: any) {
      setError(err.message || 'Registration failed.');
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
          <CardTitle className="text-lg">Create an Account</CardTitle>
          <CardDescription>Start tracking your expenses with precision</CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {error && (
            <div className="p-2.5 rounded-control bg-expense/10 border border-expense/20 text-expense text-xs">
              {error}
            </div>
          )}

          <Input
            label="Email Address"
            type="email"
            required
            autoFocus
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <Input
            label="Username"
            type="text"
            required
            placeholder="alex_smith"
            helperText="3-20 chars: lowercase, numbers, underscores"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />

          <Input
            label="Password"
            type="password"
            required
            placeholder="At least 6 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <Button type="submit" className="w-full mt-2" isLoading={loading}>
            Create Account
          </Button>
        </form>

        <div className="mt-5 text-center text-xs text-text-muted">
          Already have an account?{' '}
          <Link to="/login" className="text-accent hover:underline font-medium">
            Sign in
          </Link>
        </div>
      </Card>
    </div>
  );
}

export default RegisterPage;
