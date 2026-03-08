import { useEffect, useState } from 'react';
import { api } from '../api';
import type { ReputationData } from '../api';

const RATING_COLORS: Record<string, string> = {
  trusted: 'var(--eve-green)',
  reputable: 'var(--eve-blue)',
  neutral: 'var(--eve-dim)',
  suspicious: 'var(--eve-orange)',
  dangerous: 'var(--eve-red)',
};

const BAR_LABELS: { key: keyof ReputationData['breakdown']; label: string }[] = [
  { key: 'combat_honor', label: 'Combat Honor' },
  { key: 'target_diversity', label: 'Target Diversity' },
  { key: 'reciprocity', label: 'Reciprocity' },
  { key: 'consistency', label: 'Consistency' },
  { key: 'community', label: 'Community' },
  { key: 'restraint', label: 'Restraint' },
];

export function ReputationBadge({ entityId }: { entityId: string }) {
  const [rep, setRep] = useState<ReputationData | null>(null);

  useEffect(() => {
    if (!entityId) return;
    api.reputation(entityId).then(setRep).catch(() => setRep(null));
  }, [entityId]);

  if (!rep) return null;

  const color = RATING_COLORS[rep.rating] || 'var(--eve-dim)';

  return (
    <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-[var(--eve-dim)] uppercase tracking-wider">
          Trust Score
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold" style={{ color }}>
            {rep.trust_score}
          </span>
          <span className="text-xs font-bold uppercase px-2 py-0.5 rounded"
            style={{ color, border: `1px solid ${color}` }}>
            {rep.rating}
          </span>
        </div>
      </div>

      {/* Score bar */}
      <div className="h-2 bg-[var(--eve-bg)] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${rep.trust_score}%`, backgroundColor: color }}
        />
      </div>

      {/* Breakdown bars */}
      <div className="space-y-2">
        {BAR_LABELS.map(({ key, label }) => (
          <div key={key} className="flex items-center gap-2 text-xs">
            <span className="w-28 text-[var(--eve-dim)]">{label}</span>
            <div className="flex-1 h-1.5 bg-[var(--eve-bg)] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${rep.breakdown[key]}%`,
                  backgroundColor: rep.breakdown[key] >= 60 ? 'var(--eve-green)' :
                    rep.breakdown[key] >= 40 ? 'var(--eve-dim)' : 'var(--eve-red)',
                }}
              />
            </div>
            <span className="w-8 text-right text-[var(--eve-dim)]">
              {rep.breakdown[key]}
            </span>
          </div>
        ))}
      </div>

      {/* Factors */}
      {rep.factors.length > 0 && (
        <div className="space-y-1">
          {rep.factors.map((f, i) => (
            <div key={i} className="text-xs text-[var(--eve-dim)] flex items-start gap-1">
              <span style={{ color }}>+</span>
              <span>{f}</span>
            </div>
          ))}
        </div>
      )}

      {/* Stats footer */}
      <div className="flex gap-4 text-xs text-[var(--eve-dim)] border-t border-[var(--eve-border)] pt-2">
        <span>{rep.stats.kills} kills</span>
        <span>{rep.stats.deaths} deaths</span>
        <span>{rep.stats.unique_victims} unique targets</span>
        <span>{rep.stats.vendettas} vendettas</span>
      </div>

      {/* Smart Assembly hint */}
      <div className="text-[10px] text-[var(--eve-dim)] opacity-60">
        Smart Assembly gate: require(trustScore &gt;= 40)
      </div>
    </div>
  );
}
