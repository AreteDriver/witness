import { useEffect, useState } from 'react';
import { api } from '../api';
import type { StreakData } from '../api';

interface Props {
  entityId?: string;
  onSelect: (entityId: string) => void;
}

function statusStyle(status: string): { color: string; label: string } {
  switch (status) {
    case 'hot': return { color: 'var(--eve-red)', label: 'ON FIRE' };
    case 'active': return { color: 'var(--eve-green)', label: 'ACTIVE' };
    case 'cooling': return { color: 'var(--eve-orange)', label: 'COOLING' };
    case 'dormant': return { color: 'var(--eve-dim)', label: 'DORMANT' };
    default: return { color: 'var(--eve-dim)', label: 'INACTIVE' };
  }
}

function StreakBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="w-full h-1.5 bg-[var(--eve-border)] rounded overflow-hidden">
      <div className="h-full rounded" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
  );
}

export function StreakTracker({ entityId, onSelect }: Props) {
  const [entityStreak, setEntityStreak] = useState<StreakData | null>(null);
  const [hotStreaks, setHotStreaks] = useState<StreakData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const promises: Promise<void>[] = [
      api.hotStreaks().then((d) => setHotStreaks(d.streaks)).catch(() => setHotStreaks([])),
    ];
    if (entityId) {
      promises.push(
        api.streak(entityId).then(setEntityStreak).catch(() => setEntityStreak(null))
      );
    }
    Promise.all(promises).finally(() => setLoading(false));
  }, [entityId]);

  if (loading) return <div className="text-[var(--eve-dim)]">Analyzing momentum...</div>;

  const maxStreak = Math.max(
    entityStreak?.longest_streak ?? 0,
    ...hotStreaks.map((s) => s.longest_streak),
    1
  );

  return (
    <div className="space-y-4">
      {/* Entity-specific streak */}
      {entityStreak && entityStreak.longest_streak > 0 && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 space-y-2">
          <div className="flex justify-between items-center">
            <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
              Momentum
            </h3>
            <span
              className="text-xs font-bold px-2 py-0.5 rounded"
              style={{
                color: statusStyle(entityStreak.status).color,
                border: `1px solid ${statusStyle(entityStreak.status).color}`,
              }}
            >
              {statusStyle(entityStreak.status).label}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <div className="text-lg font-bold text-[var(--eve-text)]">{entityStreak.current_streak}</div>
              <div className="text-xs text-[var(--eve-dim)]">Current Streak</div>
            </div>
            <div>
              <div className="text-lg font-bold text-[var(--eve-text)]">{entityStreak.longest_streak}</div>
              <div className="text-xs text-[var(--eve-dim)]">Longest Streak</div>
            </div>
            <div>
              <div className="text-lg font-bold text-[var(--eve-text)]">{entityStreak.avg_kills_per_week}</div>
              <div className="text-xs text-[var(--eve-dim)]">Kills/Week</div>
            </div>
          </div>

          <div className="flex gap-4 text-xs text-[var(--eve-dim)]">
            <span>7d: <span className="text-[var(--eve-text)]">{entityStreak.kills_7d}</span> kills</span>
            <span>30d: <span className="text-[var(--eve-text)]">{entityStreak.kills_30d}</span> kills</span>
          </div>
        </div>
      )}

      {/* Hot streaks leaderboard */}
      {hotStreaks.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs uppercase tracking-wider text-[var(--eve-red)] font-bold">
            Active Hunters
          </h3>
          <div className="space-y-1">
            {hotStreaks.map((s) => {
              const style = statusStyle(s.status);
              return (
                <div
                  key={s.entity_id}
                  className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded px-3 py-2"
                >
                  <div className="flex justify-between items-center mb-1">
                    <button
                      onClick={() => onSelect(s.entity_id)}
                      className="text-sm text-[var(--eve-green)] hover:underline"
                    >
                      {s.display_name || s.entity_id.slice(0, 12)}
                    </button>
                    <div className="flex gap-2 items-center">
                      <span className="text-xs" style={{ color: style.color }}>
                        {style.label}
                      </span>
                      {s.current_streak > 0 && (
                        <span className="text-xs font-bold text-[var(--eve-red)]">
                          {s.current_streak} streak
                        </span>
                      )}
                    </div>
                  </div>
                  <StreakBar value={s.longest_streak} max={maxStreak} color={style.color} />
                  <div className="flex gap-3 mt-1 text-xs text-[var(--eve-dim)]">
                    <span>{s.kills_7d} kills/7d</span>
                    <span>{s.avg_kills_per_week} avg/wk</span>
                    <span>best: {s.longest_streak}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {hotStreaks.length === 0 && !entityStreak && (
        <div className="text-[var(--eve-dim)] text-sm">No active hunters detected.</div>
      )}
    </div>
  );
}
