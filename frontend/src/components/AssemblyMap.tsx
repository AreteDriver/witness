import { useEffect, useState } from 'react';
import { api } from '../api';
import type { AssemblyStats } from '../api';

const STATE_COLORS: Record<string, string> = {
  online: 'var(--eve-green)',
  anchored: 'var(--eve-blue)',
  offline: 'var(--eve-red)',
  unanchored: 'var(--eve-dim)',
};

export function AssemblyMap() {
  const [stats, setStats] = useState<AssemblyStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.assemblies().then(setStats).catch(() => setStats(null)).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
        <span className="text-[var(--eve-dim)] text-sm">Loading assembly network...</span>
      </div>
    );
  }

  if (!stats || stats.total === 0) {
    return (
      <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
        <h3 className="text-sm font-bold text-[var(--eve-dim)] uppercase tracking-wider mb-2">
          Watcher Network
        </h3>
        <p className="text-xs text-[var(--eve-dim)]">No assemblies deployed yet.</p>
      </div>
    );
  }

  return (
    <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-[var(--eve-dim)] uppercase tracking-wider">
          Watcher Network
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-[var(--eve-green)] text-sm font-bold">{stats.online}</span>
          <span className="text-xs text-[var(--eve-dim)]">/ {stats.total} online</span>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-3">
        <div className="text-center">
          <div className="text-lg font-bold text-[var(--eve-green)]">{stats.systems_covered}</div>
          <div className="text-[10px] text-[var(--eve-dim)]">Systems</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-[var(--eve-text)]">{stats.online}</div>
          <div className="text-[10px] text-[var(--eve-dim)]">Online</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-[var(--eve-red)]">{stats.offline}</div>
          <div className="text-[10px] text-[var(--eve-dim)]">Offline</div>
        </div>
      </div>

      {/* Assembly list */}
      <div className="space-y-1 max-h-48 overflow-y-auto">
        {stats.assemblies.map((a) => (
          <div key={a.assembly_id} className="flex items-center justify-between text-xs py-1 border-b border-[var(--eve-border)]">
            <div className="flex items-center gap-2">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: STATE_COLORS[a.state] || 'var(--eve-dim)' }}
              />
              <span className="text-[var(--eve-text)]">
                {a.solar_system_name || a.solar_system_id?.slice(0, 12) || 'Unknown'}
              </span>
            </div>
            <span className="text-[var(--eve-dim)]">{a.type}</span>
          </div>
        ))}
      </div>

      <div className="text-[10px] text-[var(--eve-dim)] opacity-60">
        Auto-updated from chain data
      </div>
    </div>
  );
}
