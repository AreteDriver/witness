import { useState } from 'react';
import { api, Fingerprint } from './api';
import { SearchBar } from './components/SearchBar';
import { FingerprintCard } from './components/FingerprintCard';
import { StoryFeed } from './components/StoryFeed';
import { Leaderboard } from './components/Leaderboard';
import { HealthBanner } from './components/HealthBanner';

function App() {
  const [fingerprint, setFingerprint] = useState<Fingerprint | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadEntity = async (entityId: string) => {
    setLoading(true);
    setError('');
    try {
      const fp = await api.fingerprint(entityId);
      setFingerprint(fp);
    } catch {
      setError(`Entity not found: ${entityId}`);
      setFingerprint(null);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-[var(--eve-border)] px-6 py-4">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold tracking-wider">
              <span className="text-[var(--eve-green)]">WITNESS</span>
              <span className="text-[var(--eve-dim)] text-sm ml-2">The Living Memory</span>
            </h1>
          </div>
          <HealthBanner />
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Search */}
        <div className="max-w-xl">
          <SearchBar onSelect={loadEntity} />
        </div>

        {/* Error */}
        {error && (
          <div className="text-[var(--eve-red)] text-sm bg-red-900/20 border border-red-900/40 rounded px-4 py-2">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && <div className="text-[var(--eve-dim)]">Analyzing...</div>}

        {/* Fingerprint */}
        {fingerprint && !loading && <FingerprintCard fp={fingerprint} />}

        {/* Bottom panels */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <StoryFeed />
          <Leaderboard onSelect={loadEntity} />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--eve-border)] px-6 py-4 mt-12">
        <div className="max-w-7xl mx-auto text-center text-xs text-[var(--eve-dim)]">
          Witness — Chain Archaeology + Oracle Intelligence — EVE Frontier Hackathon 2026
        </div>
      </footer>
    </div>
  );
}

export default App;
