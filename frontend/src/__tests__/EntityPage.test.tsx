import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";
import { EntityPage } from "../components/EntityPage";

// Mock the api module
vi.mock("../api", () => ({
  api: {
    fingerprint: vi.fn(),
    entity: vi.fn(),
  },
}));

import { api } from "../api";
const mockFingerprint = vi.mocked(api.fingerprint);
const mockEntity = vi.mocked(api.entity);

// Mock child components to isolate EntityPage
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
vi.mock("../components/ReputationBadge", () => ({
  ReputationBadge: () => <div>ReputationBadge</div>,
}));
vi.mock("../components/StreakTracker", () => ({
  StreakTracker: () => <div>StreakTracker</div>,
}));
vi.mock("../components/TierGate", () => ({
  TierGate: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("../components/ErrorBoundary", () => ({
  ErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

function renderEntityPage(entityId: string) {
  return render(
    <MemoryRouter initialEntries={[`/entity/${entityId}`]}>
      <Routes>
        <Route path="/entity/:entityId" element={<EntityPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockFingerprint.mockReset();
  mockEntity.mockReset();
});

describe("EntityPage", () => {
  it("renders loading state while fetching", () => {
    // Never resolve — keeps component in loading state
    mockFingerprint.mockReturnValue(new Promise(() => {}));
    mockEntity.mockReturnValue(new Promise(() => {}));

    renderEntityPage("char-001");
    expect(screen.getByText("Analyzing entity...")).toBeInTheDocument();
  });

  it("shows error for invalid entity", async () => {
    mockFingerprint.mockRejectedValue(new Error("not found"));
    mockEntity.mockRejectedValue(new Error("not found"));

    renderEntityPage("invalid-id");

    await waitFor(() => {
      expect(screen.getByText("Entity not found: invalid-id")).toBeInTheDocument();
    });
  });

  it("renders back button on error state", async () => {
    mockFingerprint.mockRejectedValue(new Error("not found"));
    mockEntity.mockRejectedValue(new Error("not found"));

    renderEntityPage("invalid-id");

    await waitFor(() => {
      expect(screen.getByText("Back to search")).toBeInTheDocument();
    });
  });
});
