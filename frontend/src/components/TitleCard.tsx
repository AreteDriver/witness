import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { api } from '../api';
import type { Dossier } from '../api';

export function TitleCard() {
  const { entityId, title } = useParams<{ entityId: string; title: string }>();
  const navigate = useNavigate();
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!entityId) return;
    api.entity(entityId)
      .then(setDossier)
      .catch(() => setDossier(null))
      .finally(() => setLoading(false));
  }, [entityId]);

  if (!entityId || !title) {
    navigate('/');
    return null;
  }

  const decodedTitle = decodeURIComponent(title);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-[var(--eve-dim)]">
          <span className="pulse-green text-[var(--eve-green)]">///</span> Loading...
        </div>
      </div>
    );
  }

  const displayName = dossier?.display_name || entityId.slice(0, 12);
  const hasTitle = dossier?.titles?.includes(decodedTitle);

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="max-w-md w-full space-y-6">
        {/* Title card */}
        <div className="bg-[var(--eve-surface)] border-2 border-[var(--eve-orange)]/40 rounded-lg p-8 text-center space-y-4 relative overflow-hidden">
          {/* Background pattern */}
          <div className="absolute inset-0 opacity-5">
            <div className="absolute inset-0" style={{
              backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 20px, var(--eve-orange) 20px, var(--eve-orange) 21px)',
            }} />
          </div>

          <div className="relative">
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[var(--eve-dim)]">
              WatchTower Designation
            </div>

            <div className="mt-4 font-mono text-2xl uppercase tracking-wider text-[var(--eve-orange)] font-bold">
              {decodedTitle}
            </div>

            <div className="mt-4 w-16 h-px bg-[var(--eve-orange)]/30 mx-auto" />

            <div className="mt-4">
              <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--eve-dim)]">
                Earned by
              </div>
              <button
                onClick={() => navigate(`/entity/${entityId}`)}
                className="text-[var(--eve-green)] font-bold text-lg hover:underline mt-1"
              >
                {displayName}
              </button>
            </div>

            {dossier && (
              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="font-mono text-[10px] text-[var(--eve-dim)]">KILLS</div>
                  <div className="text-sm font-bold text-[var(--eve-red)]">{dossier.kill_count}</div>
                </div>
                <div>
                  <div className="font-mono text-[10px] text-[var(--eve-dim)]">DEATHS</div>
                  <div className="text-sm font-bold text-[var(--eve-text)]">{dossier.death_count}</div>
                </div>
                <div>
                  <div className="font-mono text-[10px] text-[var(--eve-dim)]">DANGER</div>
                  <div className={`text-sm font-bold ${
                    dossier.danger_rating === 'deadly' ? 'text-[var(--eve-red)]' :
                    dossier.danger_rating === 'dangerous' ? 'text-[var(--eve-orange)]' :
                    'text-[var(--eve-green)]'
                  }`}>{dossier.danger_rating.toUpperCase()}</div>
                </div>
              </div>
            )}

            {!hasTitle && (
              <div className="mt-4 text-[10px] text-[var(--eve-dim)] italic">
                Title not currently held by this entity
              </div>
            )}

            <div className="mt-6 font-mono text-[9px] text-[var(--eve-dim)]">
              watchtower-evefrontier.vercel.app
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-center gap-4">
          <button
            onClick={() => navigate(`/entity/${entityId}`)}
            className="text-xs text-[var(--eve-green)] hover:underline"
          >
            View Full Dossier
          </button>
          <button
            onClick={() => navigate('/')}
            className="text-xs text-[var(--eve-dim)] hover:underline"
          >
            Search
          </button>
        </div>
      </div>
    </div>
  );
}
