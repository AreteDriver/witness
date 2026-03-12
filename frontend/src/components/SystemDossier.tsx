import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { api } from '../api';
import type { SystemDossier as SystemDossierData } from '../api';

const DANGER_COLORS: Record<string, string> = {
  extreme: 'text-[var(--eve-red)]',
  high: 'text-[var(--eve-orange)]',
  moderate: 'text-[var(--eve-yellow,#FFCC00)]',
  low: 'text-[var(--eve-green)]',
  minimal: 'text-[var(--eve-dim)]',
};

export function SystemDossier() {
  const { systemId } = useParams<{ systemId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<SystemDossierData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!systemId) return;
    setLoading(true);
    setError('');
    api.systemDossier(systemId)
      .then(setData)
      .catch(() => setError(`System not found: ${systemId}`))
      .finally(() => setLoading(false));
  }, [systemId]);

  if (!systemId) {
    navigate('/');
    return null;
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-[var(--eve-dim)] py-8">
        <span className="pulse-green text-[var(--eve-green)]">///</span>
        Scanning system...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <div className="text-[var(--eve-red)] text-sm bg-red-900/20 border border-red-900/40 rounded px-4 py-2">
          {error || 'No data'}
        </div>
        <button onClick={() => navigate('/')} className="text-xs text-[var(--eve-green)] hover:underline">
          Back to search
        </button>
      </div>
    );
  }

  const displayName = data.solar_system_name || systemId.slice(0, 16);
  const dangerColor = DANGER_COLORS[data.danger_level] || 'text-[var(--eve-dim)]';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <button onClick={() => navigate('/')} className="text-xs text-[var(--eve-dim)] hover:text-[var(--eve-green)] mb-1">
          &larr; Back
        </button>
        <h2 className="text-lg font-bold text-[var(--eve-text)]">
          <span className="text-[var(--eve-orange)]">SYSTEM</span>
          <span className="text-[var(--eve-green)] ml-2">{displayName}</span>
        </h2>
        <div className="text-xs text-[var(--eve-dim)] mt-0.5 font-mono">{systemId}</div>
      </div>

      {/* Threat overview */}
      {data.total_kills > 0 ? (
        <>
          <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
            <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--eve-orange)] font-bold mb-3">
              Threat Assessment
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">Danger</div>
                <div className={`text-lg font-bold ${dangerColor}`}>{data.danger_level.toUpperCase()}</div>
              </div>
              <div>
                <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">Total Kills</div>
                <div className="text-lg font-bold text-[var(--eve-red)]">{data.total_kills}</div>
              </div>
              <div>
                <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">Kills (24h)</div>
                <div className="text-lg font-bold text-[var(--eve-text)]">{data.kills_24h ?? 0}</div>
              </div>
              <div>
                <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">Kills (7d)</div>
                <div className="text-lg font-bold text-[var(--eve-text)]">{data.kills_7d ?? 0}</div>
              </div>
              <div>
                <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">Unique Attackers</div>
                <div className="text-lg font-bold text-[var(--eve-text)]">{data.unique_attackers ?? 0}</div>
              </div>
              <div>
                <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">Unique Victims</div>
                <div className="text-lg font-bold text-[var(--eve-text)]">{data.unique_victims ?? 0}</div>
              </div>
              <div>
                <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">Gate Transits</div>
                <div className="text-lg font-bold text-[var(--eve-text)]">{data.gate_transits ?? 0}</div>
              </div>
              <div>
                <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">First Kill</div>
                <div className="text-sm text-[var(--eve-text)]">
                  {data.first_kill ? new Date(data.first_kill * 1000).toLocaleDateString() : '—'}
                </div>
              </div>
            </div>
          </div>

          {/* Top combatants */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {data.top_attackers && data.top_attackers.length > 0 && (
              <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
                <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--eve-red)] font-bold mb-3">
                  Most Lethal (in system)
                </h3>
                <div className="space-y-2">
                  {data.top_attackers.map((a) => (
                    <button
                      key={a.entity_id}
                      onClick={() => navigate(`/entity/${a.entity_id}`)}
                      className="w-full flex justify-between items-center text-sm hover:bg-[var(--eve-border)] rounded px-2 py-1"
                    >
                      <span className="text-[var(--eve-green)] font-mono text-xs">{a.display_name}</span>
                      <span className="text-[var(--eve-red)] text-xs">{a.kills} kills</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {data.top_victims && data.top_victims.length > 0 && (
              <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
                <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--eve-orange)] font-bold mb-3">
                  Most Targeted (in system)
                </h3>
                <div className="space-y-2">
                  {data.top_victims.map((v) => (
                    <button
                      key={v.entity_id}
                      onClick={() => navigate(`/entity/${v.entity_id}`)}
                      className="w-full flex justify-between items-center text-sm hover:bg-[var(--eve-border)] rounded px-2 py-1"
                    >
                      <span className="text-[var(--eve-green)] font-mono text-xs">{v.display_name}</span>
                      <span className="text-[var(--eve-dim)] text-xs">{v.deaths} deaths</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Activity heatmap (hour distribution) */}
          {data.hour_distribution && Object.keys(data.hour_distribution).length > 0 && (
            <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
              <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--eve-orange)] font-bold mb-3">
                Kill Activity by Hour (UTC)
              </h3>
              <div className="flex gap-0.5 items-end h-16">
                {Array.from({ length: 24 }, (_, h) => {
                  const count = data.hour_distribution?.[h] ?? 0;
                  const max = Math.max(...Object.values(data.hour_distribution ?? {}), 1);
                  const pct = (count / max) * 100;
                  return (
                    <div key={h} className="flex-1 flex flex-col items-center gap-0.5" title={`${h}:00 — ${count} kills`}>
                      <div
                        className="w-full rounded-sm bg-[var(--eve-green)]"
                        style={{ height: `${Math.max(pct, 2)}%`, opacity: count > 0 ? 0.3 + (pct / 100) * 0.7 : 0.1 }}
                      />
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-between text-[9px] text-[var(--eve-dim)] mt-1 font-mono">
                <span>00:00</span>
                <span>06:00</span>
                <span>12:00</span>
                <span>18:00</span>
                <span>23:00</span>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 text-center text-[var(--eve-dim)]">
          No kill activity recorded in this system.
        </div>
      )}

      {/* Infrastructure */}
      {data.infrastructure && data.infrastructure.length > 0 && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
          <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--eve-orange)] font-bold mb-3">
            Infrastructure ({data.infrastructure.length})
          </h3>
          <div className="space-y-1">
            {data.infrastructure.map((a) => (
              <div key={a.assembly_id} className="flex justify-between text-xs">
                <span className="text-[var(--eve-text)]">{a.type}</span>
                <span className={a.state === 'online' ? 'text-[var(--eve-green)]' : 'text-[var(--eve-dim)]'}>
                  {a.state}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent stories */}
      {data.recent_stories && data.recent_stories.length > 0 && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
          <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--eve-orange)] font-bold mb-3">
            Recent Intelligence
          </h3>
          <div className="space-y-3">
            {data.recent_stories.map((s) => (
              <div key={s.id} className="border-l-2 border-[var(--eve-green)]/30 pl-3">
                <div className="text-xs text-[var(--eve-text)]">{s.headline}</div>
                <div className="text-[10px] text-[var(--eve-dim)] mt-0.5 font-mono">
                  {new Date(s.timestamp * 1000).toLocaleString()}
                  <span className="ml-2 uppercase">{s.severity}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
