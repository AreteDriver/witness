import { useEffect, useState } from 'react';
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

const TIER_LABELS: Record<number, { name: string; color: string }> = {
  0: { name: 'Free', color: 'var(--eve-dim)' },
  1: { name: 'Scout', color: 'var(--eve-blue)' },
  2: { name: 'Oracle', color: 'var(--eve-green)' },
  3: { name: 'Spymaster', color: 'var(--eve-orange)' },
};

export function WalletConnect() {
  const [wallet, setWallet] = useState<string | null>(null);
  const [sub, setSub] = useState<SubscriptionData | null>(null);
  const [connecting, setConnecting] = useState(false);

  // Check if already connected
  useEffect(() => {
    if (!window.ethereum) return;
    window.ethereum
      .request({ method: 'eth_accounts' })
      .then((accounts) => {
        const accs = accounts as string[];
        if (accs.length > 0) {
          setWallet(accs[0]);
        }
      })
      .catch(() => {});
  }, []);

  // Load subscription when wallet changes
  useEffect(() => {
    if (!wallet) {
      setSub(null);
      return;
    }
    api.subscription(wallet).then(setSub).catch(() => setSub(null));
  }, [wallet]);

  // Listen for account changes
  useEffect(() => {
    if (!window.ethereum) return;
    const handler = (...args: unknown[]) => {
      const accounts = args[0] as string[];
      setWallet(accounts.length > 0 ? accounts[0] : null);
    };
    window.ethereum.on('accountsChanged', handler);
    return () => window.ethereum?.removeListener('accountsChanged', handler);
  }, []);

  const connect = async () => {
    if (!window.ethereum) return;
    setConnecting(true);
    try {
      const accounts = (await window.ethereum.request({
        method: 'eth_requestAccounts',
      })) as string[];
      if (accounts.length > 0) {
        setWallet(accounts[0]);
      }
    } catch {
      // User rejected
    }
    setConnecting(false);
  };

  const disconnect = () => {
    setWallet(null);
    setSub(null);
  };

  // No wallet provider
  if (!window.ethereum) {
    return (
      <div className="flex items-center gap-2 text-xs text-[var(--eve-dim)]">
        <span className="w-2 h-2 rounded-full bg-[var(--eve-red)]" />
        No wallet
      </div>
    );
  }

  // Not connected
  if (!wallet) {
    return (
      <button
        onClick={connect}
        disabled={connecting}
        className="flex items-center gap-2 px-3 py-1.5 text-xs font-bold
                   border border-[var(--eve-green)] text-[var(--eve-green)]
                   rounded hover:bg-[var(--eve-green)] hover:text-[var(--eve-bg)]
                   transition-colors disabled:opacity-50"
      >
        <span className="w-2 h-2 rounded-full bg-[var(--eve-red)]" />
        {connecting ? 'Connecting...' : 'Connect Wallet'}
      </button>
    );
  }

  // Connected
  const tier = TIER_LABELS[sub?.tier ?? 0] || TIER_LABELS[0];
  const shortAddr = `${wallet.slice(0, 6)}...${wallet.slice(-4)}`;

  return (
    <div className="flex items-center gap-3">
      {/* Subscription badge */}
      {sub && (
        <span
          className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border"
          style={{ color: tier.color, borderColor: tier.color }}
        >
          {tier.name}
        </span>
      )}

      {/* Wallet address */}
      <button
        onClick={disconnect}
        className="flex items-center gap-2 text-xs text-[var(--eve-text)]
                   hover:text-[var(--eve-green)] transition-colors"
        title="Click to disconnect"
      >
        <span className="w-2 h-2 rounded-full bg-[var(--eve-green)]" />
        {shortAddr}
      </button>
    </div>
  );
}
