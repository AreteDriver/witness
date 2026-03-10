import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('../api', () => ({
  api: {
    cycle: vi.fn(),
    orbitalZones: vi.fn(),
    zoneHistory: vi.fn(),
    scanFeed: vi.fn(),
    clones: vi.fn(),
    cloneQueue: vi.fn(),
    crowns: vi.fn(),
    crownRoster: vi.fn(),
  },
}));

import { api } from '../api';

const mockCycle = vi.mocked(api.cycle);
const mockOrbitalZones = vi.mocked(api.orbitalZones);
const mockScanFeed = vi.mocked(api.scanFeed);
const mockClones = vi.mocked(api.clones);
const mockCloneQueue = vi.mocked(api.cloneQueue);
const mockCrowns = vi.mocked(api.crowns);
const mockCrownRoster = vi.mocked(api.crownRoster);

import { CycleBanner } from '../components/CycleBanner';
import { OrbitalZones } from '../components/OrbitalZones';
import { VoidScanFeed } from '../components/VoidScanFeed';
import { CloneStatus } from '../components/CloneStatus';
import { CrownRoster } from '../components/CrownRoster';

beforeEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// CycleBanner
// ---------------------------------------------------------------------------
describe('CycleBanner', () => {
  it('shows cycle info when API succeeds', async () => {
    mockCycle.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: { number: 5, name: 'Shroud of Fear', reset_at: 1741651200, days_elapsed: 3 },
    });
    render(<CycleBanner />);
    await waitFor(() => {
      expect(screen.getByText('CYCLE 5')).toBeInTheDocument();
    });
    expect(screen.getByText('SHROUD OF FEAR')).toBeInTheDocument();
    expect(screen.getByText('DAY 3')).toBeInTheDocument();
  });

  it('shows static fallback when API fails', async () => {
    mockCycle.mockRejectedValue(new Error('fail'));
    render(<CycleBanner />);
    await waitFor(() => {
      expect(screen.getByText('CYCLE 5')).toBeInTheDocument();
    });
    expect(screen.getByText('SHROUD OF FEAR')).toBeInTheDocument();
    // No DAY element in fallback
    expect(screen.queryByText(/DAY/)).not.toBeInTheDocument();
  });

  it('returns null while loading', () => {
    // Never resolve — keep in loading state
    mockCycle.mockReturnValue(new Promise(() => {}));
    const { container } = render(<CycleBanner />);
    expect(container.innerHTML).toBe('');
  });
});

// ---------------------------------------------------------------------------
// OrbitalZones
// ---------------------------------------------------------------------------
describe('OrbitalZones', () => {
  it('renders zone list on success', async () => {
    mockOrbitalZones.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: [
        {
          zone_id: 'z-1',
          name: 'Alpha Sector',
          solar_system_id: 'sys-001',
          feral_ai_tier: 1,
          threat_level: 'ACTIVE',
          last_scanned: null,
          stale: false,
        },
      ],
    });
    render(<OrbitalZones />);
    await waitFor(() => {
      expect(screen.getByText('Alpha Sector')).toBeInTheDocument();
    });
    expect(screen.getAllByText('ACTIVE').length).toBeGreaterThanOrEqual(1);
  });

  it('shows AI EVOLVED badge when evolved zones exist', async () => {
    mockOrbitalZones.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: [
        {
          zone_id: 'z-1',
          name: 'Beta Sector',
          solar_system_id: 'sys-002',
          feral_ai_tier: 3,
          threat_level: 'EVOLVED',
          last_scanned: null,
          stale: false,
        },
        {
          zone_id: 'z-2',
          name: 'Gamma Sector',
          solar_system_id: 'sys-003',
          feral_ai_tier: 2,
          threat_level: 'ACTIVE',
          last_scanned: null,
          stale: false,
        },
      ],
    });
    render(<OrbitalZones />);
    await waitFor(() => {
      expect(screen.getByText('2 AI EVOLVED')).toBeInTheDocument();
    });
  });

  it('shows error + retry on API failure', async () => {
    mockOrbitalZones.mockRejectedValue(new Error('fail'));
    render(<OrbitalZones />);
    await waitFor(() => {
      expect(screen.getByText(/Failed to load orbital zones/)).toBeInTheDocument();
    });
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('filter buttons render', async () => {
    mockOrbitalZones.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: [],
    });
    render(<OrbitalZones />);
    await waitFor(() => {
      expect(screen.getByText('ALL')).toBeInTheDocument();
    });
    expect(screen.getByText('DORMANT')).toBeInTheDocument();
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// VoidScanFeed
// ---------------------------------------------------------------------------
describe('VoidScanFeed', () => {
  it('renders scan list on success', async () => {
    mockScanFeed.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: [
        {
          scan_id: 's-1',
          zone_id: 'z-1',
          scanner_id: 'char-1',
          scanner_name: 'PilotAlpha',
          result_type: 'CLEAR',
          scanned_at: Math.floor(Date.now() / 1000) - 120,
        },
      ],
    });
    render(<VoidScanFeed />);
    await waitFor(() => {
      expect(screen.getByText('CLEAR')).toBeInTheDocument();
    });
    expect(screen.getByText('z-1')).toBeInTheDocument();
    expect(screen.getByText('by PilotAlpha')).toBeInTheDocument();
  });

  it('shows hostile warning banner when hostile scans exist', async () => {
    mockScanFeed.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: [
        {
          scan_id: 's-1',
          zone_id: 'z-1',
          scanner_id: 'char-1',
          scanner_name: 'PilotAlpha',
          result_type: 'HOSTILE',
          scanned_at: Math.floor(Date.now() / 1000) - 60,
          zone_hostile_recent: true,
        },
      ],
    });
    render(<VoidScanFeed />);
    await waitFor(() => {
      expect(screen.getByText(/SCAN BEFORE YOU MOVE/)).toBeInTheDocument();
    });
    expect(screen.getByText(/1 zone\(s\) with recent hostile activity/)).toBeInTheDocument();
  });

  it('shows error + retry on first load failure', async () => {
    mockScanFeed.mockRejectedValue(new Error('fail'));
    render(<VoidScanFeed />);
    await waitFor(() => {
      expect(screen.getByText(/Failed to load scan feed/)).toBeInTheDocument();
    });
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// CloneStatus
// ---------------------------------------------------------------------------
describe('CloneStatus', () => {
  it('renders active clones on success', async () => {
    mockClones.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: [
        {
          clone_id: 'c-1',
          owner_id: 'owner-1',
          owner_name: 'PilotBeta',
          blueprint_id: 'bp-1',
          status: 'active',
          location_zone_id: 'z-1',
          manufactured_at: 1741600000,
        },
      ],
    });
    mockCloneQueue.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: [],
    });
    render(<CloneStatus />);
    await waitFor(() => {
      expect(screen.getByText('PilotBeta')).toBeInTheDocument();
    });
    expect(screen.getByText('1 active')).toBeInTheDocument();
  });

  it('shows LOW CLONE RESERVE alert when below threshold', async () => {
    // threshold is 5, provide 2 clones
    mockClones.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: [
        {
          clone_id: 'c-1',
          owner_id: 'o-1',
          owner_name: 'Pilot1',
          blueprint_id: 'bp-1',
          status: 'active',
          location_zone_id: 'z-1',
          manufactured_at: 1741600000,
        },
        {
          clone_id: 'c-2',
          owner_id: 'o-2',
          owner_name: 'Pilot2',
          blueprint_id: 'bp-2',
          status: 'active',
          location_zone_id: 'z-2',
          manufactured_at: 1741600000,
        },
      ],
    });
    mockCloneQueue.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: [],
    });
    render(<CloneStatus />);
    await waitFor(() => {
      expect(screen.getByText(/LOW CLONE RESERVE/)).toBeInTheDocument();
    });
  });

  it('shows error + retry on API failure', async () => {
    mockClones.mockRejectedValue(new Error('fail'));
    mockCloneQueue.mockRejectedValue(new Error('fail'));
    render(<CloneStatus />);
    await waitFor(() => {
      expect(screen.getByText(/Failed to load clone status/)).toBeInTheDocument();
    });
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// CrownRoster
// ---------------------------------------------------------------------------
describe('CrownRoster', () => {
  it('renders crown list on success', async () => {
    mockCrowns.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: [
        {
          crown_id: 'cr-1',
          character_id: 'char-1',
          character_name: 'WarriorKing',
          crown_type: 'warrior',
          attributes: 'strength',
          equipped_at: 1741600000,
        },
      ],
    });
    mockCrownRoster.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: {
        distribution: [{ crown_type: 'warrior', count: 1 }],
        crowned: 1,
        total_characters: 5,
        uncrowned: 4,
      },
    });
    render(<CrownRoster />);
    await waitFor(() => {
      expect(screen.getByText('WarriorKing')).toBeInTheDocument();
    });
    expect(screen.getAllByText('warrior').length).toBeGreaterThanOrEqual(1);
  });

  it('shows distribution bars', async () => {
    mockCrowns.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: [
        {
          crown_id: 'cr-1',
          character_id: 'char-1',
          character_name: 'WarriorKing',
          crown_type: 'warrior',
          attributes: 'strength',
          equipped_at: 1741600000,
        },
      ],
    });
    mockCrownRoster.mockResolvedValue({
      cycle: 5,
      reset_at: 1741651200,
      data: {
        distribution: [
          { crown_type: 'warrior', count: 3 },
          { crown_type: 'merchant', count: 2 },
        ],
        crowned: 5,
        total_characters: 10,
        uncrowned: 5,
      },
    });
    render(<CrownRoster />);
    await waitFor(() => {
      expect(screen.getByText('5 crowned')).toBeInTheDocument();
    });
    expect(screen.getByText('5 unidentified')).toBeInTheDocument();
    // Distribution entries render with counts
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('shows error + retry on API failure', async () => {
    mockCrowns.mockRejectedValue(new Error('fail'));
    mockCrownRoster.mockRejectedValue(new Error('fail'));
    render(<CrownRoster />);
    await waitFor(() => {
      expect(screen.getByText(/Failed to load crown roster/)).toBeInTheDocument();
    });
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });
});
