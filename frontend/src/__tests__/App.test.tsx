import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import App from "../App";
import { AuthProvider } from "../contexts/AuthContext";

// Mock @mysten/dapp-kit — AuthProvider uses its hooks
vi.mock("@mysten/dapp-kit", () => ({
  useCurrentAccount: () => null,
  useDisconnectWallet: () => ({ mutate: vi.fn() }),
  useSignPersonalMessage: () => ({ mutateAsync: vi.fn() }),
}));

// Mock the event stream hook with capturable handlers
let mockEventHandlers: Record<string, (e: { data: Record<string, unknown> }) => void> = {};
let mockConnected = false;
vi.mock("../hooks/useEventStream", () => ({
  useEventStream: (handlers: Record<string, (e: { data: Record<string, unknown> }) => void>) => {
    mockEventHandlers = handlers;
    return { connected: mockConnected, lastEvent: null };
  },
}));

// Mock the api module
vi.mock("../api", () => ({
  api: {
    fingerprint: vi.fn(),
    entity: vi.fn(),
    search: vi.fn(),
    subscription: vi.fn(),
    walletMe: vi.fn(),
    walletChallenge: vi.fn(),
    walletConnect: vi.fn(),
    walletDisconnect: vi.fn(),
  },
}));

import { api } from "../api";
const mockApi = vi.mocked(api);

// Mock all child components that make API calls
vi.mock("../components/HealthBanner", () => ({
  HealthBanner: () => <div data-testid="health-banner">HealthBanner</div>,
}));
vi.mock("../components/WalletConnect", () => ({
  WalletConnect: () => <div data-testid="wallet-connect">WalletConnect</div>,
}));
vi.mock("../components/SearchBar", () => ({
  SearchBar: ({ onSelect }: { onSelect: (id: string) => void }) => (
    <input
      data-testid="search-bar"
      placeholder="Search entities..."
      onChange={(e) => {
        if (e.target.value === "trigger") onSelect("entity-1");
      }}
    />
  ),
}));
vi.mock("../components/FingerprintCard", () => ({
  FingerprintCard: () => <div data-testid="fingerprint-card">FingerprintCard</div>,
}));
vi.mock("../components/ActivityHeatmap", () => ({
  ActivityHeatmap: () => <div>ActivityHeatmap</div>,
}));
vi.mock("../components/EntityTimeline", () => ({
  EntityTimeline: () => <div>EntityTimeline</div>,
}));
vi.mock("../components/NarrativePanel", () => ({
  NarrativePanel: () => <div>NarrativePanel</div>,
}));
vi.mock("../components/CompareView", () => ({
  CompareView: () => <div data-testid="compare-view">CompareView</div>,
}));
vi.mock("../components/StoryFeed", () => ({
  StoryFeed: () => <div>StoryFeed</div>,
}));
vi.mock("../components/Leaderboard", () => ({
  Leaderboard: () => <div>Leaderboard</div>,
}));
vi.mock("../components/KillGraph", () => ({
  KillGraph: () => <div>KillGraph</div>,
}));
vi.mock("../components/HotzoneMap", () => ({
  HotzoneMap: () => <div>HotzoneMap</div>,
}));
vi.mock("../components/StreakTracker", () => ({
  StreakTracker: () => <div>StreakTracker</div>,
}));
vi.mock("../components/CorpIntel", () => ({
  CorpIntel: () => <div>CorpIntel</div>,
}));
vi.mock("../components/ReputationBadge", () => ({
  ReputationBadge: () => <div>ReputationBadge</div>,
}));
vi.mock("../components/AssemblyMap", () => ({
  AssemblyMap: () => <div>AssemblyMap</div>,
}));
vi.mock("../components/AccountPage", () => ({
  AccountPage: () => <div data-testid="account-page">AccountPage</div>,
}));
vi.mock("../components/EntityPage", () => ({
  EntityPage: () => <div data-testid="entity-page">EntityPage</div>,
}));
vi.mock("../components/CorpPage", () => ({
  CorpPage: () => <div data-testid="corp-page">CorpPage</div>,
}));
vi.mock("../components/TierGate", () => ({
  TierGate: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("../components/ErrorBoundary", () => ({
  ErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("../components/CycleBanner", () => ({
  CycleBanner: () => <div data-testid="cycle-banner">CycleBanner</div>,
}));
vi.mock("../components/OrbitalZones", () => ({
  OrbitalZones: () => <div data-testid="orbital-zones">OrbitalZones</div>,
}));
vi.mock("../components/VoidScanFeed", () => ({
  VoidScanFeed: () => <div>VoidScanFeed</div>,
}));
vi.mock("../components/CloneStatus", () => ({
  CloneStatus: () => <div>CloneStatus</div>,
}));
vi.mock("../components/CrownRoster", () => ({
  CrownRoster: () => <div>CrownRoster</div>,
}));
vi.mock("../components/AdminAnalytics", () => ({
  AdminAnalytics: () => <div>AdminAnalytics</div>,
}));
vi.mock("../components/SystemDossier", () => ({
  SystemDossier: () => <div>SystemDossier</div>,
}));
vi.mock("../components/TitleCard", () => ({
  TitleCard: () => <div>TitleCard</div>,
}));
vi.mock("../components/AegisEcosystem", () => ({
  AegisEcosystem: () => <div data-testid="aegis-ecosystem">AegisEcosystem</div>,
}));
vi.mock("../components/NexusCard", () => ({
  NexusCard: () => <div>NexusCard</div>,
}));
vi.mock("../components/CollapsibleSection", () => ({
  CollapsibleSection: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

function renderApp(initialRoute = "/") {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  // Only clear api mock call history — don't use clearAllMocks/restoreAllMocks
  // as they destroy vi.mock() factory implementations for component mocks
  mockApi.fingerprint.mockClear();
  mockApi.entity.mockClear();
  mockApi.search.mockClear();
  mockApi.subscription.mockResolvedValue(null);
  mockApi.walletMe.mockRejectedValue(new Error("no session"));
  mockApi.walletDisconnect.mockResolvedValue(undefined as never);
});

describe("App", () => {
  it("renders without crashing", () => {
    renderApp();
    expect(document.querySelector(".min-h-screen")).toBeTruthy();
  });

  it("renders WATCHTOWER header", () => {
    renderApp();
    expect(screen.getByText("WATCHTOWER")).toBeInTheDocument();
  });

  it("renders The Living Memory subtitle", () => {
    renderApp();
    expect(screen.getByText("The Living Memory")).toBeInTheDocument();
  });

  it("renders all six tab buttons", () => {
    renderApp();
    expect(screen.getByText("Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Tactical")).toBeInTheDocument();
    expect(screen.getByText("Shroud")).toBeInTheDocument();
    expect(screen.getByText("Compare")).toBeInTheDocument();
    expect(screen.getByText("Feed & Rankings")).toBeInTheDocument();
    expect(screen.getByText("Connect")).toBeInTheDocument();
  });

  it("renders the search bar", () => {
    renderApp();
    expect(screen.getByTestId("search-bar")).toBeInTheDocument();
  });

  it("renders the footer", () => {
    renderApp();
    expect(
      screen.getByText(/Chain Archaeology.*Oracle Intelligence/)
    ).toBeInTheDocument();
  });

  it("renders health banner and wallet connect", () => {
    renderApp();
    expect(screen.getByTestId("health-banner")).toBeInTheDocument();
    expect(screen.getByTestId("wallet-connect")).toBeInTheDocument();
  });

  it("shows empty state message when no entity selected", () => {
    renderApp();
    expect(
      screen.getByText(/Search for an entity/)
    ).toBeInTheDocument();
  });

  it("switches to Compare tab on click", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByText("Compare"));
    // CompareView is lazy-loaded — wait for Suspense to resolve
    await waitFor(() => {
      expect(screen.getByTestId("compare-view")).toBeInTheDocument();
    });
  });

  it("switches to Connect/Account tab on click", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByText("Connect"));
    // AccountPage is lazy-loaded
    await waitFor(() => {
      expect(screen.getByTestId("account-page")).toBeInTheDocument();
    });
  });

  it("renders entity page at /entity/:id route", async () => {
    renderApp("/entity/char-001");
    // EntityPage is lazy-loaded
    await waitFor(() => {
      expect(screen.getByTestId("entity-page")).toBeInTheDocument();
    });
  });

  it("renders corp page at /corp/:id route", async () => {
    renderApp("/corp/corp-001");
    // CorpPage is lazy-loaded
    await waitFor(() => {
      expect(screen.getByTestId("corp-page")).toBeInTheDocument();
    });
  });

  it("shows live ticker when events arrive via SSE", async () => {
    mockConnected = true;
    renderApp();

    const { act } = await import("@testing-library/react");
    act(() => {
      mockEventHandlers.kill?.({ data: { new_count: 3 } });
    });

    expect(screen.getByText("LIVE")).toBeInTheDocument();
    expect(screen.getByText(/New kill detected/)).toBeInTheDocument();

    // Reset
    mockConnected = false;
  });
});
