import { useState } from 'react';
import { api } from '../api';
import type { CompareResult } from '../api';

interface Props {
  initialEntity?: string;
  onSelect: (entityId: string) => void;
}

function SimilarityBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const color = value > 0.7 ? 'var(--eve-red)' : value > 0.4 ? 'var(--eve-yellow)' : 'var(--eve-green)';
  return (
    <div className="mb-3">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-[var(--eve-dim)]">{label}</span>
        <span style={{ color }} className="font-bold">{pct}%</span>
      </div>
      <div className="h-2 bg-[var(--eve-border)] rounded-full">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

export function CompareView({ initialEntity, onSelect }: Props) {
  const [entity1, setEntity1] = useState(initialEntity || '');
  const [entity2, setEntity2] = useState('');
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const runCompare = async () => {
    if (!entity1 || !entity2) return;
    setLoading(true);
    setError('');
    try {
      const data = await api.compare(entity1, entity2);
      setResult(data);
    } catch {
      setError('Comparison failed — check entity IDs');
    }
    setLoading(false);
  };

  return (
    <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-6 space-y-4">
      <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
        Fingerprint Comparison — Alt Detection
      </h3>

      <div className="grid grid-cols-2 gap-3">
        <input
          value={entity1}
          onChange={(e) => setEntity1(e.target.value)}
          placeholder="Entity 1 ID..."
          className="bg-[var(--eve-bg)] border border-[var(--eve-border)] rounded px-3 py-1.5 text-sm text-[var(--eve-text)] placeholder-[var(--eve-dim)] focus:border-[var(--eve-green)] focus:outline-none"
        />
        <input
          value={entity2}
          onChange={(e) => setEntity2(e.target.value)}
          placeholder="Entity 2 ID..."
          className="bg-[var(--eve-bg)] border border-[var(--eve-border)] rounded px-3 py-1.5 text-sm text-[var(--eve-text)] placeholder-[var(--eve-dim)] focus:border-[var(--eve-green)] focus:outline-none"
        />
      </div>

      <button
        onClick={runCompare}
        disabled={loading || !entity1 || !entity2}
        className="px-4 py-1.5 bg-[var(--eve-green)] text-black font-bold rounded text-sm hover:opacity-90 disabled:opacity-50"
      >
        {loading ? 'Analyzing...' : 'Compare Fingerprints'}
      </button>

      {error && <div className="text-[var(--eve-red)] text-sm">{error}</div>}

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <button onClick={() => onSelect(result.entity_1)} className="text-left text-sm text-[var(--eve-green)] hover:underline font-mono truncate">
              {result.entity_1}
            </button>
            <button onClick={() => onSelect(result.entity_2)} className="text-left text-sm text-[var(--eve-green)] hover:underline font-mono truncate">
              {result.entity_2}
            </button>
          </div>

          <SimilarityBar label="Temporal Similarity" value={result.temporal_similarity} />
          <SimilarityBar label="Route Similarity" value={result.route_similarity} />
          <SimilarityBar label="Social Similarity" value={result.social_similarity} />

          <div className="border-t border-[var(--eve-border)] pt-3">
            <SimilarityBar label="OVERALL" value={result.overall_similarity} />
          </div>

          <div className="flex gap-3">
            {result.likely_alt && (
              <span className="px-3 py-1 bg-red-900/60 text-red-300 rounded text-xs font-bold uppercase">
                Likely Alt Account
              </span>
            )}
            {result.likely_fleet_mate && (
              <span className="px-3 py-1 bg-yellow-900/60 text-yellow-300 rounded text-xs font-bold uppercase">
                Likely Fleet Mate
              </span>
            )}
            {!result.likely_alt && !result.likely_fleet_mate && result.overall_similarity < 0.3 && (
              <span className="px-3 py-1 bg-green-900/60 text-green-300 rounded text-xs font-bold uppercase">
                Distinct Entities
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
