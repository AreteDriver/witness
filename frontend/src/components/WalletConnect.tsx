import { useAuth, TIER_LABELS } from '../contexts/AuthContext';

export function WalletConnect() {
  const { wallet, subscription, connecting, hasProvider, connect, disconnect } = useAuth();

  if (!hasProvider) {
    return (
      <div className="flex items-center gap-2 text-xs text-[var(--eve-dim)]">
        <span className="w-2 h-2 rounded-full bg-[var(--eve-red)]" />
        No wallet
      </div>
    );
  }

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

  const tier = TIER_LABELS[subscription?.tier ?? 0] || TIER_LABELS[0];
  const shortAddr = `${wallet.slice(0, 6)}...${wallet.slice(-4)}`;

  return (
    <div className="flex items-center gap-3">
      {subscription && (
        <span
          className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border"
          style={{ color: tier.color, borderColor: tier.color }}
        >
          {tier.name}
        </span>
      )}
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
