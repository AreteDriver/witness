import { Fingerprint } from '../api';

function ThreatBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    extreme: 'bg-red-900 text-red-300',
    high: 'bg-red-900/60 text-red-400',
    moderate: 'bg-yellow-900/60 text-yellow-400',
    low: 'bg-green-900/60 text-green-400',
    none: 'bg-[var(--eve-border)] text-[var(--eve-dim)]',
    unknown: 'bg-[var(--eve-border)] text-[var(--eve-dim)]',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${colors[level] || colors.unknown}`}>
      {level}
    </span>
  );
}

function OpsecGauge({ score, rating }: { score: number; rating: string }) {
  const color = score >= 60 ? 'var(--eve-green)' : score >= 40 ? 'var(--eve-yellow)' : 'var(--eve-red)';
  return (
    <div className="flex items-center gap-3">
      <div className="relative w-20 h-20">
        <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
          <circle cx="18" cy="18" r="15.9" fill="none" stroke="var(--eve-border)" strokeWidth="3" />
          <circle
            cx="18" cy="18" r="15.9" fill="none" stroke={color} strokeWidth="3"
            strokeDasharray={`${score} ${100 - score}`} strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center text-lg font-bold" style={{ color }}>
          {score}
        </div>
      </div>
      <div>
        <div className="text-sm font-bold" style={{ color }}>{rating}</div>
        <div className="text-xs text-[var(--eve-dim)]">OPSEC</div>
      </div>
    </div>
  );
}

function StatBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="mb-2">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-[var(--eve-dim)]">{label}</span>
        <span>{value}</span>
      </div>
      <div className="h-1.5 bg-[var(--eve-border)] rounded-full">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function HourChart({ peakHour, pct }: { peakHour: string; pct: number }) {
  return (
    <div className="text-sm">
      <span className="text-[var(--eve-dim)]">Peak: </span>
      <span className="font-bold text-[var(--eve-green)]">{peakHour}</span>
      <span className="text-[var(--eve-dim)]"> ({pct}%)</span>
    </div>
  );
}

export function FingerprintCard({ fp }: { fp: Fingerprint }) {
  return (
    <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <div className="text-xs text-[var(--eve-green)] uppercase tracking-wider mb-1">
            {fp.entity_type} profile
          </div>
          <h2 className="text-xl font-bold">{fp.entity_id.slice(0, 24)}</h2>
          <div className="text-xs text-[var(--eve-dim)] mt-1">{fp.event_count} events analyzed</div>
        </div>
        <div className="flex items-center gap-3">
          <ThreatBadge level={fp.threat.threat_level} />
          <OpsecGauge score={fp.opsec_score} rating={fp.opsec_rating} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Temporal */}
        <div className="space-y-3">
          <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
            Activity Pattern
          </h3>
          <HourChart peakHour={fp.temporal.peak_hour} pct={fp.temporal.peak_hour_pct} />
          <StatBar label="Active Hours" value={fp.temporal.active_hours} max={24} color="var(--eve-blue)" />
          <StatBar label="Entropy" value={fp.temporal.entropy} max={4.58} color="var(--eve-green)" />
          <div className="text-xs text-[var(--eve-dim)]">{fp.temporal.predictability}</div>
        </div>

        {/* Route */}
        <div className="space-y-3">
          <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
            Movement
          </h3>
          <div className="text-sm">
            <span className="text-[var(--eve-dim)]">Top gate: </span>
            <span className="font-mono">{fp.route.top_gate || 'N/A'}</span>
            <span className="text-[var(--eve-dim)]"> ({fp.route.top_gate_pct}%)</span>
          </div>
          <StatBar label="Unique Gates" value={fp.route.unique_gates} max={20} color="var(--eve-blue)" />
          <StatBar label="Unique Systems" value={fp.route.unique_systems} max={10} color="var(--eve-yellow)" />
          <StatBar label="Route Entropy" value={fp.route.route_entropy} max={4.0} color="var(--eve-green)" />
          <div className="text-xs text-[var(--eve-dim)]">{fp.route.predictability}</div>
        </div>

        {/* Social + Threat */}
        <div className="space-y-3">
          <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
            Intel
          </h3>
          {fp.entity_type === 'character' && (
            <>
              <StatBar label="Associates" value={fp.social.unique_associates} max={20} color="var(--eve-blue)" />
              <StatBar label="Solo Ratio" value={fp.social.solo_ratio} max={100} color="var(--eve-yellow)" />
              {fp.social.top_5_associates.length > 0 && (
                <div className="text-xs space-y-1">
                  <div className="text-[var(--eve-dim)]">Top associates:</div>
                  {fp.social.top_5_associates.slice(0, 3).map((a) => (
                    <div key={a.id} className="flex justify-between font-mono">
                      <span>{a.id}</span>
                      <span className="text-[var(--eve-dim)]">{a.count}x</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
          <div className="border-t border-[var(--eve-border)] pt-2 mt-2">
            <div className="text-sm">
              <span className="text-[var(--eve-dim)]">K/D: </span>
              <span className={fp.threat.kill_ratio > 0.5 ? 'text-[var(--eve-red)]' : ''}>
                {fp.threat.kill_ratio.toFixed(2)}
              </span>
            </div>
            <div className="text-sm">
              <span className="text-[var(--eve-dim)]">Kills/day: </span>
              <span>{fp.threat.kills_per_day.toFixed(1)}</span>
            </div>
            <div className="text-sm">
              <span className="text-[var(--eve-dim)]">Combat zones: </span>
              <span>{fp.threat.combat_zones}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
