import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { api } from '../api';
import type { Fingerprint, Dossier } from '../api';
import { FingerprintCard } from './FingerprintCard';
import { ActivityHeatmap } from './ActivityHeatmap';
import { EntityTimeline } from './EntityTimeline';
import { NarrativePanel } from './NarrativePanel';
import { ReputationBadge } from './ReputationBadge';
import { StreakTracker } from './StreakTracker';
import { TierGate } from './TierGate';
import { ErrorBoundary } from './ErrorBoundary';

export function EntityPage() {
  const { entityId } = useParams<{ entityId: string }>();
  const navigate = useNavigate();
  const [fingerprint, setFingerprint] = useState<Fingerprint | null>(null);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!entityId) return;
    setLoading(true);
    setError('');
    Promise.all([
      api.fingerprint(entityId),
      api.entity(entityId),
    ])
      .then(([fp, dos]) => {
        setFingerprint(fp);
        setDossier(dos);
      })
      .catch(() => {
        setError(`Entity not found: ${entityId}`);
        setFingerprint(null);
        setDossier(null);
      })
      .finally(() => setLoading(false));
  }, [entityId]);

  if (!entityId) {
    navigate('/');
    return null;
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-[var(--eve-dim)] py-8">
        <span className="pulse-green text-[var(--eve-green)]">///</span>
        Analyzing entity...
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="text-[var(--eve-red)] text-sm bg-red-900/20 border border-red-900/40 rounded px-4 py-2">
          {error}
        </div>
        <button
          onClick={() => navigate('/')}
          className="text-xs text-[var(--eve-green)] hover:underline"
        >
          Back to search
        </button>
      </div>
    );
  }

  if (!fingerprint) return null;

  const displayName = dossier?.display_name || entityId;
  const titles = dossier?.titles || [];

  return (
    <div className="space-y-6">
      {/* Entity header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <button
            onClick={() => navigate('/')}
            className="text-xs text-[var(--eve-dim)] hover:text-[var(--eve-green)] mb-1"
          >
            &larr; Back
          </button>
          <h2 className="text-lg font-bold text-[var(--eve-text)]">
            <span className="text-[var(--eve-green)]">{displayName}</span>
            <span className="text-[var(--eve-dim)] text-sm ml-2">
              {fingerprint.entity_type} / {fingerprint.event_count} events
            </span>
          </h2>

          {/* Earned titles — click to share */}
          {titles.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {titles.map((title) => (
                <button
                  key={title}
                  onClick={() => navigate(`/title/${entityId}/${encodeURIComponent(title)}`)}
                  className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-sm bg-[var(--eve-orange)]/15 text-[var(--eve-orange)] border border-[var(--eve-orange)]/30 hover:bg-[var(--eve-orange)]/25 transition-colors cursor-pointer"
                  title="Click to view shareable title card"
                >
                  {title}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="text-xs text-[var(--eve-dim)]">
          OPSEC: <span className={
            fingerprint.opsec_score >= 70 ? 'text-[var(--eve-green)]' :
            fingerprint.opsec_score >= 40 ? 'text-[var(--eve-yellow,#FFCC00)]' :
            'text-[var(--eve-red)]'
          }>{fingerprint.opsec_score}/100 ({fingerprint.opsec_rating})</span>
        </div>
      </div>

      {/* Dossier summary card */}
      {dossier && (
        <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4">
          <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--eve-orange)] font-bold mb-3">
            Dossier Summary
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">Kills</div>
              <div className="text-lg font-bold text-[var(--eve-red)]">{dossier.kill_count}</div>
            </div>
            <div>
              <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">Deaths</div>
              <div className="text-lg font-bold text-[var(--eve-text)]">{dossier.death_count}</div>
            </div>
            <div>
              <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">Danger</div>
              <div className={`text-lg font-bold ${
                dossier.danger_rating === 'deadly' ? 'text-[var(--eve-red)]' :
                dossier.danger_rating === 'dangerous' ? 'text-[var(--eve-orange)]' :
                'text-[var(--eve-green)]'
              }`}>{dossier.danger_rating.toUpperCase()}</div>
            </div>
            <div>
              <div className="font-mono text-[10px] text-[var(--eve-dim)] uppercase">First Seen</div>
              <div className="text-sm text-[var(--eve-text)]">
                {new Date(dossier.first_seen * 1000).toLocaleDateString()}
              </div>
            </div>
          </div>
          {dossier.tribe_name && (
            <div className="mt-3 text-xs text-[var(--eve-dim)]">
              Tribe: <span className="text-[var(--eve-text)]">{dossier.tribe_name}</span>
              {dossier.tribe_short && <span className="ml-1 text-[var(--eve-orange)]">[{dossier.tribe_short}]</span>}
            </div>
          )}
        </div>
      )}

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <ErrorBoundary>
            <TierGate requiredTier={1} featureName="Behavioral Fingerprint">
              <FingerprintCard fp={fingerprint} />
            </TierGate>
          </ErrorBoundary>

          <ErrorBoundary>
            <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 space-y-4">
              <ActivityHeatmap entityId={entityId} />
              <EntityTimeline entityId={entityId} />
            </div>
          </ErrorBoundary>
        </div>

        <div className="space-y-6">
          <ErrorBoundary>
            <TierGate requiredTier={1} featureName="Reputation Score">
              <ReputationBadge entityId={entityId} />
            </TierGate>
          </ErrorBoundary>

          <ErrorBoundary>
            <TierGate requiredTier={2} featureName="AI Narrative">
              <NarrativePanel entityId={entityId} />
            </TierGate>
          </ErrorBoundary>

          <ErrorBoundary>
            <StreakTracker entityId={entityId} />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
}
