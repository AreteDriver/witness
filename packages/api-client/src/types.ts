/**
 * WatchTower API types — shared across web, mobile, and third-party integrations.
 * These types match the backend Pydantic models 1:1.
 */

// === Entity Intelligence ===

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

export interface Dossier {
  entity_id: string;
  entity_type: string;
  display_name: string;
  first_seen: number;
  last_seen: number;
  event_count: number;
  kill_count: number;
  death_count: number;
  gate_count: number;
  corp_id: string | null;
  danger_rating: string;
  titles: string[];
  tribe_name: string | null;
  tribe_short: string | null;
}

export interface Narrative {
  entity_id: string;
  narrative: string;
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

// === Tactical ===

export interface KillGraphData {
  nodes: { id: string; name: string; kills: number; deaths: number }[];
  edges: {
    attacker: string;
    victim: string;
    attacker_name: string;
    victim_name: string;
    count: number;
    systems: string[];
  }[];
  vendettas: {
    entity_1: string;
    entity_2: string;
    entity_1_name: string;
    entity_2_name: string;
    kills_1_to_2: number;
    kills_2_to_1: number;
    total: number;
  }[];
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

// === Corporation ===

export interface CorpData {
  corp_id: string;
  member_count: number;
  total_kills: number;
  total_deaths: number;
  kill_ratio: number;
}

export interface CorpProfile {
  corp_id: string;
  tribe_name: string | null;
  tribe_short: string | null;
  member_count: number;
  active_members: number;
  total_kills: number;
  total_deaths: number;
  kill_ratio: number;
  systems: string[];
  system_count: number;
  top_killers: { entity_id: string; display_name: string; kills: number }[];
  threat_level: string;
}

export interface CorpRivalry {
  corp_1: string;
  corp_2: string;
  kills_1_to_2: number;
  kills_2_to_1: number;
  total: number;
}

// === Feed & Search ===

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

// === Assemblies ===

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

// === System ===

export interface SystemDossier {
  solar_system_id: string;
  solar_system_name: string;
  total_kills: number;
  unique_victims?: number;
  unique_attackers?: number;
  first_kill?: number;
  last_kill?: number;
  kills_24h?: number;
  kills_7d?: number;
  gate_transits?: number;
  danger_level: string;
  hour_distribution?: Record<number, number>;
  top_attackers?: { entity_id: string; display_name: string; kills: number }[];
  top_victims?: { entity_id: string; display_name: string; deaths: number }[];
  infrastructure?: { assembly_id: string; type: string; state: string; owner: string }[];
  recent_stories?: { id: number; event_type: string; headline: string; severity: string; timestamp: number }[];
}

// === Subscription & Payment ===

export interface SubscriptionData {
  wallet: string;
  tier: number;
  tier_name: string;
  expires_at: number;
  active: boolean;
}

export interface PricingData {
  sui_usd: number;
  fetched_at: string;
  is_stale: boolean;
  tiers: Record<string, {
    usd_per_week: number;
    sui_per_week: number;
    sui_mist: number;
    tier: number;
  }>;
}

// === Watches & Alerts ===

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

// === NEXUS ===

export interface NexusSubscription {
  id: number;
  name: string;
  endpoint_url: string;
  filters: Record<string, unknown>;
  active: boolean;
  delivery_count: number;
  last_delivered_at: number | null;
  created_at: number;
}

export interface NexusSubscribeResponse {
  status: string;
  api_key: string;
  secret: string;
  name: string;
  endpoint_url: string;
  filters: Record<string, unknown>;
}

export interface NexusQuota {
  tier: number;
  subscriptions_used: number;
  subscriptions_max: number;
  deliveries_today: number;
  deliveries_max: number;
}

export interface NexusDelivery {
  id: number;
  event_type: string;
  status_code: number | null;
  success: number;
  attempts: number;
  error: string | null;
  delivered_at: number;
  name: string;
}

// === Auth ===

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

// === Cycle 5 ===

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

// === Admin ===

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
  top_active_7d: {
    entity_id: string;
    display_name: string;
    kill_count: number;
    death_count: number;
    event_count: number;
  }[];
}
