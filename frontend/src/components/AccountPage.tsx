import { useEffect, useState } from 'react';
import { useLocation } from 'react-router';
import { ConnectButton, useSignAndExecuteTransaction } from '@mysten/dapp-kit';
import { Transaction } from '@mysten/sui/transactions';
import { useAuth, TIER_LABELS } from '../contexts/AuthContext';
import { api } from '../api';
import type { WatchData, AlertData, NexusSubscription, NexusDelivery, NexusQuota } from '../api';
import { usePricing } from '../hooks/usePricing';

const WATCHTOWER_PACKAGE = '0x3ca7e3af5bf5b072157d02534f5e4013cf11a12b79385c270d97de480e7b7dca';
const SUBSCRIPTION_CONFIG = '0x7bd0e266d3c26665b13c432f70d9b7e5ecc266de993094f8ac8290020283be9d';
const SUBSCRIPTION_REGISTRY = '0x4bb5a6999fadd2039b8cfcb7a1b3de0f07973fe0ec74181b024edaaa6069d160';
const SUI_CLOCK = '0x6';

const TIER_KEYS: Record<number, string> = {
  1: 'scout',
  2: 'oracle',
  3: 'spymaster',
};

const TIER_FEATURES: Record<number, string[]> = {
  0: ['Entity search', 'Story feed', 'Leaderboards', 'Kill streaks'],
  1: ['Behavioral fingerprints', 'Reputation scores', 'Fingerprint compare', 'Hotzones'],
  2: ['AI narratives', 'Oracle watches', 'Battle reports', 'Corp intel', 'NEXUS webhooks (2 subs, 100/day)'],
  3: ['Kill graph network', 'Alt detection', 'Full API access', 'Priority support', 'NEXUS webhooks (10 subs, 1K/day)'],
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
  const { pricing, loading: pricingLoading, error: pricingError, refetch: refetchPricing } = usePricing();
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
  const [nexusExpanded, setNexusExpanded] = useState(false);
  const [nexusName, setNexusName] = useState('');
  const [nexusEndpoint, setNexusEndpoint] = useState('');
  const [nexusFilterTypes, setNexusFilterTypes] = useState('');
  const [nexusFilterEntities, setNexusFilterEntities] = useState('');
  const [nexusFilterSystems, setNexusFilterSystems] = useState('');
  const [nexusError, setNexusError] = useState('');
  const [showDeliveries, setShowDeliveries] = useState(false);
  const [nexusQuota, setNexusQuota] = useState<NexusQuota | null>(null);
  const [subscribing, setSubscribing] = useState<number | null>(null);
  const [txError, setTxError] = useState<string>('');
  const { mutateAsync: signAndExecuteTransaction } = useSignAndExecuteTransaction();
  const location = useLocation();

  const handleSubscribe = async (tier: number) => {
    setSubscribing(tier);
    setTxError('');
    try {
      // Refetch pricing to get fresh rate
      const freshData = await api.getPricing();
      if (freshData.is_stale) {
        setTxError('Price data is outdated. Please refresh prices and try again.');
        return;
      }
      const tierKey = TIER_KEYS[tier];
      if (!tierKey || !freshData.tiers[tierKey]) {
        setTxError('Invalid tier');
        return;
      }
      const price = freshData.tiers[tierKey].sui_mist;

      const tx = new Transaction();
      const [coin] = tx.splitCoins(tx.gas, [price]);
      tx.moveCall({
        target: `${WATCHTOWER_PACKAGE}::subscription::subscribe`,
        arguments: [
          tx.object(SUBSCRIPTION_CONFIG),
          tx.object(SUBSCRIPTION_REGISTRY),
          tx.pure.u8(tier),
          coin,
          tx.object(SUI_CLOCK),
        ],
      });
      await signAndExecuteTransaction({ transaction: tx });
      await refreshSubscription();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Transaction failed';
      setTxError(msg);
    } finally {
      setSubscribing(null);
    }
  };

  // Scroll to #nexus when navigating from NexusCard — auto-expand
  useEffect(() => {
    if (location.hash === '#nexus') {
      setNexusExpanded(true);
      const el = document.getElementById('nexus');
      if (el) {
        setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100);
      }
    }
  }, [location.hash]);

  useEffect(() => {
    if (!wallet) return;
    setLoadingWatches(true);
    Promise.all([
      api.watches(wallet).then((d) => setWatches(d.watches)).catch(() => setWatches([])),
      api.alerts(wallet).then((d) => setAlerts(d.alerts)).catch(() => setAlerts([])),
      api.nexusQuota().then((d) => setNexusQuota(d)).catch(() => setNexusQuota(null)),
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
  const isHackathonMode = currentTier >= 3 && subscription?.active;

  const tierColors: Record<string, string> = {
    scout: 'var(--eve-blue)',
    oracle: 'var(--eve-green)',
    spymaster: 'var(--eve-orange)',
  };

  const SUBSCRIPTION_TIERS = (['scout', 'oracle', 'spymaster'] as const).map((key) => {
    const tp = pricing?.tiers[key];
    return {
      key,
      name: key.charAt(0).toUpperCase() + key.slice(1),
      tier: tp?.tier ?? ({ scout: 1, oracle: 2, spymaster: 3 }[key]),
      suiPrice: tp ? `${tp.sui_per_week} SUI / week` : '...',
      fiatPrice: tp ? `$${tp.usd_per_week.toFixed(2)}/wk` : '...',
      color: tierColors[key],
      features: TIER_FEATURES[{ scout: 1, oracle: 2, spymaster: 3 }[key]],
      popular: key === 'oracle',
    };
  });

  return (
    <div className="space-y-6">
      {/* Hackathon Mode Banner */}
      {isHackathonMode && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-orange)] rounded-lg p-4 text-center space-y-1">
          <div className="text-sm font-bold text-[var(--eve-orange)] uppercase tracking-wider">
            Hackathon Mode Active
          </div>
          <p className="text-xs text-[var(--eve-dim)]">
            All tiers unlocked during hackathon — subscribe now to lock in access post-hackathon
          </p>
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
              <div className="text-sm text-[var(--eve-text)]">Sui Testnet</div>
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
              <div className="flex items-center gap-3">
                <div className="text-sm text-[var(--eve-text)]">
                  {subscription?.active ? formatExpiry(subscription.expires_at) : 'No active subscription'}
                </div>
                {subscription?.active && currentTier >= 1 && (
                  <button
                    className="px-3 py-1 text-[10px] font-bold rounded transition-opacity
                               hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{ backgroundColor: tierLabel.color, color: 'var(--eve-bg)' }}
                    disabled={subscribing !== null || pricingLoading || !pricing || pricing.is_stale}
                    onClick={() => handleSubscribe(currentTier)}
                  >
                    {subscribing === currentTier ? 'Confirming...' : 'Renew (1 week)'}
                  </button>
                )}
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

          {currentTier >= 2 && (
            <button
              onClick={() => document.getElementById('nexus')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}
              className="w-full px-3 py-1.5 text-xs font-bold border border-[var(--eve-blue,#3B82F6)]
                         text-[var(--eve-blue,#3B82F6)] rounded hover:bg-[var(--eve-blue,#3B82F6)]
                         hover:text-[var(--eve-bg)] transition-colors"
            >
              Set Up NEXUS Webhooks
            </button>
          )}
        </div>
      </div>

      {/* Subscribe / Upgrade — hidden at max tier */}
      {currentTier < 3 && (
      <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-5 space-y-4">
        <h3 className="text-sm font-bold text-[var(--eve-green)] uppercase tracking-wider">
          {currentTier > 0 ? 'Upgrade' : 'Subscribe'}
        </h3>
        <p className="text-xs text-[var(--eve-dim)]">
          {currentTier > 0
            ? 'Unlock more intelligence by upgrading your tier. Pay on-chain with SUI or by card.'
            : 'Unlock deeper intelligence with a WatchTower subscription. Pay on-chain with SUI or by card.'}
        </p>

        {/* Stale price warning */}
        {pricing?.is_stale && (
          <div className="flex items-center justify-between bg-[var(--eve-bg)] border border-[var(--eve-orange,#FF6600)] rounded p-3">
            <div className="text-xs text-[var(--eve-orange,#FF6600)]">
              Price data may be outdated. SUI prices shown might not reflect current market rates.
            </div>
            <button
              onClick={refetchPricing}
              className="ml-3 px-3 py-1 text-xs font-bold border border-[var(--eve-orange,#FF6600)]
                         text-[var(--eve-orange,#FF6600)] rounded hover:bg-[var(--eve-orange,#FF6600)]
                         hover:text-[var(--eve-bg)] transition-colors shrink-0"
            >
              Refresh Prices
            </button>
          </div>
        )}

        {/* Pricing error */}
        {pricingError && (
          <div className="flex items-center justify-between bg-[var(--eve-bg)] border border-[var(--eve-red)] rounded p-3">
            <div className="text-xs text-[var(--eve-red)]">{pricingError}</div>
            <button
              onClick={refetchPricing}
              className="ml-3 px-3 py-1 text-xs font-bold border border-[var(--eve-red)]
                         text-[var(--eve-red)] rounded hover:bg-[var(--eve-red)]
                         hover:text-[var(--eve-bg)] transition-colors shrink-0"
            >
              Retry
            </button>
          </div>
        )}

        {/* SUI/USD rate display */}
        {pricing && !pricingLoading && (
          <div className="text-[10px] text-[var(--eve-dim)] text-right">
            1 SUI = ${pricing.sui_usd.toFixed(4)} USD
            {' '}&middot;{' '}
            Updated {new Date(pricing.fetched_at).toLocaleTimeString()}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {txError && (
            <div className="col-span-full text-xs text-[var(--eve-red)] bg-[var(--eve-bg)] border border-[var(--eve-red)] rounded p-2 mb-2">
              {txError}
            </div>
          )}
          {SUBSCRIPTION_TIERS.filter((plan) => plan.tier > currentTier).map((plan) => {
            return (
              <div
                key={plan.name}
                className="relative border rounded-lg p-4 space-y-3"
                style={{ borderColor: plan.color }}
              >
                {plan.popular && (
                  <div
                    className="absolute -top-2.5 left-1/2 -translate-x-1/2 text-[10px] font-bold uppercase
                               px-2 py-0.5 rounded"
                    style={{ backgroundColor: plan.color, color: 'var(--eve-bg)' }}
                  >
                    Popular
                  </div>
                )}
                <div className="text-center space-y-1">
                  <div className="text-xs font-bold uppercase" style={{ color: plan.color }}>
                    {plan.name}
                  </div>
                  <div className="text-lg font-bold text-[var(--eve-text)]">
                    {pricingLoading ? '...' : plan.suiPrice}
                  </div>
                  <div className="text-[10px] text-[var(--eve-dim)]">~{plan.fiatPrice} equivalent</div>
                </div>
                <ul className="text-[10px] text-[var(--eve-dim)] space-y-0.5">
                  {plan.features.map((f) => (
                    <li key={f}>+ {f}</li>
                  ))}
                </ul>
                <div className="space-y-2">
                  {pricing?.is_stale ? (
                    <button
                      className="w-full px-3 py-1.5 text-xs font-bold rounded border
                                 border-[var(--eve-orange,#FF6600)] text-[var(--eve-orange,#FF6600)]
                                 hover:bg-[var(--eve-orange,#FF6600)] hover:text-[var(--eve-bg)]
                                 transition-colors"
                      onClick={refetchPricing}
                    >
                      Refresh Prices
                    </button>
                  ) : (
                    <button
                      className="w-full px-3 py-1.5 text-xs font-bold rounded transition-opacity
                                 hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                      style={{ backgroundColor: plan.color, color: 'var(--eve-bg)' }}
                      disabled={subscribing !== null || pricingLoading || !pricing}
                      onClick={() => handleSubscribe(plan.tier)}
                    >
                      {subscribing === plan.tier ? 'Confirming...' : pricingLoading ? 'Loading...' : 'Pay with SUI'}
                    </button>
                  )}
                  <button
                    className="w-full px-3 py-1.5 text-xs font-bold rounded border
                               transition-colors hover:text-[var(--eve-text)]"
                    style={{ borderColor: plan.color, color: 'var(--eve-dim)' }}
                    onClick={async () => {
                      try {
                        const { url } = await api.createCheckout(plan.tier);
                        window.location.href = url;
                      } catch {
                        alert('Failed to start checkout. Please try again.');
                      }
                    }}
                  >
                    Pay with Card
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      )}

      {/* NEXUS Subscriptions */}
      <div id="nexus" className="bg-[var(--eve-surface)] border border-[var(--eve-blue,#3B82F6)] rounded-lg p-5 space-y-4">
        <button
          onClick={() => setNexusExpanded(!nexusExpanded)}
          className="w-full flex justify-between items-center"
        >
          <h3 className="text-sm font-bold text-[var(--eve-blue,#3B82F6)] uppercase tracking-wider">
            NEXUS Webhooks
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border
                             text-[var(--eve-blue,#3B82F6)] border-[var(--eve-blue,#3B82F6)]">
              Builder API
            </span>
            <span className="text-[var(--eve-blue,#3B82F6)] text-xs">
              {nexusExpanded ? '\u25B2' : '\u25BC'}
            </span>
          </div>
        </button>

        <p className="text-xs text-[var(--eve-dim)]">
          Subscribe to enriched event webhooks. WatchTower POSTs HMAC-signed payloads
          with resolved names, system data, and intelligence when matching events are indexed.
        </p>

        {nexusExpanded && (<>

        {/* Quota display */}
        {nexusQuota && (
          <div className="grid grid-cols-2 gap-3">
            <div className="border border-[var(--eve-border)] rounded p-2">
              <div className="text-[10px] text-[var(--eve-dim)] uppercase">Subscriptions</div>
              <div className="text-sm text-[var(--eve-text)] font-mono">
                {nexusQuota.subscriptions_used} / {nexusQuota.subscriptions_max}
              </div>
            </div>
            <div className="border border-[var(--eve-border)] rounded p-2">
              <div className="text-[10px] text-[var(--eve-dim)] uppercase">Deliveries Today</div>
              <div className="text-sm text-[var(--eve-text)] font-mono">
                {nexusQuota.deliveries_today} / {nexusQuota.deliveries_max}
              </div>
            </div>
          </div>
        )}

        {/* Tier gate message — hidden when quota allows access (hackathon mode) */}
        {nexusQuota && nexusQuota.subscriptions_max === 0 && (
          <div className="border border-[var(--eve-orange,#FF6600)] rounded p-3 text-center space-y-1">
            <div className="text-xs font-bold text-[var(--eve-orange,#FF6600)]">
              Oracle Tier Required
            </div>
            <p className="text-[10px] text-[var(--eve-dim)]">
              NEXUS webhooks require Oracle (Tier 2) or higher.
              Transfer items to a Watcher Assembly in-game to upgrade.
            </p>
          </div>
        )}

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
        {nexusQuota && nexusQuota.subscriptions_max > 0 && !showNexusForm ? (
          <button
            onClick={() => setShowNexusForm(true)}
            disabled={nexusQuota.subscriptions_used >= nexusQuota.subscriptions_max}
            className="w-full px-3 py-1.5 text-xs font-bold border border-[var(--eve-blue,#3B82F6)]
                       text-[var(--eve-blue,#3B82F6)] rounded hover:bg-[var(--eve-blue,#3B82F6)]
                       hover:text-[var(--eve-bg)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {nexusQuota.subscriptions_used >= nexusQuota.subscriptions_max
              ? `Limit Reached (${nexusQuota.subscriptions_used}/${nexusQuota.subscriptions_max})`
              : '+ New Subscription'}
          </button>
        ) : showNexusForm ? (
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
        ) : null}

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
        </>)}
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

    </div>
  );
}
