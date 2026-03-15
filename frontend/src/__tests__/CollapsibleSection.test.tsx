import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CollapsibleSection } from "../components/CollapsibleSection";

// Mock useIsMobile — controlled per test
const mockUseIsMobile = vi.fn();
vi.mock("../hooks/useIsMobile", () => ({
  useIsMobile: () => mockUseIsMobile(),
}));

beforeEach(() => {
  mockUseIsMobile.mockReset();
});

describe("CollapsibleSection", () => {
  it("renders children directly on desktop", () => {
    mockUseIsMobile.mockReturnValue(false);

    render(
      <CollapsibleSection title="Test Section">
        <div data-testid="child-content">Hello</div>
      </CollapsibleSection>
    );

    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    // No toggle button on desktop — children rendered directly
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows toggle button on mobile", () => {
    mockUseIsMobile.mockReturnValue(true);

    render(
      <CollapsibleSection title="Kill Network">
        <div data-testid="child-content">Graph</div>
      </CollapsibleSection>
    );

    expect(screen.getByRole("button", { name: /Kill Network/ })).toBeInTheDocument();
  });

  it("toggles content visibility on click (mobile)", async () => {
    mockUseIsMobile.mockReturnValue(true);
    const user = userEvent.setup();

    render(
      <CollapsibleSection title="Corp Wars" defaultOpen={true}>
        <div data-testid="child-content">Content</div>
      </CollapsibleSection>
    );

    // defaultOpen=true, so content is visible
    expect(screen.getByTestId("child-content")).toBeInTheDocument();

    // Click to collapse
    await user.click(screen.getByRole("button", { name: /Corp Wars/ }));
    expect(screen.queryByTestId("child-content")).not.toBeInTheDocument();

    // Click to expand
    await user.click(screen.getByRole("button", { name: /Corp Wars/ }));
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
  });
});
