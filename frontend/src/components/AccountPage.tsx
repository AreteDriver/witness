import { useEffect, useState } from 'react';
import { useAuth, TIER_LABELS } from '../contexts/AuthContext';
import { api } from '../api';
import type { WatchData, AlertData } from '../api';

const TIER_FEATURES: Record<number, string[]> = {
  0: ['Entity search', 'Story feed', 'Leaderboards', 'Kill streaks'],
  1: ['Behavioral fingerprints', 'Reputation scores', 'Fingerprint compare', 'Hotzones'],
  2: ['AI narratives', 'Oracle watches', 'Battle reports', 'Corp intel'],
  3: ['Kill graph network', 'Alt detection', 'Full API access', 'Priority support'],
};

function formatExpiry(ts: number): string {
  if (!ts) return 'N/A';
  const d = new Date(ts * 1000);
  const now = Date.now();
  const diff = ts * 1000 - now;
  if (diff <= 0) return 'Expired';
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  return `${d.toLocaleDateString()} (${days}d ${hours}h remaining)`;
}

function WatchTypeLabel({ type }: { type: string }) {
  const labels: Record<string, string> = {
    entity_movement: 'Movement',
    gate_traffic_spike: 'Traffic Spike',
    killmail_proximity: 'Kill Alert',
    hostile_sighting: 'Hostile',
  };
  return <span>{labels[type] || type}</span>;
}

export function AccountPage() {
  const {
    wallet, subscription, hasProvider, connect, disconnect,
    refreshSubscription, eveCharacter, eveLogin, eveLogout,
  } = useAuth();
  const [watches, setWatches] = useState<WatchData[]>([]);
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [loadingWatches, setLoadingWatches] = useState(false);

  useEffect(() => {
    if (!wallet) return;
    setLoadingWatches(true);
    Promise.all([
      api.watches(wallet).then((d) => setWatches(d.watches)).catch(() => setWatches([])),
      api.alerts(wallet).then((d) => setAlerts(d.alerts)).catch(() => setAlerts([])),
    ]).finally(() => setLoadingWatches(false));
  }, [wallet]);

  const dismissAlert = async (alertId: number) => {
    await api.markAlertRead(alertId);
    setAlerts((prev) => prev.filter((a) => a.id !== alertId));
  };

  const removeWatch = async (targetId: string) => {
    if (!wallet) return;
    await api.deleteWatch(targetId, wallet);
    setWatches((prev) => prev.filter((w) => w.target_id !== targetId));
  };

  // Not connected state
  if (!wallet) {
    return (
      <div className="space-y-8">
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-8 text-center space-y-4">
          <div className="text-4xl text-[var(--eve-green)] pulse-green">///</div>
          <h2 className="text-lg font-bold text-[var(--eve-text)]">Connect Your Wallet</h2>
          <p className="text-sm text-[var(--eve-dim)] max-w-md mx-auto">
            Connect your EVM wallet to access premium intelligence features,
            manage watches, and view your subscription status.
          </p>
          <div className="flex gap-3 justify-center">
            {hasProvider && (
              <button
                onClick={connect}
                className="px-6 py-2 text-sm font-bold border border-[var(--eve-green)]
                           text-[var(--eve-green)] rounded hover:bg-[var(--eve-green)]
                           hover:text-[var(--eve-bg)] transition-colors"
              >
                Connect Wallet
              </button>
            )}
            <button
              onClick={eveLogin}
              className="px-6 py-2 text-sm font-bold border border-[var(--eve-blue,#4488ff)]
                         text-[var(--eve-blue,#4488ff)] rounded hover:bg-[var(--eve-blue,#4488ff)]
                         hover:text-[var(--eve-bg)] transition-colors"
            >
              Login with EVE SSO
            </button>
          </div>
          {!hasProvider && (
            <p className="text-xs text-[var(--eve-dim)]">
              Or install MetaMask for wallet-based authentication.
            </p>
          )}

          {/* Tier overview */}
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-left">
            {[0, 1, 2, 3].map((tier) => {
              const label = TIER_LABELS[tier];
              return (
                <div
                  key={tier}
                  className="border rounded-lg p-4 space-y-2"
                  style={{ borderColor: label.color }}
                >
                  <div className="text-xs font-bold uppercase" style={{ color: label.color }}>
                    {label.name}
                  </div>
                  <ul className="text-xs text-[var(--eve-dim)] space-y-1">
                    {TIER_FEATURES[tier].map((f) => (
                      <li key={f}>+ {f}</li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // Connected state
  const currentTier = subscription?.tier ?? 0;
  const tierLabel = TIER_LABELS[currentTier] || TIER_LABELS[0];

  return (
    <div className="space-y-6">
      {/* EVE Character Card */}
      {eveCharacter && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-blue,#4488ff)] rounded-lg p-5 space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-bold text-[var(--eve-blue,#4488ff)] uppercase tracking-wider">
              EVE Identity
            </h3>
            <span className="w-2 h-2 rounded-full bg-[var(--eve-blue,#4488ff)]" />
          </div>
          <div className="space-y-3">
            <div>
              <div className="text-[10px] text-[var(--eve-dim)] uppercase">Character</div>
              <div className="text-sm text-[var(--eve-text)] font-bold">{eveCharacter.character_name}</div>
            </div>
            <div>
              <div className="text-[10px] text-[var(--eve-dim)] uppercase">Character ID</div>
              <div className="text-sm text-[var(--eve-text)] font-mono">{eveCharacter.character_id}</div>
            </div>
            {eveCharacter.on_chain && (
              <div>
                <div className="text-[10px] text-[var(--eve-dim)] uppercase">On-Chain Activity</div>
                <div className="flex gap-3 text-xs text-[var(--eve-text)]">
                  <span>{eveCharacter.on_chain.kill_count} kills</span>
                  <span>{eveCharacter.on_chain.death_count} deaths</span>
                  <span>{eveCharacter.on_chain.gate_count} transits</span>
                </div>
              </div>
            )}
            {!eveCharacter.on_chain && (
              <div className="text-xs text-[var(--eve-dim)]">
                No on-chain activity found for this character.
              </div>
            )}
          </div>
          <button
            onClick={eveLogout}
            className="w-full px-3 py-1.5 text-xs font-bold border border-[var(--eve-border)]
                       text-[var(--eve-dim)] rounded hover:border-[var(--eve-red)]
                       hover:text-[var(--eve-red)] transition-colors"
          >
            Logout EVE SSO
          </button>
        </div>
      )}

      {/* EVE Login (if wallet connected but no EVE char) */}
      {!eveCharacter && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-5 space-y-4">
          <h3 className="text-sm font-bold text-[var(--eve-blue,#4488ff)] uppercase tracking-wider">
            EVE Identity
          </h3>
          <p className="text-xs text-[var(--eve-dim)]">
            Link your EVE Online character to verify your identity and cross-reference on-chain data.
          </p>
          <button
            onClick={eveLogin}
            className="w-full px-3 py-1.5 text-xs font-bold border border-[var(--eve-blue,#4488ff)]
                       text-[var(--eve-blue,#4488ff)] rounded hover:bg-[var(--eve-blue,#4488ff)]
                       hover:text-[var(--eve-bg)] transition-colors"
          >
            Login with EVE SSO
          </button>
        </div>
      )}

      {/* Wallet & Subscription */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Wallet Card */}
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-5 space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-bold text-[var(--eve-green)] uppercase tracking-wider">
              Wallet
            </h3>
            <span className="w-2 h-2 rounded-full bg-[var(--eve-green)]" />
          </div>

          <div className="space-y-3">
            <div>
              <div className="text-[10px] text-[var(--eve-dim)] uppercase">Address</div>
              <div className="text-sm text-[var(--eve-text)] font-mono break-all">{wallet}</div>
            </div>
            <div>
              <div className="text-[10px] text-[var(--eve-dim)] uppercase">Status</div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[var(--eve-green)]" />
                <span className="text-sm text-[var(--eve-text)]">Connected</span>
              </div>
            </div>
          </div>

          <button
            onClick={disconnect}
            className="w-full px-3 py-1.5 text-xs font-bold border border-[var(--eve-red)]
                       text-[var(--eve-red)] rounded hover:bg-[var(--eve-red)]
                       hover:text-[var(--eve-bg)] transition-colors"
          >
            Disconnect
          </button>
        </div>

        {/* Subscription Card */}
        <div
          className="bg-[var(--eve-surface)] border rounded-lg p-5 space-y-4"
          style={{ borderColor: tierLabel.color }}
        >
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-bold uppercase tracking-wider" style={{ color: tierLabel.color }}>
              Subscription
            </h3>
            <span
              className="text-[10px] font-bold uppercase px-2 py-0.5 rounded border"
              style={{ color: tierLabel.color, borderColor: tierLabel.color }}
            >
              {tierLabel.name}
            </span>
          </div>

          <div className="space-y-3">
            <div>
              <div className="text-[10px] text-[var(--eve-dim)] uppercase">Tier</div>
              <div className="text-sm text-[var(--eve-text)]">
                {tierLabel.name} (Level {currentTier})
              </div>
            </div>
            <div>
              <div className="text-[10px] text-[var(--eve-dim)] uppercase">Expires</div>
              <div className="text-sm text-[var(--eve-text)]">
                {subscription?.active ? formatExpiry(subscription.expires_at) : 'No active subscription'}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-[var(--eve-dim)] uppercase">Features</div>
              <ul className="text-xs text-[var(--eve-dim)] space-y-0.5 mt-1">
                {[0, 1, 2, 3].filter((t) => t <= currentTier).flatMap((t) =>
                  TIER_FEATURES[t].map((f) => (
                    <li key={f} className="text-[var(--eve-text)]">+ {f}</li>
                  ))
                )}
              </ul>
            </div>
          </div>

          {currentTier < 3 && (
            <div className="pt-2 border-t border-[var(--eve-border)]">
              <div className="text-[10px] text-[var(--eve-dim)] uppercase mb-2">Upgrade</div>
              <p className="text-xs text-[var(--eve-dim)]">
                Transfer items to a Watcher Assembly to upgrade your tier.
                Visit any Watcher-equipped Smart Assembly in-game.
              </p>
            </div>
          )}

          <button
            onClick={refreshSubscription}
            className="w-full px-3 py-1.5 text-xs font-bold border border-[var(--eve-border)]
                       text-[var(--eve-dim)] rounded hover:border-[var(--eve-green)]
                       hover:text-[var(--eve-green)] transition-colors"
          >
            Refresh Status
          </button>
        </div>
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-5 space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-bold text-[var(--eve-orange,#FF6600)] uppercase tracking-wider">
              Alerts
            </h3>
            <span className="text-xs text-[var(--eve-dim)]">
              {alerts.filter((a) => !a.read).length} unread
            </span>
          </div>
          <div className="space-y-2">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`flex items-start justify-between px-3 py-2 rounded border transition-colors ${
                  alert.severity === 'critical'
                    ? 'border-[var(--eve-red)]'
                    : 'border-[var(--eve-border)]'
                }`}
              >
                <div className="space-y-0.5">
                  <div className="text-xs font-bold text-[var(--eve-text)]">{alert.title}</div>
                  <div className="text-[10px] text-[var(--eve-dim)]">{alert.body}</div>
                  <div className="text-[10px] text-[var(--eve-dim)]">
                    {new Date(alert.created_at * 1000).toLocaleString()}
                  </div>
                </div>
                <button
                  onClick={() => dismissAlert(alert.id)}
                  className="text-[10px] text-[var(--eve-dim)] hover:text-[var(--eve-text)]
                             transition-colors px-2 py-1 shrink-0"
                >
                  Dismiss
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Active Watches */}
      <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-5 space-y-4">
        <div className="flex justify-between items-center">
          <h3 className="text-sm font-bold text-[var(--eve-green)] uppercase tracking-wider">
            Active Watches
          </h3>
          <span className="text-xs text-[var(--eve-dim)]">{watches.length} active</span>
        </div>

        {loadingWatches && (
          <div className="text-xs text-[var(--eve-dim)]">Loading watches...</div>
        )}

        {!loadingWatches && watches.length === 0 && (
          <div className="text-center py-6 space-y-2">
            <div className="text-xs text-[var(--eve-dim)]">No active watches</div>
            <p className="text-xs text-[var(--eve-dim)]">
              {currentTier >= 2
                ? 'Create watches from entity profiles to track movements and events.'
                : 'Upgrade to Oracle tier to create watches.'}
            </p>
          </div>
        )}

        {watches.length > 0 && (
          <div className="space-y-2">
            {watches.map((w) => (
              <div
                key={w.id}
                className="flex items-center justify-between px-3 py-2 rounded
                           border border-[var(--eve-border)] hover:border-[var(--eve-green)]
                           transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-[var(--eve-green)]" />
                  <div>
                    <div className="text-xs text-[var(--eve-text)] font-mono">
                      {w.target_id}
                    </div>
                    <div className="text-[10px] text-[var(--eve-dim)]">
                      <WatchTypeLabel type={w.watch_type} />
                      {w.webhook_url && ' + webhook'}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => removeWatch(w.target_id)}
                  className="text-[10px] text-[var(--eve-red)] hover:text-[var(--eve-text)]
                             transition-colors px-2 py-1"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tier Comparison */}
      <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-5 space-y-4">
        <h3 className="text-sm font-bold text-[var(--eve-green)] uppercase tracking-wider">
          Tier Comparison
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[0, 1, 2, 3].map((tier) => {
            const label = TIER_LABELS[tier];
            const isActive = tier <= currentTier;
            return (
              <div
                key={tier}
                className={`border rounded-lg p-3 space-y-2 transition-opacity ${
                  isActive ? 'opacity-100' : 'opacity-40'
                }`}
                style={{ borderColor: isActive ? label.color : 'var(--eve-border)' }}
              >
                <div
                  className="text-[10px] font-bold uppercase"
                  style={{ color: label.color }}
                >
                  {label.name}
                  {tier === currentTier && (
                    <span className="ml-1 text-[var(--eve-text)]">(current)</span>
                  )}
                </div>
                <ul className="text-[10px] text-[var(--eve-dim)] space-y-0.5">
                  {TIER_FEATURES[tier].map((f) => (
                    <li key={f}>{isActive ? '+' : '-'} {f}</li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
