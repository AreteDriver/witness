import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import { api } from '../api';
import type { SubscriptionData } from '../api';

declare global {
  interface Window {
    ethereum?: {
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
      on: (event: string, handler: (...args: unknown[]) => void) => void;
      removeListener: (event: string, handler: (...args: unknown[]) => void) => void;
    };
  }
}

export const TIER_LABELS: Record<number, { name: string; color: string }> = {
  0: { name: 'Free', color: 'var(--eve-dim)' },
  1: { name: 'Scout', color: 'var(--eve-blue)' },
  2: { name: 'Oracle', color: 'var(--eve-green)' },
  3: { name: 'Spymaster', color: 'var(--eve-orange)' },
};

interface AuthState {
  wallet: string | null;
  subscription: SubscriptionData | null;
  connecting: boolean;
  hasProvider: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
  refreshSubscription: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

const STORAGE_KEY = 'witness_wallet';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [wallet, setWallet] = useState<string | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionData | null>(null);
  const [connecting, setConnecting] = useState(false);
  const hasProvider = typeof window !== 'undefined' && !!window.ethereum;

  const fetchSubscription = useCallback(async (addr: string) => {
    try {
      const sub = await api.subscription(addr);
      setSubscription(sub);
    } catch {
      setSubscription(null);
    }
  }, []);

  const setWalletAndPersist = useCallback((addr: string | null) => {
    setWallet(addr);
    if (addr) {
      localStorage.setItem(STORAGE_KEY, addr);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  // Restore wallet from localStorage + verify it's still connected
  useEffect(() => {
    if (!window.ethereum) return;
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return;

    window.ethereum
      .request({ method: 'eth_accounts' })
      .then((accounts) => {
        const accs = accounts as string[];
        const stillConnected = accs.some(
          (a) => a.toLowerCase() === saved.toLowerCase()
        );
        if (stillConnected) {
          setWallet(saved);
        } else {
          localStorage.removeItem(STORAGE_KEY);
        }
      })
      .catch(() => localStorage.removeItem(STORAGE_KEY));
  }, []);

  // Fetch subscription when wallet changes
  useEffect(() => {
    if (!wallet) {
      setSubscription(null);
      return;
    }
    fetchSubscription(wallet);
  }, [wallet, fetchSubscription]);

  // Listen for account changes from wallet
  useEffect(() => {
    if (!window.ethereum) return;
    const handler = (...args: unknown[]) => {
      const accounts = args[0] as string[];
      if (accounts.length > 0) {
        setWalletAndPersist(accounts[0]);
      } else {
        setWalletAndPersist(null);
      }
    };
    window.ethereum.on('accountsChanged', handler);
    return () => window.ethereum?.removeListener('accountsChanged', handler);
  }, [setWalletAndPersist]);

  const connect = useCallback(async () => {
    if (!window.ethereum) return;
    setConnecting(true);
    try {
      const accounts = (await window.ethereum.request({
        method: 'eth_requestAccounts',
      })) as string[];
      if (accounts.length > 0) {
        setWalletAndPersist(accounts[0]);
      }
    } catch {
      // User rejected
    }
    setConnecting(false);
  }, [setWalletAndPersist]);

  const disconnect = useCallback(() => {
    setWalletAndPersist(null);
    setSubscription(null);
  }, [setWalletAndPersist]);

  const refreshSubscription = useCallback(async () => {
    if (wallet) await fetchSubscription(wallet);
  }, [wallet, fetchSubscription]);

  return (
    <AuthContext.Provider
      value={{
        wallet,
        subscription,
        connecting,
        hasProvider,
        connect,
        disconnect,
        refreshSubscription,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
