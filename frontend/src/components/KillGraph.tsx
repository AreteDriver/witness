import { useEffect, useState } from 'react';
import { api } from '../api';
import type { KillGraphData } from '../api';

interface Props {
  entityId?: string;
  onSelect: (entityId: string) => void;
}

function dangerColor(kills: number): string {
  if (kills >= 50) return 'var(--eve-red)';
  if (kills >= 20) return 'var(--eve-orange)';
  if (kills >= 5) return 'var(--eve-green)';
  return 'var(--eve-dim)';
}

export function KillGraph({ entityId, onSelect }: Props) {
  const [data, setData] = useState<KillGraphData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.killGraph(entityId).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [entityId]);

  if (loading) return <div className="text-[var(--eve-dim)]">Loading kill graph...</div>;
  if (!data || data.edges.length === 0) return <div className="text-[var(--eve-dim)]">No kill relationships found.</div>;

  return (
    <div className="space-y-4">
      <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
        Kill Network {entityId ? '(Entity)' : '(Global)'}
      </h3>

      {/* Vendettas */}
      {data.vendettas.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs uppercase tracking-wider text-[var(--eve-red)] font-bold">
            Vendettas — Mutual Kills
          </h4>
          {data.vendettas.map((v, i) => (
            <div key={i} className="bg-red-900/20 border border-red-900/40 rounded p-2 flex justify-between items-center text-sm">
              <div className="flex gap-2 items-center">
                <button onClick={() => onSelect(v.entity_1)} className="text-[var(--eve-green)] hover:underline">
                  {v.entity_1_name || v.entity_1.slice(0, 12)}
                </button>
                <span className="text-[var(--eve-red)]">{v.kills_1_to_2}</span>
                <span className="text-[var(--eve-dim)]">vs</span>
                <span className="text-[var(--eve-red)]">{v.kills_2_to_1}</span>
                <button onClick={() => onSelect(v.entity_2)} className="text-[var(--eve-green)] hover:underline">
                  {v.entity_2_name || v.entity_2.slice(0, 12)}
                </button>
              </div>
              <span className="text-xs text-[var(--eve-dim)]">{v.total} total</span>
            </div>
          ))}
        </div>
      )}

      {/* Top edges */}
      <div className="space-y-1">
        <h4 className="text-xs uppercase tracking-wider text-[var(--eve-dim)] font-bold">
          Top Kill Relationships ({data.total_nodes} pilots, {data.total_edges} connections)
        </h4>
        <div className="max-h-64 overflow-y-auto space-y-1">
          {data.edges.slice(0, 20).map((e, i) => (
            <div key={i} className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded px-3 py-1.5 flex justify-between items-center text-sm">
              <div className="flex gap-2 items-center">
                <button onClick={() => onSelect(e.attacker)} className="text-[var(--eve-green)] hover:underline text-xs">
                  {e.attacker_name || e.attacker.slice(0, 12)}
                </button>
                <span className="text-[var(--eve-dim)]">killed</span>
                <button onClick={() => onSelect(e.victim)} className="text-[var(--eve-text)] hover:underline text-xs">
                  {e.victim_name || e.victim.slice(0, 12)}
                </button>
              </div>
              <span className="font-bold text-xs" style={{ color: dangerColor(e.count) }}>
                {e.count}x
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
