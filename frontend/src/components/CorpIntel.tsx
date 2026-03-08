import { useEffect, useState } from 'react';
import { api } from '../api';
import type { CorpData, CorpRivalry } from '../api';

function threatColor(kills: number): string {
  if (kills >= 100) return 'var(--eve-red)';
  if (kills >= 50) return 'var(--eve-orange)';
  if (kills >= 20) return '#f0c040';
  if (kills > 0) return 'var(--eve-green)';
  return 'var(--eve-dim)';
}

export function CorpIntel() {
  const [corps, setCorps] = useState<CorpData[]>([]);
  const [rivalries, setRivalries] = useState<CorpRivalry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.corps().then((d) => setCorps(d.corps)).catch(() => setCorps([])),
      api.corpRivalries().then((d) => setRivalries(d.rivalries)).catch(() => setRivalries([])),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-[var(--eve-dim)]">Analyzing organizations...</div>;

  return (
    <div className="space-y-4">
      {/* Corp Rivalries */}
      {rivalries.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs uppercase tracking-wider text-[var(--eve-red)] font-bold">
            Corp Wars
          </h3>
          {rivalries.slice(0, 5).map((r, i) => (
            <div key={i} className="bg-red-900/20 border border-red-900/40 rounded p-2 text-sm">
              <div className="flex justify-between items-center">
                <div className="flex gap-2 items-center">
                  <span className="text-[var(--eve-green)]">{r.corp_1.slice(0, 12)}</span>
                  <span className="text-[var(--eve-red)] font-bold">{r.kills_1_to_2}</span>
                  <span className="text-[var(--eve-dim)]">vs</span>
                  <span className="text-[var(--eve-red)] font-bold">{r.kills_2_to_1}</span>
                  <span className="text-[var(--eve-green)]">{r.corp_2.slice(0, 12)}</span>
                </div>
                <span className="text-xs text-[var(--eve-dim)]">{r.total} mutual kills</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Corp Leaderboard */}
      {corps.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
            Corp Combat Rankings
          </h3>
          <div className="space-y-1">
            {corps.slice(0, 15).map((c, i) => (
              <div
                key={c.corp_id}
                className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded px-3 py-2 flex justify-between items-center"
              >
                <div className="flex gap-3 items-center">
                  <span className="text-xs text-[var(--eve-dim)] w-5">{i + 1}</span>
                  <span className="text-sm text-[var(--eve-text)]">{c.corp_id.slice(0, 14)}</span>
                </div>
                <div className="flex gap-4 text-xs">
                  <span>{c.member_count} members</span>
                  <span style={{ color: threatColor(c.total_kills) }}>{c.total_kills} kills</span>
                  <span className="text-[var(--eve-dim)]">{c.total_deaths} deaths</span>
                  <span className="text-[var(--eve-text)]">{(c.kill_ratio * 100).toFixed(0)}% KR</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {corps.length === 0 && rivalries.length === 0 && (
        <div className="text-[var(--eve-dim)] text-sm">No corporation data available.</div>
      )}
    </div>
  );
}
