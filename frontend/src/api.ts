const BASE = '/api';

async function fetchJson<T>(url: string): Promise<T> {
  const r = await fetch(`${BASE}${url}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export interface Entity {
  entity_id: string;
  entity_type: string;
  display_name: string;
  event_count: number;
  kill_count: number;
  death_count: number;
  gate_count: number;
}

export interface Fingerprint {
  entity_id: string;
  entity_type: string;
  event_count: number;
  temporal: {
    peak_hour: string;
    peak_hour_pct: number;
    active_hours: number;
    entropy: number;
    predictability: string;
  };
  route: {
    top_gate: string;
    top_gate_pct: number;
    unique_gates: number;
    unique_systems: number;
    route_entropy: number;
    predictability: string;
  };
  social: {
    top_associate: string;
    top_associate_count: number;
    unique_associates: number;
    solo_ratio: number;
    top_5_associates: { id: string; count: number }[];
  };
  threat: {
    kill_ratio: number;
    kills_per_day: number;
    deaths_per_day: number;
    threat_level: string;
    combat_zones: number;
  };
  opsec_score: number;
  opsec_rating: string;
}

export interface FeedItem {
  id: number;
  event_type: string;
  headline: string;
  body: string;
  severity: string;
  timestamp: number;
}

export interface SearchResult {
  entity_id: string;
  entity_type: string;
  display_name: string;
  event_count: number;
}

export const api = {
  health: () => fetchJson<{ status: string; tables: Record<string, number> }>('/health'),
  search: (q: string) => fetchJson<{ results: SearchResult[] }>(`/search?q=${encodeURIComponent(q)}`),
  entity: (id: string) => fetchJson<Entity>(`/entity/${id}`),
  fingerprint: (id: string) => fetchJson<Fingerprint>(`/entity/${id}/fingerprint`),
  feed: (limit = 20) => fetchJson<{ items: FeedItem[] }>(`/feed?limit=${limit}`),
  entities: (type?: string, limit = 20) =>
    fetchJson<{ entities: Entity[]; total: number }>(
      `/entities?limit=${limit}${type ? `&entity_type=${type}` : ''}`
    ),
  leaderboard: (category: string) =>
    fetchJson<{ entries: { entity_id: string; display_name: string; score: number }[] }>(
      `/leaderboard/${category}`
    ),
};
