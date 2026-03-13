import { useState, useEffect } from 'react';
import { useSignAndExecuteTransaction } from '@mysten/dapp-kit';
import { Transaction } from '@mysten/sui/transactions';
import { api } from '../api';
import type { AnalyticsData } from '../api';
import { useAuth } from '../contexts/AuthContext';

const WATCHTOWER_PACKAGE = '0x3ca7e3af5bf5b072157d02534f5e4013cf11a12b79385c270d97de480e7b7dca';
const ADMIN_CAP = '0x5af68eea339255f184218108fa52859a08b572e2f906940bafbed436cbbeaaae';
const SUBSCRIPTION_REGISTRY = '0x4bb5a6999fadd2039b8cfcb7a1b3de0f07973fe0ec74181b024edaaa6069d160';
const SUI_CLOCK = '0x6';

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
      <div className="text-xs text-[var(--eve-dim)] uppercase tracking-wider">{label}</div>
      <div className="text-2xl font-bold text-[var(--eve-green)] mt-1">{typeof value === 'number' ? value.toLocaleString() : value}</div>
      {sub && <div className="text-xs text-[var(--eve-dim)] mt-1">{sub}</div>}
    </div>
  );
}

export function AdminAnalytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const { isAdmin } = useAuth();
  const { mutateAsync: signAndExecuteTransaction } = useSignAndExecuteTransaction();

  // Admin action state
  const [grantAddr, setGrantAddr] = useState('');
  const [grantTier, setGrantTier] = useState(1);
  const [grantDays, setGrantDays] = useState(7);
  const [grantLoading, setGrantLoading] = useState(false);
  const [grantResult, setGrantResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const [luxAddr, setLuxAddr] = useState('');
  const [luxTier, setLuxTier] = useState(1);
  const [luxLoading, setLuxLoading] = useState(false);
  const [luxResult, setLuxResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const handleGrantSubscription = async () => {
    if (!grantAddr.trim()) return;
    setGrantLoading(true);
    setGrantResult(null);
    try {
      const tx = new Transaction();
      tx.moveCall({
        target: `${WATCHTOWER_PACKAGE}::subscription::grant_subscription`,
        arguments: [
          tx.object(ADMIN_CAP),
          tx.object(SUBSCRIPTION_REGISTRY),
          tx.pure.address(grantAddr.trim()),
          tx.pure.u8(grantTier),
          tx.pure.u64(grantDays),
          tx.object(SUI_CLOCK),
        ],
      });
      await signAndExecuteTransaction({ transaction: tx });
      setGrantResult({ ok: true, msg: `Granted tier ${grantTier} for ${grantDays}d` });
      setGrantAddr('');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Transaction failed';
      setGrantResult({ ok: false, msg });
    } finally {
      setGrantLoading(false);
    }
  };

  const handleCreditLux = async () => {
    if (!luxAddr.trim()) return;
    setLuxLoading(true);
    setLuxResult(null);
    try {
      const tx = new Transaction();
      tx.moveCall({
        target: `${WATCHTOWER_PACKAGE}::subscription::credit_lux_payment`,
        arguments: [
          tx.object(ADMIN_CAP),
          tx.object(SUBSCRIPTION_REGISTRY),
          tx.pure.address(luxAddr.trim()),
          tx.pure.u8(luxTier),
          tx.object(SUI_CLOCK),
        ],
      });
      await signAndExecuteTransaction({ transaction: tx });
      setLuxResult({ ok: true, msg: `Credited LUX payment for tier ${luxTier}` });
      setLuxAddr('');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Transaction failed';
      setLuxResult({ ok: false, msg });
    } finally {
      setLuxLoading(false);
    }
  };

  useEffect(() => {
    api.analytics()
      .then(setData)
      .catch(() => setError('Failed to load analytics'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="text-center py-8 text-[var(--eve-dim)]">
        <span className="pulse-green text-[var(--eve-green)]">///</span> Loading analytics...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-[var(--eve-red)] bg-red-900/20 border border-red-900/40 rounded px-4 py-3">
        {error || 'No data'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-[var(--eve-green)] tracking-wider">
          ADMIN ANALYTICS
        </h2>
        <div className="text-xs text-[var(--eve-dim)]">
          Last updated: {new Date(data.timestamp * 1000).toLocaleString()}
        </div>
      </div>

      {/* Totals */}
      <div>
        <h3 className="text-sm font-bold text-[var(--eve-text)] mb-3 uppercase tracking-wider">Platform Totals</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Entities" value={data.totals.entities} sub={`${data.totals.characters} chars / ${data.totals.gates} gates`} />
          <StatCard label="Killmails" value={data.totals.killmails} />
          <StatCard label="Gate Events" value={data.totals.gate_events} />
          <StatCard label="Titles Earned" value={data.totals.titles} />
          <StatCard label="Stories Generated" value={data.totals.stories} />
          <StatCard label="Active Watches" value={data.totals.active_watches} />
        </div>
      </div>

      {/* Activity */}
      <div>
        <h3 className="text-sm font-bold text-[var(--eve-text)] mb-3 uppercase tracking-wider">Activity</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <StatCard label="Kills (24h)" value={data.activity.kills_24h} sub={`${data.activity.kills_7d} this week`} />
          <StatCard label="Gate Transits (24h)" value={data.activity.gate_transits_24h} sub={`${data.activity.gate_transits_7d} this week`} />
          <StatCard label="New Entities (24h)" value={data.activity.new_entities_24h} />
        </div>
      </div>

      {/* Subscriptions */}
      <div>
        <h3 className="text-sm font-bold text-[var(--eve-text)] mb-3 uppercase tracking-wider">Subscriptions</h3>
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Scout" value={data.subscriptions.scout} />
          <StatCard label="Oracle" value={data.subscriptions.oracle} />
          <StatCard label="Spymaster" value={data.subscriptions.spymaster} />
        </div>
      </div>

      {/* Top Active (7d) */}
      <div>
        <h3 className="text-sm font-bold text-[var(--eve-text)] mb-3 uppercase tracking-wider">Top Active (7d)</h3>
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--eve-border)] text-[var(--eve-dim)] text-xs uppercase">
                <th className="px-4 py-2 text-left">Entity</th>
                <th className="px-4 py-2 text-right">Events</th>
                <th className="px-4 py-2 text-right">Kills</th>
                <th className="px-4 py-2 text-right">Deaths</th>
              </tr>
            </thead>
            <tbody>
              {data.top_active_7d.map((e) => (
                <tr key={e.entity_id} className="border-b border-[var(--eve-border)] last:border-0 hover:bg-[var(--eve-border)]">
                  <td className="px-4 py-2 text-[var(--eve-green)] font-mono text-xs">
                    {e.display_name || e.entity_id.slice(0, 12)}
                  </td>
                  <td className="px-4 py-2 text-right text-[var(--eve-text)]">{e.event_count.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right text-[var(--eve-red)]">{e.kill_count}</td>
                  <td className="px-4 py-2 text-right text-[var(--eve-dim)]">{e.death_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Admin Contract Actions */}
      {isAdmin && (
        <div>
          <h3 className="text-sm font-bold text-[var(--eve-text)] mb-3 uppercase tracking-wider">Admin Actions</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

            {/* Grant Subscription */}
            <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 space-y-3">
              <div className="text-xs text-[var(--eve-dim)] uppercase tracking-wider">Grant Subscription</div>
              <input
                type="text"
                placeholder="Subscriber address (0x...)"
                value={grantAddr}
                onChange={(e) => setGrantAddr(e.target.value)}
                className="w-full bg-[var(--eve-bg)] border border-[var(--eve-border)] rounded px-3 py-2 text-sm text-[var(--eve-text)] font-mono placeholder:text-[var(--eve-dim)] focus:border-[var(--eve-green)] focus:outline-none"
              />
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="text-xs text-[var(--eve-dim)] block mb-1">Tier</label>
                  <select
                    value={grantTier}
                    onChange={(e) => setGrantTier(Number(e.target.value))}
                    className="w-full bg-[var(--eve-bg)] border border-[var(--eve-border)] rounded px-3 py-2 text-sm text-[var(--eve-text)] focus:border-[var(--eve-green)] focus:outline-none"
                  >
                    <option value={1}>1 — Scout</option>
                    <option value={2}>2 — Oracle</option>
                    <option value={3}>3 — Spymaster</option>
                  </select>
                </div>
                <div className="flex-1">
                  <label className="text-xs text-[var(--eve-dim)] block mb-1">Days</label>
                  <input
                    type="number"
                    min={1}
                    value={grantDays}
                    onChange={(e) => setGrantDays(Number(e.target.value))}
                    className="w-full bg-[var(--eve-bg)] border border-[var(--eve-border)] rounded px-3 py-2 text-sm text-[var(--eve-text)] focus:border-[var(--eve-green)] focus:outline-none"
                  />
                </div>
              </div>
              <button
                onClick={handleGrantSubscription}
                disabled={grantLoading || !grantAddr.trim()}
                className="w-full bg-[var(--eve-green)] text-[var(--eve-bg)] font-bold text-sm py-2 rounded hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                {grantLoading ? 'Signing...' : 'Grant Subscription'}
              </button>
              {grantResult && (
                <div className={`text-xs px-3 py-2 rounded ${grantResult.ok ? 'text-[var(--eve-green)] bg-green-900/20 border border-green-900/40' : 'text-[var(--eve-red)] bg-red-900/20 border border-red-900/40'}`}>
                  {grantResult.msg}
                </div>
              )}
            </div>

            {/* Credit LUX Payment */}
            <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 space-y-3">
              <div className="text-xs text-[var(--eve-dim)] uppercase tracking-wider">Credit LUX Payment</div>
              <input
                type="text"
                placeholder="Subscriber address (0x...)"
                value={luxAddr}
                onChange={(e) => setLuxAddr(e.target.value)}
                className="w-full bg-[var(--eve-bg)] border border-[var(--eve-border)] rounded px-3 py-2 text-sm text-[var(--eve-text)] font-mono placeholder:text-[var(--eve-dim)] focus:border-[var(--eve-green)] focus:outline-none"
              />
              <div>
                <label className="text-xs text-[var(--eve-dim)] block mb-1">Tier</label>
                <select
                  value={luxTier}
                  onChange={(e) => setLuxTier(Number(e.target.value))}
                  className="w-full bg-[var(--eve-bg)] border border-[var(--eve-border)] rounded px-3 py-2 text-sm text-[var(--eve-text)] focus:border-[var(--eve-green)] focus:outline-none"
                >
                  <option value={1}>1 — Scout</option>
                  <option value={2}>2 — Oracle</option>
                  <option value={3}>3 — Spymaster</option>
                </select>
              </div>
              <button
                onClick={handleCreditLux}
                disabled={luxLoading || !luxAddr.trim()}
                className="w-full bg-[var(--eve-orange)] text-[var(--eve-bg)] font-bold text-sm py-2 rounded hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                {luxLoading ? 'Signing...' : 'Credit LUX'}
              </button>
              {luxResult && (
                <div className={`text-xs px-3 py-2 rounded ${luxResult.ok ? 'text-[var(--eve-green)] bg-green-900/20 border border-green-900/40' : 'text-[var(--eve-red)] bg-red-900/20 border border-red-900/40'}`}>
                  {luxResult.msg}
                </div>
              )}
            </div>

          </div>
        </div>
      )}
    </div>
  );
}
