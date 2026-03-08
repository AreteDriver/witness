import { useState } from 'react';
import { api } from './api';
import type { Fingerprint } from './api';
import { SearchBar } from './components/SearchBar';
import { FingerprintCard } from './components/FingerprintCard';
import { ActivityHeatmap } from './components/ActivityHeatmap';
import { EntityTimeline } from './components/EntityTimeline';
import { NarrativePanel } from './components/NarrativePanel';
import { CompareView } from './components/CompareView';
import { StoryFeed } from './components/StoryFeed';
import { Leaderboard } from './components/Leaderboard';
import { HealthBanner } from './components/HealthBanner';
import { KillGraph } from './components/KillGraph';
import { HotzoneMap } from './components/HotzoneMap';
import { StreakTracker } from './components/StreakTracker';
import { CorpIntel } from './components/CorpIntel';

type Tab = 'intel' | 'tactical' | 'compare' | 'feed';

function App() {
  const [fingerprint, setFingerprint] = useState<Fingerprint | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<Tab>('intel');
  const [selectedEntity, setSelectedEntity] = useState('');

  const loadEntity = async (entityId: string) => {
    setLoading(true);
    setError('');
    setSelectedEntity(entityId);
    setActiveTab('intel');
    try {
      const fp = await api.fingerprint(entityId);
      setFingerprint(fp);
    } catch {
      setError(`Entity not found: ${entityId}`);
      setFingerprint(null);
    }
    setLoading(false);
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: 'intel', label: 'Intelligence' },
    { key: 'tactical', label: 'Tactical' },
    { key: 'compare', label: 'Compare' },
    { key: 'feed', label: 'Feed & Rankings' },
  ];

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

        {/* Tabs */}
        <div className="flex gap-1 border-b border-[var(--eve-border)]">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-bold transition-colors ${
                activeTab === tab.key
                  ? 'text-[var(--eve-green)] border-b-2 border-[var(--eve-green)]'
                  : 'text-[var(--eve-dim)] hover:text-[var(--eve-text)]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div className="text-[var(--eve-red)] text-sm bg-red-900/20 border border-red-900/40 rounded px-4 py-2">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && <div className="text-[var(--eve-dim)]">Analyzing...</div>}

        {/* Tab Content */}
        {activeTab === 'intel' && (
          <div className="space-y-6">
            {fingerprint && !loading && (
              <>
                <FingerprintCard fp={fingerprint} />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 space-y-4">
                    <ActivityHeatmap entityId={selectedEntity} />
                    <EntityTimeline entityId={selectedEntity} />
                  </div>
                  <NarrativePanel entityId={selectedEntity} />
                </div>
              </>
            )}
            {!fingerprint && !loading && !error && (
              <div className="text-center py-12 text-[var(--eve-dim)]">
                Search for an entity above to view their behavioral profile.
              </div>
            )}
          </div>
        )}

        {activeTab === 'tactical' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-6">
              <KillGraph entityId={selectedEntity || undefined} onSelect={loadEntity} />
              <CorpIntel />
            </div>
            <div className="space-y-6">
              <HotzoneMap />
              <StreakTracker entityId={selectedEntity || undefined} onSelect={loadEntity} />
            </div>
          </div>
        )}

        {activeTab === 'compare' && (
          <CompareView initialEntity={selectedEntity} onSelect={loadEntity} />
        )}

        {activeTab === 'feed' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <StoryFeed />
            <Leaderboard onSelect={loadEntity} />
          </div>
        )}
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
