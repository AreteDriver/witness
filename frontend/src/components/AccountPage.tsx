import { useEffect, useState } from 'react';
import { ConnectButton } from '@mysten/dapp-kit';
import { useAuth, TIER_LABELS } from '../contexts/AuthContext';
import { api } from '../api';
import type { WatchData, AlertData, NexusSubscription, NexusDelivery } from '../api';

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
    wallet, subscription, isAdmin, disconnect, refreshSubscription,
  } = useAuth();
  const [watches, setWatches] = useState<WatchData[]>([]);
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [loadingWatches, setLoadingWatches] = useState(false);

  // NEXUS state
  const NEXUS_KEY = 'watchtower_nexus_key';
  const [nexusKey, setNexusKey] = useState<string>(localStorage.getItem(NEXUS_KEY) || '');
  const [nexusSubs, setNexusSubs] = useState<NexusSubscription[]>([]);
  const [nexusDeliveries, setNexusDeliveries] = useState<NexusDelivery[]>([]);
  const [nexusLoading, setNexusLoading] = useState(false);
  const [nexusSecret, setNexusSecret] = useState<string>('');
  const [showNexusForm, setShowNexusForm] = useState(false);
  const [nexusName, setNexusName] = useState('');
  const [nexusEndpoint, setNexusEndpoint] = useState('');
  const [nexusFilterTypes, setNexusFilterTypes] = useState('');
  const [nexusFilterEntities, setNexusFilterEntities] = useState('');
  const [nexusFilterSystems, setNexusFilterSystems] = useState('');
  const [nexusError, setNexusError] = useState('');
  const [showDeliveries, setShowDeliveries] = useState(false);

  useEffect(() => {
    if (!wallet) return;
    setLoadingWatches(true);
    Promise.all([
      api.watches(wallet).then((d) => setWatches(d.watches)).catch(() => setWatches([])),
      api.alerts(wallet).then((d) => setAlerts(d.alerts)).catch(() => setAlerts([])),
    ]).finally(() => setLoadingWatches(false));
  }, [wallet]);

  // Load NEXUS subscriptions when key is set
  useEffect(() => {
    if (!nexusKey) return;
    setNexusLoading(true);
    Promise.all([
      api.nexusSubscriptions(nexusKey).then((d) => setNexusSubs(d.subscriptions)).catch(() => setNexusSubs([])),
      api.nexusDeliveries(nexusKey, 20).then((d) => setNexusDeliveries(d.deliveries)).catch(() => setNexusDeliveries([])),
    ]).finally(() => setNexusLoading(false));
  }, [nexusKey]);

  const createNexusSub = async () => {
    setNexusError('');
    if (!nexusName.trim() || !nexusEndpoint.trim()) {
      setNexusError('Name and endpoint URL are required.');
      return;
    }
    try {
      const filters: Record<string, unknown> = {};
      if (nexusFilterTypes.trim()) {
        filters.event_types = nexusFilterTypes.split(',').map((s) => s.trim()).filter(Boolean);
      }
      if (nexusFilterEntities.trim()) {
        filters.entity_ids = nexusFilterEntities.split(',').map((s) => s.trim()).filter(Boolean);
      }
      if (nexusFilterSystems.trim()) {
        filters.system_ids = nexusFilterSystems.split(',').map((s) => s.trim()).filter(Boolean);
      }
      const resp = await api.nexusSubscribe(nexusName.trim(), nexusEndpoint.trim(), filters);
      setNexusKey(resp.api_key);
      localStorage.setItem(NEXUS_KEY, resp.api_key);
      setNexusSecret(resp.secret);
      setShowNexusForm(false);
      setNexusName('');
      setNexusEndpoint('');
      setNexusFilterTypes('');
      setNexusFilterEntities('');
      setNexusFilterSystems('');
    } catch (e) {
      setNexusError(e instanceof Error ? e.message : 'Subscription failed');
    }
  };

  const deleteNexusSub = async (subId: number) => {
    if (!nexusKey) return;
    await api.nexusDeleteSubscription(subId, nexusKey);
    setNexusSubs((prev) => prev.filter((s) => s.id !== subId));
  };

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
            Connect your Sui wallet to access premium intelligence features,
            manage watches, and view your subscription status.
          </p>
          <div className="flex gap-3 justify-center">
            <ConnectButton
              connectText="Connect Sui Wallet"
              className="px-6 py-2 text-sm font-bold border border-[var(--eve-green)]
                         text-[var(--eve-green)] rounded hover:bg-[var(--eve-green)]
                         hover:text-[var(--eve-bg)] transition-colors"
            />
          </div>

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
      {/* Wallet & Subscription */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Wallet Card */}
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-5 space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-bold text-[var(--eve-green)] uppercase tracking-wider">
              Wallet
            </h3>
            <div className="flex items-center gap-2">
              {isAdmin && (
                <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border
                                 text-[var(--eve-red)] border-[var(--eve-red)]">
                  Admin
                </span>
              )}
              <span className="w-2 h-2 rounded-full bg-[var(--eve-green)]" />
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <div className="text-[10px] text-[var(--eve-dim)] uppercase">Address</div>
              <div className="text-sm text-[var(--eve-text)] font-mono break-all">{wallet}</div>
            </div>
            <div>
              <div className="text-[10px] text-[var(--eve-dim)] uppercase">Network</div>
              <div className="text-sm text-[var(--eve-text)]">Sui Mainnet</div>
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

      {/* NEXUS Subscriptions */}
      <div className="bg-[var(--eve-surface)] border border-[var(--eve-blue,#3B82F6)] rounded-lg p-5 space-y-4">
        <div className="flex justify-between items-center">
          <h3 className="text-sm font-bold text-[var(--eve-blue,#3B82F6)] uppercase tracking-wider">
            NEXUS Webhooks
          </h3>
          <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border
                           text-[var(--eve-blue,#3B82F6)] border-[var(--eve-blue,#3B82F6)]">
            Builder API
          </span>
        </div>

        <p className="text-xs text-[var(--eve-dim)]">
          Subscribe to enriched event webhooks. WatchTower POSTs HMAC-signed payloads
          with resolved names, system data, and intelligence when matching events are indexed.
        </p>

        {/* Secret reveal (one-time after creation) */}
        {nexusSecret && (
          <div className="border border-[var(--eve-orange,#FF6600)] rounded p-3 space-y-1">
            <div className="text-[10px] font-bold text-[var(--eve-orange,#FF6600)] uppercase">
              Save Your HMAC Secret — shown only once
            </div>
            <div className="text-xs text-[var(--eve-text)] font-mono break-all bg-[var(--eve-bg)] p-2 rounded">
              {nexusSecret}
            </div>
            <div className="text-[10px] text-[var(--eve-dim)]">
              Use this to verify <code className="text-[var(--eve-text)]">X-Nexus-Signature</code> on incoming webhooks.
            </div>
            <button
              onClick={() => setNexusSecret('')}
              className="text-[10px] text-[var(--eve-dim)] hover:text-[var(--eve-text)] transition-colors"
            >
              I've saved it — dismiss
            </button>
          </div>
        )}

        {/* API Key display / entry */}
        {nexusKey ? (
          <div className="space-y-1">
            <div className="text-[10px] text-[var(--eve-dim)] uppercase">API Key</div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--eve-text)] font-mono">
                {nexusKey.slice(0, 12)}...{nexusKey.slice(-4)}
              </span>
              <button
                onClick={() => { setNexusKey(''); localStorage.removeItem(NEXUS_KEY); setNexusSubs([]); }}
                className="text-[10px] text-[var(--eve-dim)] hover:text-[var(--eve-red)] transition-colors"
              >
                Clear
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-[10px] text-[var(--eve-dim)] uppercase">
              Enter existing API key or create a new subscription
            </div>
            <input
              type="text"
              placeholder="nxs_..."
              className="w-full px-3 py-1.5 text-xs font-mono bg-[var(--eve-bg)] border border-[var(--eve-border)]
                         rounded text-[var(--eve-text)] placeholder-[var(--eve-dim)]
                         focus:border-[var(--eve-blue,#3B82F6)] focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const val = (e.target as HTMLInputElement).value.trim();
                  if (val) { setNexusKey(val); localStorage.setItem(NEXUS_KEY, val); }
                }
              }}
            />
          </div>
        )}

        {/* Create new subscription */}
        {!showNexusForm ? (
          <button
            onClick={() => setShowNexusForm(true)}
            className="w-full px-3 py-1.5 text-xs font-bold border border-[var(--eve-blue,#3B82F6)]
                       text-[var(--eve-blue,#3B82F6)] rounded hover:bg-[var(--eve-blue,#3B82F6)]
                       hover:text-[var(--eve-bg)] transition-colors"
          >
            + New Subscription
          </button>
        ) : (
          <div className="border border-[var(--eve-border)] rounded p-3 space-y-3">
            <div className="text-[10px] font-bold text-[var(--eve-blue,#3B82F6)] uppercase">
              New NEXUS Subscription
            </div>
            {nexusError && (
              <div className="text-xs text-[var(--eve-red)]">{nexusError}</div>
            )}
            <input
              type="text"
              placeholder="Subscription name (e.g. My Kill Bot)"
              value={nexusName}
              onChange={(e) => setNexusName(e.target.value)}
              className="w-full px-3 py-1.5 text-xs bg-[var(--eve-bg)] border border-[var(--eve-border)]
                         rounded text-[var(--eve-text)] placeholder-[var(--eve-dim)]
                         focus:border-[var(--eve-blue,#3B82F6)] focus:outline-none"
            />
            <input
              type="text"
              placeholder="Webhook URL (https://...)"
              value={nexusEndpoint}
              onChange={(e) => setNexusEndpoint(e.target.value)}
              className="w-full px-3 py-1.5 text-xs font-mono bg-[var(--eve-bg)] border border-[var(--eve-border)]
                         rounded text-[var(--eve-text)] placeholder-[var(--eve-dim)]
                         focus:border-[var(--eve-blue,#3B82F6)] focus:outline-none"
            />
            <div className="text-[10px] text-[var(--eve-dim)] uppercase mt-2">
              Filters (optional — leave blank for all events)
            </div>
            <input
              type="text"
              placeholder="Event types (comma-separated: killmail, gate_transit)"
              value={nexusFilterTypes}
              onChange={(e) => setNexusFilterTypes(e.target.value)}
              className="w-full px-3 py-1.5 text-xs bg-[var(--eve-bg)] border border-[var(--eve-border)]
                         rounded text-[var(--eve-text)] placeholder-[var(--eve-dim)]
                         focus:border-[var(--eve-blue,#3B82F6)] focus:outline-none"
            />
            <input
              type="text"
              placeholder="Entity IDs (comma-separated)"
              value={nexusFilterEntities}
              onChange={(e) => setNexusFilterEntities(e.target.value)}
              className="w-full px-3 py-1.5 text-xs font-mono bg-[var(--eve-bg)] border border-[var(--eve-border)]
                         rounded text-[var(--eve-text)] placeholder-[var(--eve-dim)]
                         focus:border-[var(--eve-blue,#3B82F6)] focus:outline-none"
            />
            <input
              type="text"
              placeholder="System IDs (comma-separated)"
              value={nexusFilterSystems}
              onChange={(e) => setNexusFilterSystems(e.target.value)}
              className="w-full px-3 py-1.5 text-xs font-mono bg-[var(--eve-bg)] border border-[var(--eve-border)]
                         rounded text-[var(--eve-text)] placeholder-[var(--eve-dim)]
                         focus:border-[var(--eve-blue,#3B82F6)] focus:outline-none"
            />
            <div className="flex gap-2">
              <button
                onClick={createNexusSub}
                className="flex-1 px-3 py-1.5 text-xs font-bold bg-[var(--eve-blue,#3B82F6)]
                           text-white rounded hover:opacity-90 transition-opacity"
              >
                Subscribe
              </button>
              <button
                onClick={() => { setShowNexusForm(false); setNexusError(''); }}
                className="px-3 py-1.5 text-xs font-bold border border-[var(--eve-border)]
                           text-[var(--eve-dim)] rounded hover:text-[var(--eve-text)] transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Active subscriptions */}
        {nexusLoading && (
          <div className="text-xs text-[var(--eve-dim)]">Loading subscriptions...</div>
        )}

        {!nexusLoading && nexusSubs.length > 0 && (
          <div className="space-y-2">
            <div className="text-[10px] text-[var(--eve-dim)] uppercase">
              Active Subscriptions ({nexusSubs.length})
            </div>
            {nexusSubs.map((sub) => (
              <div
                key={sub.id}
                className={`flex items-start justify-between px-3 py-2 rounded border transition-colors ${
                  sub.active ? 'border-[var(--eve-blue,#3B82F6)]' : 'border-[var(--eve-red)] opacity-60'
                }`}
              >
                <div className="space-y-0.5 min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${sub.active ? 'bg-[var(--eve-green)]' : 'bg-[var(--eve-red)]'}`} />
                    <span className="text-xs font-bold text-[var(--eve-text)]">{sub.name}</span>
                    {!sub.active && (
                      <span className="text-[10px] text-[var(--eve-red)]">(disabled)</span>
                    )}
                  </div>
                  <div className="text-[10px] text-[var(--eve-dim)] font-mono truncate">
                    {sub.endpoint_url}
                  </div>
                  <div className="text-[10px] text-[var(--eve-dim)]">
                    {sub.delivery_count} deliveries
                    {sub.last_delivered_at && (
                      <> &middot; last: {new Date(sub.last_delivered_at * 1000).toLocaleString()}</>
                    )}
                  </div>
                  {sub.filters && Object.keys(sub.filters).length > 0 && (
                    <div className="text-[10px] text-[var(--eve-dim)]">
                      Filters: {Object.entries(sub.filters).map(([k, v]) => (
                        <span key={k} className="inline-block mr-2">
                          <span className="text-[var(--eve-text)]">{k}</span>={Array.isArray(v) ? (v as string[]).join(',') : String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => deleteNexusSub(sub.id)}
                  className="text-[10px] text-[var(--eve-red)] hover:text-[var(--eve-text)]
                             transition-colors px-2 py-1 shrink-0"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Delivery history toggle */}
        {nexusKey && (
          <div>
            <button
              onClick={() => setShowDeliveries(!showDeliveries)}
              className="text-xs text-[var(--eve-blue,#3B82F6)] hover:text-[var(--eve-text)] transition-colors"
            >
              {showDeliveries ? 'Hide' : 'Show'} Delivery History
            </button>
            {showDeliveries && nexusDeliveries.length > 0 && (
              <div className="mt-2 space-y-1">
                {nexusDeliveries.map((d) => (
                  <div
                    key={d.id}
                    className={`flex items-center justify-between px-2 py-1 rounded text-[10px] ${
                      d.success ? 'text-[var(--eve-green)]' : 'text-[var(--eve-red)]'
                    }`}
                  >
                    <span className="font-mono">{d.event_type}</span>
                    <span>
                      {d.success ? `${d.status_code}` : `FAIL (${d.error || d.status_code})`}
                      {' '}&middot;{' '}
                      {new Date(d.delivered_at * 1000).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {showDeliveries && nexusDeliveries.length === 0 && (
              <div className="mt-2 text-[10px] text-[var(--eve-dim)]">No deliveries yet.</div>
            )}
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
