import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";
import { CorpPage } from "../components/CorpPage";

// Mock the api module
vi.mock("../api", () => ({
  api: {
    corp: vi.fn(),
  },
}));

import { api } from "../api";
const mockCorp = vi.mocked(api.corp);

function renderCorpPage(corpId: string) {
  return render(
    <MemoryRouter initialEntries={[`/corp/${corpId}`]}>
      <Routes>
        <Route path="/corp/:corpId" element={<CorpPage />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockCorp.mockReset();
});

describe("CorpPage", () => {
  it("renders loading state while fetching", () => {
    // Never resolve — keeps component in loading state
    mockCorp.mockReturnValue(new Promise(() => {}));

    renderCorpPage("corp-001");
    expect(screen.getByText("Analyzing corporation...")).toBeInTheDocument();
  });

  it("shows error for invalid corp", async () => {
    mockCorp.mockRejectedValue(new Error("not found"));

    renderCorpPage("bad-corp");

    await waitFor(() => {
      expect(screen.getByText("Corporation not found: bad-corp")).toBeInTheDocument();
    });
  });

  it("renders back button on error state", async () => {
    mockCorp.mockRejectedValue(new Error("not found"));

    renderCorpPage("bad-corp");

    await waitFor(() => {
      // CorpPage uses HTML entity &larr; which renders as the left arrow character
      const backButton = screen.getByRole("button", { name: /Back/i });
      expect(backButton).toBeInTheDocument();
    });
  });
});
