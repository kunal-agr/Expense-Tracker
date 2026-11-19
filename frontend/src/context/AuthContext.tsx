import React, { createContext, useContext, useEffect, useState } from 'react';
import { api, setAuthToken, getAuthToken } from '../lib/api';

export interface User {
  id: number | string;
  email: string;
  username: string;
  role?: string;
  has_wallet: boolean;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (loginData: { login: string; password: string }) => Promise<User>;
  register: (regData: { email: string; username: string; password: string }) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
  setWalletInitialized: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchCurrentUser = async (): Promise<User | null> => {
    try {
      const userData = await api.get<User>('/me');
      setUser(userData);
      return userData;
    } catch (err) {
      setUser(null);
      setAuthToken(null);
      return null;
    }
  };

  useEffect(() => {
    const initAuth = async () => {
      const token = getAuthToken();
      if (token) {
        await fetchCurrentUser();
      }
      setIsLoading(false);
    };

    initAuth();

    const handleExpired = () => {
      setUser(null);
      setAuthToken(null);
    };

    window.addEventListener('auth:expired', handleExpired);
    return () => window.removeEventListener('auth:expired', handleExpired);
  }, []);

  const login = async (loginData: { login: string; password: string }): Promise<User> => {
    const res = await api.post<{ access_token: string; user: User }>('/auth/login', loginData);
    setAuthToken(res.access_token);
    setUser(res.user);
    return res.user;
  };

  const register = async (regData: { email: string; username: string; password: string }): Promise<User> => {
    const res = await api.post<{ access_token: string; user: User }>('/auth/register', regData);
    setAuthToken(res.access_token);
    setUser(res.user);
    return res.user;
  };

  const logout = async (): Promise<void> => {
    try {
      await api.post('/auth/logout');
    } catch (err) {
      // Continue client cleanup even if network fails
    }
    setAuthToken(null);
    setUser(null);
  };

  const refreshUser = async (): Promise<User | null> => {
    return await fetchCurrentUser();
  };

  const setWalletInitialized = () => {
    if (user) {
      setUser({ ...user, has_wallet: true });
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
        setWalletInitialized,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
