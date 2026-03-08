import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";
import { AuthProvider } from "../contexts/AuthContext";

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
vi.mock("../components/TierGate", () => ({
  TierGate: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

function renderApp() {
  return render(
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("renders WITNESS header", () => {
    renderApp();
    expect(screen.getByText("WITNESS")).toBeInTheDocument();
  });

  it("renders The Living Memory subtitle", () => {
    renderApp();
    expect(screen.getByText("The Living Memory")).toBeInTheDocument();
  });

  it("renders all five tab buttons", () => {
    renderApp();
    expect(screen.getByText("Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Tactical")).toBeInTheDocument();
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
      screen.getByText(/Search for an entity to view their behavioral fingerprint/)
    ).toBeInTheDocument();
  });

  it("switches to Compare tab on click", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByText("Compare"));
    expect(screen.getByTestId("compare-view")).toBeInTheDocument();
  });

  it("switches to Account tab on click", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByText("Connect"));
    expect(screen.getByTestId("account-page")).toBeInTheDocument();
  });
});
