import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { api } from '../api';
import type { HotzoneData } from '../api';

const DANGER_COLORS: Record<string, string> = {
  extreme: '#ff3232',
  high: '#ff9632',
  moderate: '#f0c040',
  low: '#00ff88',
  minimal: '#666',
};

export function HotzoneMap() {
  const navigate = useNavigate();
  const [hotzones, setHotzones] = useState<HotzoneData[]>([]);
  const [window, setWindow] = useState('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.hotzones(window)
      .then((d) => setHotzones(d.hotzones))
      .catch(() => setHotzones([]))
      .finally(() => setLoading(false));
  }, [window]);

  const windows = ['24h', '7d', '30d', 'all'] as const;
  const maxKills = Math.max(...hotzones.map((h) => h.kills), 1);

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--eve-orange)] font-bold">
          Kill Density — Danger Zones
        </h3>
        <div className="flex gap-1">
          {windows.map((w) => (
            <button
              key={w}
              onClick={() => setWindow(w)}
              className={`px-2 py-0.5 text-xs rounded font-mono ${
                window === w
                  ? 'bg-[var(--eve-green)] text-[var(--eve-bg)] font-bold'
                  : 'text-[var(--eve-dim)] hover:text-[var(--eve-text)]'
              }`}
            >
              {w}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="text-[var(--eve-dim)] text-sm py-4">
          <span className="pulse-green text-[var(--eve-green)]">///</span> Scanning systems...
        </div>
      )}

      {!loading && hotzones.length === 0 && (
        <div className="text-[var(--eve-dim)] text-sm py-4">No kill activity in this window.</div>
      )}

      {!loading && hotzones.length > 0 && (
        <div className="space-y-0">
          {/* Visual bar heatmap */}
          {hotzones.map((hz) => {
            const pct = (hz.kills / maxKills) * 100;
            const color = DANGER_COLORS[hz.danger_level] || DANGER_COLORS.minimal;
            const displayName = hz.solar_system_name || hz.solar_system_id.slice(0, 12);

            return (
              <button
                key={hz.solar_system_id}
                onClick={() => navigate(`/system/${hz.solar_system_id}`)}
                className="w-full text-left group relative"
              >
                {/* Bar row */}
                <div className="flex items-center gap-2 py-1.5 px-1 hover:bg-[var(--eve-border)]/30 rounded transition-colors">
                  {/* System label */}
                  <div className="w-28 shrink-0 truncate">
                    <span
                      className="font-mono text-xs font-bold group-hover:underline"
                      style={{ color }}
                    >
                      {displayName}
                    </span>
                  </div>

                  {/* Bar */}
                  <div className="flex-1 h-5 relative bg-[var(--eve-border)]/20 rounded-sm overflow-hidden">
                    <div
                      className="h-full rounded-sm transition-all duration-500"
                      style={{
                        width: `${Math.max(pct, 3)}%`,
                        background: `linear-gradient(90deg, ${color}40, ${color}90)`,
                        boxShadow: `0 0 8px ${color}30`,
                      }}
                    />
                    {/* Kill count inside bar */}
                    <div className="absolute inset-0 flex items-center px-2">
                      <span className="font-mono text-[10px] font-bold text-white/90 drop-shadow-sm">
                        {hz.kills}
                      </span>
                    </div>
                  </div>

                  {/* Danger badge */}
                  <div className="w-16 shrink-0 text-right">
                    <span
                      className="font-mono text-[9px] uppercase font-bold"
                      style={{ color }}
                    >
                      {hz.danger_level}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}

          {/* Summary footer */}
          <div className="flex justify-between items-center pt-3 mt-2 border-t border-[var(--eve-border)]">
            <div className="text-[10px] text-[var(--eve-dim)] font-mono">
              {hotzones.length} systems — {hotzones.reduce((s, h) => s + h.kills, 0)} total kills
            </div>
            <div className="flex gap-3 text-[9px] font-mono">
              {Object.entries(DANGER_COLORS).slice(0, 4).map(([level, c]) => (
                <span key={level} className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: c }} />
                  <span className="text-[var(--eve-dim)] uppercase">{level}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
