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

export interface TimelineEvent {
  event_type: string;
  timestamp: number;
  gate_id?: string;
  gate_name?: string;
  character_id?: string;
  solar_system_id?: string;
  killmail_id?: string;
  victim_character_id?: string;
  delta_seconds: number;
}

export interface CompareResult {
  entity_1: string;
  entity_2: string;
  temporal_similarity: number;
  route_similarity: number;
  social_similarity: number;
  overall_similarity: number;
  likely_alt: boolean;
  likely_fleet_mate: boolean;
}

export interface Narrative {
  entity_id: string;
  narrative: string;
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

export interface KillGraphData {
  nodes: { id: string; name: string; kills: number; deaths: number }[];
  edges: { attacker: string; victim: string; attacker_name: string; victim_name: string; count: number; systems: string[] }[];
  vendettas: { entity_1: string; entity_2: string; entity_1_name: string; entity_2_name: string; kills_1_to_2: number; kills_2_to_1: number; total: number }[];
  total_edges: number;
  total_nodes: number;
}

export interface HotzoneData {
  solar_system_id: string;
  solar_system_name: string;
  kills: number;
  unique_attackers: number;
  unique_victims: number;
  latest_kill: number;
  danger_level: string;
}

export interface StreakData {
  entity_id: string;
  display_name?: string;
  current_streak: number;
  longest_streak: number;
  last_kill_time: number;
  status: string;
  kills_7d: number;
  kills_30d: number;
  avg_kills_per_week: number;
}

export interface CorpData {
  corp_id: string;
  member_count: number;
  total_kills: number;
  total_deaths: number;
  kill_ratio: number;
}

export interface CorpRivalry {
  corp_1: string;
  corp_2: string;
  kills_1_to_2: number;
  kills_2_to_1: number;
  total: number;
}

export interface ReputationData {
  entity_id: string;
  trust_score: number;
  rating: string;
  breakdown: {
    combat_honor: number;
    target_diversity: number;
    reciprocity: number;
    consistency: number;
    community: number;
    restraint: number;
  };
  stats: {
    kills: number;
    deaths: number;
    unique_victims: number;
    unique_attackers: number;
    vendettas: number;
  };
  factors: string[];
}

export interface AssemblyData {
  assembly_id: string;
  type: string;
  solar_system_id: string;
  solar_system_name: string;
  state: string;
  position: { x: number; y: number; z: number };
  deployed_at: number;
}

export interface AssemblyStats {
  total: number;
  online: number;
  offline: number;
  systems_covered: number;
  by_type: Record<string, number>;
  assemblies: AssemblyData[];
}

export interface SubscriptionData {
  wallet: string;
  tier: number;
  tier_name: string;
  expires_at: number;
  active: boolean;
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
  timeline: (id: string, start?: number, end?: number) =>
    fetchJson<{ entity_id: string; events: TimelineEvent[] }>(
      `/entity/${id}/timeline${start ? `?start=${start}` : ''}${end ? `&end=${end}` : ''}`
    ),
  compare: (id1: string, id2: string) =>
    fetchJson<CompareResult>(`/fingerprint/compare?entity_1=${id1}&entity_2=${id2}`),
  narrative: (id: string) => fetchJson<Narrative>(`/entity/${id}/narrative`),
  killGraph: (entityId?: string) =>
    fetchJson<KillGraphData>(`/kill-graph${entityId ? `?entity_id=${entityId}` : ''}`),
  hotzones: (window = 'all') =>
    fetchJson<{ window: string; hotzones: HotzoneData[] }>(`/hotzones?window=${window}`),
  streak: (id: string) => fetchJson<StreakData>(`/entity/${id}/streak`),
  hotStreaks: () => fetchJson<{ streaks: StreakData[] }>('/streaks'),
  corps: () => fetchJson<{ corps: CorpData[] }>('/corps'),
  corpRivalries: () => fetchJson<{ rivalries: CorpRivalry[] }>('/corps/rivalries'),
  reputation: (id: string) => fetchJson<ReputationData>(`/entity/${id}/reputation`),
  assemblies: () => fetchJson<AssemblyStats>('/assemblies'),
  subscription: (wallet: string) => fetchJson<SubscriptionData>(`/subscription/${wallet}`),
};
