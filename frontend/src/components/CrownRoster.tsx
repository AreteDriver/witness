import { useEffect, useState } from 'react';
import { api } from '../api';
import type { CrownEntry, CrownRoster as CrownRosterData } from '../api';

const CROWN_COLORS: Record<string, string> = {
  warrior: 'var(--eve-red)',
  merchant: 'var(--eve-green)',
  explorer: 'var(--eve-yellow)',
  diplomat: '#9b59b6',
  engineer: 'var(--eve-orange)',
};

export function CrownRoster() {
  const [crowns, setCrowns] = useState<CrownEntry[]>([]);
  const [roster, setRoster] = useState<CrownRosterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError(false);
    Promise.all([api.crowns(), api.crownRoster()])
      .then(([c, r]) => {
        setCrowns(c.data);
        setRoster(r.data);
        setLoading(false);
      })
      .catch(() => { setError(true); setLoading(false); });
  }, [retryKey]);

  if (loading) return <div className="text-[var(--eve-dim)]">Loading crowns...</div>;

  if (error) {
    return (
      <div className="text-xs text-[var(--eve-red)]">
        Failed to load crown roster.{' '}
        <button
          onClick={() => { setError(false); setRetryKey((k) => k + 1); }}
          className="underline hover:text-[var(--eve-text)] transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
        Crown Roster
      </h3>

      {/* Distribution chart (bar) */}
      {roster && roster.distribution.length > 0 && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded p-3 space-y-2">
          <div className="flex justify-between text-xs text-[var(--eve-dim)]">
            <span>{roster.crowned} crowned</span>
            {roster.uncrowned > 0 && (
              <span>{roster.uncrowned} unidentified</span>
            )}
          </div>
          {roster.distribution.map((d) => {
            const pct = roster.crowned > 0 ? (d.count / roster.crowned) * 100 : 0;
            return (
              <div key={d.crown_type} className="space-y-0.5">
                <div className="flex justify-between text-xs">
                  <span
                    className="font-bold capitalize"
                    style={{ color: CROWN_COLORS[d.crown_type] || 'var(--eve-text)' }}
                  >
                    {d.crown_type || 'unknown'}
                  </span>
                  <span className="text-[var(--eve-dim)]">{d.count}</span>
                </div>
                <div className="w-full h-1.5 bg-[var(--eve-border)] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: CROWN_COLORS[d.crown_type] || 'var(--eve-dim)',
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Member list */}
      {crowns.length > 0 && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded p-3">
          <div className="text-xs text-[var(--eve-dim)] mb-2 uppercase font-bold">Members</div>
          <div className="space-y-0.5 max-h-60 overflow-y-auto pr-1">
            {crowns.map((c) => (
              <div key={c.crown_id} className="flex items-center gap-2 text-xs">
                <span className="text-[var(--eve-text)] flex-1 truncate">
                  {c.character_name || c.character_id}
                </span>
                <span
                  className="font-bold capitalize shrink-0 text-right"
                  style={{ color: CROWN_COLORS[c.crown_type] || 'var(--eve-dim)' }}
                >
                  {c.crown_type || 'none'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {crowns.length === 0 && (
        <div className="text-[var(--eve-dim)] text-sm">No crown data yet.</div>
      )}
    </div>
  );
}
