import { describe, it, expect, vi, beforeEach } from "vitest";
import { api } from "../api";

const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockReset();
  localStorage.clear();
});

function mockOk(data: unknown) {
  mockFetch.mockResolvedValueOnce({
    ok: true,
    json: () => Promise.resolve(data),
  });
}

function mockError(status: number) {
  mockFetch.mockResolvedValueOnce({ ok: false, status });
}

describe("api", () => {
  it("health calls /api/health", async () => {
    mockOk({ status: "ok", tables: { events: 100 } });
    const result = await api.health();
    expect(mockFetch).toHaveBeenCalledWith("/api/health", expect.objectContaining({ headers: {} }));
    expect(result.status).toBe("ok");
  });

  it("search encodes query parameter", async () => {
    mockOk({ results: [] });
    await api.search("test entity");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/search?q=test%20entity",
      expect.objectContaining({})
    );
  });

  it("fingerprint calls correct endpoint", async () => {
    mockOk({ entity_id: "abc123" });
    await api.fingerprint("abc123");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/entity/abc123/fingerprint",
      expect.objectContaining({})
    );
  });

  it("entity calls correct endpoint", async () => {
    mockOk({ entity_id: "xyz" });
    await api.entity("xyz");
    expect(mockFetch).toHaveBeenCalledWith("/api/entity/xyz", expect.objectContaining({}));
  });

  it("feed passes limit parameter", async () => {
    mockOk({ items: [] });
    await api.feed(10);
    expect(mockFetch).toHaveBeenCalledWith("/api/feed?limit=10", expect.objectContaining({}));
  });

  it("feed uses default limit of 20", async () => {
    mockOk({ items: [] });
    await api.feed();
    expect(mockFetch).toHaveBeenCalledWith("/api/feed?limit=20", expect.objectContaining({}));
  });

  it("compare builds correct query string", async () => {
    mockOk({ overall_similarity: 0.9 });
    await api.compare("a", "b");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/fingerprint/compare?entity_1=a&entity_2=b",
      expect.objectContaining({})
    );
  });

  it("narrative calls correct endpoint", async () => {
    mockOk({ entity_id: "x", narrative: "text" });
    await api.narrative("x");
    expect(mockFetch).toHaveBeenCalledWith("/api/entity/x/narrative", expect.objectContaining({}));
  });

  it("reputation calls correct endpoint", async () => {
    mockOk({ entity_id: "x", trust_score: 50 });
    await api.reputation("x");
    expect(mockFetch).toHaveBeenCalledWith("/api/entity/x/reputation", expect.objectContaining({}));
  });

  it("leaderboard calls correct endpoint", async () => {
    mockOk({ entries: [] });
    await api.leaderboard("kills");
    expect(mockFetch).toHaveBeenCalledWith("/api/leaderboard/kills", expect.objectContaining({}));
  });

  it("throws on non-ok response", async () => {
    mockError(404);
    await expect(api.entity("missing")).rejects.toThrow("HTTP 404");
  });

  it("entities with type filter", async () => {
    mockOk({ entities: [], total: 0 });
    await api.entities("character", 5);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/entities?limit=5&entity_type=character",
      expect.objectContaining({})
    );
  });

  it("entities without type filter", async () => {
    mockOk({ entities: [], total: 0 });
    await api.entities(undefined, 10);
    expect(mockFetch).toHaveBeenCalledWith("/api/entities?limit=10", expect.objectContaining({}));
  });

  it("subscription calls correct endpoint", async () => {
    mockOk({ wallet: "0xabc", tier: 1 });
    await api.subscription("0xabc");
    expect(mockFetch).toHaveBeenCalledWith("/api/subscription/0xabc", expect.objectContaining({}));
  });

  it("streak calls correct endpoint", async () => {
    mockOk({ entity_id: "x", current_streak: 5 });
    await api.streak("x");
    expect(mockFetch).toHaveBeenCalledWith("/api/entity/x/streak", expect.objectContaining({}));
  });

  it("injects X-Wallet-Address header when wallet is stored", async () => {
    localStorage.setItem("watchtower_wallet", "0xdeadbeef");
    mockOk({ status: "ok" });
    await api.health();
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({
        headers: { "X-Wallet-Address": "0xdeadbeef" },
      })
    );
  });
});
