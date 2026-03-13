import { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import type { ReactNode } from 'react';
import { useCurrentAccount, useDisconnectWallet, useSignPersonalMessage } from '@mysten/dapp-kit';
import { api } from '../api';
import type { SubscriptionData } from '../api';

export const TIER_LABELS: Record<number, { name: string; color: string }> = {
  0: { name: 'Free', color: 'var(--eve-dim)' },
  1: { name: 'Scout', color: 'var(--eve-blue)' },
  2: { name: 'Oracle', color: 'var(--eve-green)' },
  3: { name: 'Spymaster', color: 'var(--eve-orange)' },
};

const SESSION_KEY = 'watchtower_session';
const WALLET_KEY = 'watchtower_wallet';

interface AuthState {
  wallet: string | null;
  subscription: SubscriptionData | null;
  connecting: boolean;
  isAdmin: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
  refreshSubscription: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [wallet, setWallet] = useState<string | null>(() => localStorage.getItem(WALLET_KEY));
  const [subscription, setSubscription] = useState<SubscriptionData | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const sessionVerified = useRef(false);

  const currentAccount = useCurrentAccount();
  const { mutate: disconnectWallet } = useDisconnectWallet();
  const { mutateAsync: signPersonalMessage } = useSignPersonalMessage();

  const fetchSubscription = useCallback(async (addr: string) => {
    try {
      const sub = await api.subscription(addr);
      setSubscription(sub);
    } catch {
      setSubscription(null);
    }
  }, []);

  // Restore session on mount — runs once before dApp kit auto-connects
  useEffect(() => {
    const savedSession = localStorage.getItem(SESSION_KEY);
    const savedWallet = localStorage.getItem(WALLET_KEY);
    if (savedSession && savedWallet) {
      api.walletMe()
        .then((me) => {
          setWallet(me.wallet_address);
          setIsAdmin(me.is_admin);
          sessionVerified.current = true;
        })
        .catch(() => {
          // Session expired — mark unverified but DON'T clear from localStorage yet.
          // dApp kit auto-connect useEffect reads localStorage synchronously;
          // clearing here causes a race where it sees no session and re-triggers signing.
          sessionVerified.current = false;
        });
    }
  }, []);

  // When dApp kit wallet connects/changes
  useEffect(() => {
    if (!currentAccount?.address) return;

    const suiAddress = currentAccount.address;
    const savedWallet = localStorage.getItem(WALLET_KEY);
    const savedSession = localStorage.getItem(SESSION_KEY);

    // Already have a saved session for this wallet — restore without re-signing
    if (savedWallet === suiAddress && savedSession) {
      setWallet(suiAddress);
      // Verify session in background — if expired, lazy re-auth on next API call
      api.walletMe()
        .then((me) => {
          setIsAdmin(me.is_admin);
          sessionVerified.current = true;
        })
        .catch(() => {
          // Session expired — clear it but DON'T re-auth automatically.
          // User will see read-only state; they can disconnect + reconnect to re-sign.
          localStorage.removeItem(SESSION_KEY);
          sessionVerified.current = false;
        });
      return;
    }

    // New wallet (not previously connected) — full challenge-response auth.
    // If savedWallet matches but session expired, stay read-only rather than
    // forcing a signature popup on every page refresh.
    if (!savedSession && savedWallet !== suiAddress) {
      authenticateWallet(suiAddress);
    }
  }, [currentAccount?.address]);

  const authenticateWallet = async (address: string) => {
    setConnecting(true);
    try {
      // Step 1: Get challenge nonce from backend
      const challenge = await api.walletChallenge();

      // Step 2: Sign the challenge message with dApp kit
      const messageBytes = new TextEncoder().encode(challenge.message);
      const { signature } = await signPersonalMessage({ message: messageBytes });

      // Step 3: Submit signature to backend for verification
      const result = await api.walletConnect(address, signature, challenge.message);
      localStorage.setItem(SESSION_KEY, result.session_token);
      localStorage.setItem(WALLET_KEY, address);
      setWallet(address);
      setIsAdmin(result.is_admin);
      sessionVerified.current = true;
    } catch (err) {
      console.error('Wallet auth failed:', err);
      // Still show wallet as connected for read-only access
      localStorage.setItem(WALLET_KEY, address);
      setWallet(address);
    }
    setConnecting(false);
  };

  // Fetch subscription when wallet changes
  useEffect(() => {
    if (!wallet) {
      setSubscription(null);
      return;
    }
    fetchSubscription(wallet);
  }, [wallet, fetchSubscription]);

  const connect = useCallback(async () => {
    // Connection handled by dapp-kit ConnectButton → useEffect above
  }, []);

  const disconnect = useCallback(() => {
    api.walletDisconnect().catch(() => {});
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(WALLET_KEY);
    setWallet(null);
    setSubscription(null);
    setIsAdmin(false);
    sessionVerified.current = false;
    disconnectWallet();
  }, [disconnectWallet]);

  const refreshSubscription = useCallback(async () => {
    if (wallet) await fetchSubscription(wallet);
  }, [wallet, fetchSubscription]);

  return (
    <AuthContext.Provider
      value={{
        wallet,
        subscription,
        connecting,
        isAdmin,
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
