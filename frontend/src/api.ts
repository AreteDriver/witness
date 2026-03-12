const BASE = '/api';

const SESSION_KEY = 'watchtower_session';
const WALLET_KEY = 'watchtower_wallet';

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const session = localStorage.getItem(SESSION_KEY);
  if (session) {
    headers['X-Session'] = session;
  }
  const wallet = localStorage.getItem(WALLET_KEY);
  if (wallet) {
    headers['X-Wallet-Address'] = wallet;
  }
  return headers;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${url}`, {
    ...init,
    headers: { ...getAuthHeaders(), ...init?.headers },
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  return fetchJson<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function deleteJson<T>(url: string): Promise<T> {
  return fetchJson<T>(url, { method: 'DELETE' });
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
  entity_ids: string[];
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

export interface WatchData {
  id: number;
  user_id: string;
  watch_type: string;
  target_id: string;
  active: boolean;
  webhook_url: string;
  created_at: number;
}

export interface AlertData {
  id: number;
  watch_id: number;
  title: string;
  body: string;
  severity: string;
  read: number;
  created_at: number;
}

// Wallet auth types
export interface WalletConnectResponse {
  session_token: string;
  wallet_address: string;
  tier: number;
  tier_name: string;
  is_admin: boolean;
}

export interface WalletMeResponse {
  wallet_address: string;
  tier: number;
  tier_name: string;
  is_admin: boolean;
  connected_at: number;
}

// Cycle 5 types
export interface CycleEnvelope<T> {
  cycle: number;
  reset_at: number;
  data: T;
}

export interface CycleInfo {
  number: number;
  name: string;
  reset_at: number;
  days_elapsed: number;
}

export interface OrbitalZone {
  zone_id: string;
  name: string;
  solar_system_id: string;
  feral_ai_tier: number;
  threat_level: string;
  last_scanned: number | null;
  stale: boolean;
}

export interface FeralAiEvent {
  event_type: string;
  old_tier: number;
  new_tier: number;
  old_threat: string;
  new_threat: string;
  severity: string;
  timestamp: number;
}

export interface ScanResult {
  scan_id: string;
  zone_id: string;
  scanner_id: string;
  scanner_name: string;
  result_type: string;
  scanned_at: number;
  zone_hostile_recent?: boolean;
}

export interface Clone {
  clone_id: string;
  owner_id: string;
  owner_name: string;
  blueprint_id: string;
  status: string;
  location_zone_id: string;
  manufactured_at: number;
  blueprint_name?: string;
  tier?: number;
  manufacture_time_sec?: number;
}

export interface CrownEntry {
  crown_id: string;
  character_id: string;
  character_name: string;
  crown_type: string;
  attributes: string;
  equipped_at: number;
}

export interface CrownRoster {
  distribution: { crown_type: string; count: number }[];
  crowned: number;
  total_characters: number;
  uncrowned: number;
}

export interface AnalyticsData {
  timestamp: number;
  totals: {
    entities: number;
    characters: number;
    gates: number;
    killmails: number;
    gate_events: number;
    titles: number;
    stories: number;
    active_watches: number;
  };
  activity: {
    kills_24h: number;
    kills_7d: number;
    gate_transits_24h: number;
    gate_transits_7d: number;
    new_entities_24h: number;
  };
  subscriptions: {
    scout: number;
    oracle: number;
    spymaster: number;
  };
  top_active_7d: { entity_id: string; display_name: string; kill_count: number; death_count: number; event_count: number }[];
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
  subscribe: (wallet: string, tier: number) =>
    postJson<SubscriptionData>('/subscribe', { wallet_address: wallet, tier }),
  watches: (userId: string) =>
    fetchJson<{ watches: WatchData[] }>(`/watches?user_id=${encodeURIComponent(userId)}`),
  createWatch: (userId: string, watchType: string, targetId: string, webhookUrl = '') =>
    postJson<{ status: string }>('/watches', {
      user_id: userId, watch_type: watchType, target_id: targetId, webhook_url: webhookUrl,
    }),
  deleteWatch: (targetId: string, userId: string) =>
    deleteJson<{ status: string }>(`/watches/${targetId}?user_id=${encodeURIComponent(userId)}`),
  alerts: (userId: string) =>
    fetchJson<{ alerts: AlertData[] }>(`/alerts?user_id=${encodeURIComponent(userId)}`),
  markAlertRead: (alertId: number) =>
    postJson<{ status: string }>(`/alerts/${alertId}/read`, {}),

  // Wallet auth
  walletConnect: (walletAddress: string) =>
    postJson<WalletConnectResponse>('/auth/wallet/connect', { wallet_address: walletAddress }),
  walletMe: () =>
    fetchJson<WalletMeResponse>('/auth/wallet/me'),
  walletDisconnect: () =>
    postJson<{ status: string }>('/auth/wallet/disconnect', {}),

  // Admin analytics
  analytics: () => fetchJson<AnalyticsData>('/admin/analytics'),

  // SSE status
  sseStatus: () => fetchJson<{ subscribers: number; timestamp: number }>('/events/status'),

  // Cycle 5
  cycle: () => fetchJson<CycleEnvelope<CycleInfo>>('/cycle'),
  orbitalZones: (threatLevel?: string) =>
    fetchJson<CycleEnvelope<OrbitalZone[]>>(
      `/orbital-zones${threatLevel ? `?threat_level=${threatLevel}` : ''}`
    ),
  zoneHistory: (zoneId: string) =>
    fetchJson<CycleEnvelope<FeralAiEvent[]>>(`/orbital-zones/${zoneId}/history`),
  scans: (zoneId?: string, resultType?: string) => {
    const params = new URLSearchParams();
    if (zoneId) params.set('zone_id', zoneId);
    if (resultType) params.set('result_type', resultType);
    const qs = params.toString();
    return fetchJson<CycleEnvelope<ScanResult[]>>(`/scans${qs ? `?${qs}` : ''}`);
  },
  scanFeed: (limit = 20) =>
    fetchJson<CycleEnvelope<ScanResult[]>>(`/scans/feed?limit=${limit}`),
  clones: (corpId?: string) =>
    fetchJson<CycleEnvelope<Clone[]>>(
      `/clones${corpId ? `?corp_id=${corpId}` : ''}`
    ),
  cloneQueue: () => fetchJson<CycleEnvelope<Clone[]>>('/clones/queue'),
  crowns: (corpId?: string) =>
    fetchJson<CycleEnvelope<CrownEntry[]>>(
      `/crowns${corpId ? `?corp_id=${corpId}` : ''}`
    ),
  crownRoster: (corpId?: string) =>
    fetchJson<CycleEnvelope<CrownRoster>>(
      `/crowns/roster${corpId ? `?corp_id=${corpId}` : ''}`
    ),
};
