import { useAuth, TIER_LABELS } from '../contexts/AuthContext';

export function WalletConnect() {
  const {
    wallet, subscription, connecting, hasProvider,
    connect, disconnect, eveCharacter, eveLogin, eveLogout,
  } = useAuth();

  if (!hasProvider && !eveCharacter) {
    return (
      <div className="flex items-center gap-2 text-xs text-[var(--eve-dim)]">
        <span className="w-2 h-2 rounded-full bg-[var(--eve-red)]" />
        No wallet
      </div>
    );
  }

  if (!wallet && !eveCharacter) {
    return (
      <div className="flex items-center gap-2">
        {hasProvider && (
          <button
            onClick={connect}
            disabled={connecting}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-bold
                       border border-[var(--eve-green)] text-[var(--eve-green)]
                       rounded hover:bg-[var(--eve-green)] hover:text-[var(--eve-bg)]
                       transition-colors disabled:opacity-50"
          >
            <span className="w-2 h-2 rounded-full bg-[var(--eve-red)]" />
            {connecting ? 'Connecting...' : 'Wallet'}
          </button>
        )}
        <button
          onClick={eveLogin}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-bold
                     border border-[var(--eve-blue,#4488ff)] text-[var(--eve-blue,#4488ff)]
                     rounded hover:bg-[var(--eve-blue,#4488ff)] hover:text-[var(--eve-bg)]
                     transition-colors"
        >
          EVE SSO
        </button>
      </div>
    );
  }

  const tier = TIER_LABELS[subscription?.tier ?? 0] || TIER_LABELS[0];
  const shortAddr = wallet ? `${wallet.slice(0, 6)}...${wallet.slice(-4)}` : '';

  return (
    <div className="flex items-center gap-3">
      {/* EVE Character */}
      {eveCharacter && (
        <button
          onClick={eveLogout}
          className="flex items-center gap-1.5 text-xs text-[var(--eve-blue,#4488ff)]
                     hover:text-[var(--eve-text)] transition-colors"
          title={`EVE: ${eveCharacter.character_name} — Click to logout`}
        >
          <span className="w-2 h-2 rounded-full bg-[var(--eve-blue,#4488ff)]" />
          {eveCharacter.character_name}
        </button>
      )}

      {/* Tier badge */}
      {subscription && (
        <span
          className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border"
          style={{ color: tier.color, borderColor: tier.color }}
        >
          {tier.name}
        </span>
      )}

      {/* Wallet address */}
      {wallet && (
        <button
          onClick={disconnect}
          className="flex items-center gap-2 text-xs text-[var(--eve-text)]
                     hover:text-[var(--eve-green)] transition-colors"
          title="Click to disconnect wallet"
        >
          <span className="w-2 h-2 rounded-full bg-[var(--eve-green)]" />
          {shortAddr}
        </button>
      )}

      {/* EVE login button if wallet connected but no EVE char */}
      {wallet && !eveCharacter && (
        <button
          onClick={eveLogin}
          className="text-[10px] text-[var(--eve-dim)] hover:text-[var(--eve-blue,#4488ff)]
                     transition-colors"
        >
          + EVE
        </button>
      )}
    </div>
  );
}
