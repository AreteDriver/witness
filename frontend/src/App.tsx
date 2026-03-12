import { useState } from 'react';
import { useNavigate, useLocation, Routes, Route } from 'react-router';
import { useEventStream } from './hooks/useEventStream';
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
import { ReputationBadge } from './components/ReputationBadge';
import { AssemblyMap } from './components/AssemblyMap';
import { WalletConnect } from './components/WalletConnect';
import { AccountPage } from './components/AccountPage';
import { EntityPage } from './components/EntityPage';
import { TierGate } from './components/TierGate';
import { ErrorBoundary } from './components/ErrorBoundary';
import { CycleBanner } from './components/CycleBanner';
import { OrbitalZones } from './components/OrbitalZones';
import { VoidScanFeed } from './components/VoidScanFeed';
import { CloneStatus } from './components/CloneStatus';
import { CrownRoster } from './components/CrownRoster';
import { useAuth } from './contexts/AuthContext';

type Tab = 'intel' | 'tactical' | 'c5' | 'compare' | 'feed' | 'account';

function tabFromPath(path: string): Tab {
  if (path.startsWith('/tactical')) return 'tactical';
  if (path.startsWith('/c5')) return 'c5';
  if (path.startsWith('/compare')) return 'compare';
  if (path.startsWith('/feed')) return 'feed';
  if (path.startsWith('/account')) return 'account';
  return 'intel';
}

function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  const [fingerprint, setFingerprint] = useState<Fingerprint | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedEntity, setSelectedEntity] = useState('');
  const { wallet } = useAuth();
  const [liveEvents, setLiveEvents] = useState<Array<{type: string, text: string, ts: number}>>([]);

  const { connected } = useEventStream({
    kill: (e) => {
      setLiveEvents(prev => [{type: 'kill', text: `New kill detected (${e.data.new_count || 1} kills)`, ts: Date.now()}, ...prev].slice(0, 5));
    },
    alert: (e) => {
      setLiveEvents(prev => [{type: 'alert', text: String(e.data.title || 'Alert triggered'), ts: Date.now()}, ...prev].slice(0, 5));
    },
    status: (_e) => {
      setLiveEvents(prev => [{type: 'status', text: 'System update received', ts: Date.now()}, ...prev].slice(0, 5));
    },
  });

  const activeTab = tabFromPath(location.pathname);

  const loadEntity = async (entityId: string) => {
    navigate(`/entity/${entityId}`);
  };

  const loadEntityInline = async (entityId: string) => {
    setLoading(true);
    setError('');
    setSelectedEntity(entityId);
    try {
      const fp = await api.fingerprint(entityId);
      setFingerprint(fp);
    } catch {
      setError(`Entity not found: ${entityId}`);
      setFingerprint(null);
    }
    setLoading(false);
  };

  const setTab = (tab: Tab) => {
    const paths: Record<Tab, string> = {
      intel: '/',
      tactical: '/tactical',
      c5: '/c5',
      compare: '/compare',
      feed: '/feed',
      account: '/account',
    };
    navigate(paths[tab]);
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: 'intel', label: 'Intelligence' },
    { key: 'tactical', label: 'Tactical' },
    { key: 'c5', label: 'Shroud' },
    { key: 'compare', label: 'Compare' },
    { key: 'feed', label: 'Feed & Rankings' },
    { key: 'account', label: wallet ? 'Account' : 'Connect' },
  ];

  return (
    <>
      {/* Search (hidden on account tab) */}
      {activeTab !== 'account' && (
        <div className="max-w-xl">
          <SearchBar onSelect={loadEntity} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--eve-border)] overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setTab(tab.key)}
            className={`px-3 sm:px-4 py-2 text-xs sm:text-sm font-bold transition-colors whitespace-nowrap ${
              activeTab === tab.key
                ? 'text-[var(--eve-green)] border-b-2 border-[var(--eve-green)]'
                : 'text-[var(--eve-dim)] hover:text-[var(--eve-text)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Live Feed */}
      {liveEvents.length > 0 && (
        <div className="text-xs text-[var(--eve-dim)] space-y-0.5 bg-[var(--eve-surface)] rounded px-3 py-2 border border-[var(--eve-border)]">
          <div className="flex items-center gap-2 mb-1">
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-[var(--eve-green)]' : 'bg-[var(--eve-red)]'}`} />
            <span className="text-[var(--eve-green)] font-bold">LIVE</span>
          </div>
          {liveEvents.map((ev, i) => (
            <div key={`${ev.ts}-${i}`} className="flex gap-2">
              <span className="text-[var(--eve-dim)]">{new Date(ev.ts).toLocaleTimeString()}</span>
              <span className={ev.type === 'kill' ? 'text-[var(--eve-red)]' : ev.type === 'alert' ? 'text-[var(--eve-yellow)]' : 'text-[var(--eve-text)]'}>
                {ev.text}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-[var(--eve-red)] text-sm bg-red-900/20 border border-red-900/40 rounded px-4 py-2">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-[var(--eve-dim)]">
          <span className="pulse-green text-[var(--eve-green)]">///</span>
          Analyzing entity...
        </div>
      )}

      {/* Tab Content */}
      {activeTab === 'intel' && (
        <div className="space-y-6">
          {fingerprint && !loading && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-2">
                  <ErrorBoundary>
                    <TierGate requiredTier={1} featureName="Behavioral Fingerprints">
                      <FingerprintCard fp={fingerprint} />
                    </TierGate>
                  </ErrorBoundary>
                </div>
                <ErrorBoundary>
                  <TierGate requiredTier={1} featureName="Reputation Score">
                    <ReputationBadge entityId={selectedEntity} />
                  </TierGate>
                </ErrorBoundary>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <ErrorBoundary>
                  <div className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded-lg p-4 space-y-4">
                    <ActivityHeatmap entityId={selectedEntity} />
                    <EntityTimeline entityId={selectedEntity} />
                  </div>
                </ErrorBoundary>
                <ErrorBoundary>
                  <TierGate requiredTier={2} featureName="AI Narrative">
                    <NarrativePanel entityId={selectedEntity} />
                  </TierGate>
                </ErrorBoundary>
              </div>
            </>
          )}
          {!fingerprint && !loading && !error && (
            <div className="text-center py-16 space-y-4">
              <div className="text-4xl text-[var(--eve-green)] pulse-green">///</div>
              <div className="text-[var(--eve-dim)]">
                Search for an entity to view their behavioral fingerprint.
              </div>
              <div className="text-xs text-[var(--eve-dim)]">
                Try "Asterix" or "Kali" to see the deadliest pilots on the frontier.
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'tactical' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-6">
            <ErrorBoundary>
              <TierGate requiredTier={3} featureName="Kill Graph">
                <KillGraph entityId={selectedEntity || undefined} onSelect={loadEntityInline} />
              </TierGate>
            </ErrorBoundary>
            <ErrorBoundary>
              <CorpIntel />
            </ErrorBoundary>
          </div>
          <div className="space-y-6">
            <ErrorBoundary>
              <TierGate requiredTier={1} featureName="Hotzones">
                <HotzoneMap />
              </TierGate>
            </ErrorBoundary>
            <ErrorBoundary>
              <StreakTracker entityId={selectedEntity || undefined} onSelect={loadEntityInline} />
            </ErrorBoundary>
            <ErrorBoundary>
              <AssemblyMap />
            </ErrorBoundary>
          </div>
        </div>
      )}

      {activeTab === 'compare' && (
        <ErrorBoundary>
          <TierGate requiredTier={1} featureName="Fingerprint Compare">
            <CompareView initialEntity={selectedEntity} onSelect={loadEntityInline} />
          </TierGate>
        </ErrorBoundary>
      )}

      {activeTab === 'c5' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-6">
            <ErrorBoundary>
              <OrbitalZones />
            </ErrorBoundary>
            <ErrorBoundary>
              <CloneStatus />
            </ErrorBoundary>
          </div>
          <div className="space-y-6">
            <ErrorBoundary>
              <VoidScanFeed />
            </ErrorBoundary>
            <ErrorBoundary>
              <CrownRoster />
            </ErrorBoundary>
          </div>
        </div>
      )}

      {activeTab === 'feed' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <ErrorBoundary>
            <StoryFeed />
          </ErrorBoundary>
          <ErrorBoundary>
            <Leaderboard onSelect={loadEntity} />
          </ErrorBoundary>
        </div>
      )}

      {activeTab === 'account' && (
        <ErrorBoundary>
          <AccountPage />
        </ErrorBoundary>
      )}
    </>
  );
}

export default function App() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen">
      {/* Cycle Banner */}
      <CycleBanner />

      {/* Header */}
      <header className="border-b border-[var(--eve-border)] px-4 sm:px-6 py-3 sm:py-4">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div
            className="cursor-pointer"
            onClick={() => navigate('/')}
          >
            <h1 className="text-lg sm:text-xl font-bold tracking-wider">
              <span className="text-[var(--eve-green)]">WATCHTOWER</span>
              <span className="text-[var(--eve-dim)] text-xs sm:text-sm ml-2 hidden sm:inline">
                The Living Memory
              </span>
            </h1>
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            <WalletConnect />
            <HealthBanner />
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-4 sm:py-6 space-y-6">
        <Routes>
          <Route path="/entity/:entityId" element={
            <ErrorBoundary>
              <EntityPage />
            </ErrorBoundary>
          } />
          <Route path="*" element={<Dashboard />} />
        </Routes>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--eve-border)] px-4 sm:px-6 py-4 mt-12">
        <div className="max-w-7xl mx-auto text-center text-xs text-[var(--eve-dim)]">
          WatchTower — Chain Archaeology + Oracle Intelligence — EVE Frontier Hackathon 2026
        </div>
      </footer>
    </div>
  );
}
