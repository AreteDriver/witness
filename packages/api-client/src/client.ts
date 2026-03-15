/**
 * WatchTower API client — configurable base URL for web (proxy) and mobile (direct).
 *
 * Web: createClient({ baseUrl: '/api' })
 * Mobile: createClient({ baseUrl: 'https://watchtower-evefrontier.fly.dev/api' })
 */

import type {
  Entity, Fingerprint, Dossier, Narrative, TimelineEvent,
  CompareResult, FeedItem, SearchResult, ReputationData,
  KillGraphData, HotzoneData, StreakData,
  CorpData, CorpProfile, CorpRivalry,
  AssemblyStats, SystemDossier, SubscriptionData, PricingData,
  WatchData, AlertData,
  NexusSubscription, NexusSubscribeResponse, NexusQuota, NexusDelivery,
  WalletConnectResponse, WalletMeResponse,
  CycleEnvelope, CycleInfo, OrbitalZone, ScanResult, Clone, CrownEntry, CrownRoster,
  AnalyticsData,
} from './types.js';

export interface ClientConfig {
  baseUrl: string;
  getHeaders?: () => Record<string, string>;
}

export function createClient(config: ClientConfig) {
  const { baseUrl, getHeaders } = config;

  async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
    const headers = { ...getHeaders?.(), ...init?.headers } as Record<string, string>;
    const r = await fetch(`${baseUrl}${url}`, { ...init, headers });
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

  return {
    // Health
    health: () => fetchJson<{ status: string; tables: Record<string, number> }>('/health'),

    // Entity Intelligence
    search: (q: string) => fetchJson<{ results: SearchResult[] }>(`/search?q=${encodeURIComponent(q)}`),
    entity: (id: string) => fetchJson<Dossier>(`/entity/${id}`),
    fingerprint: (id: string) => fetchJson<Fingerprint>(`/entity/${id}/fingerprint`),
    timeline: (id: string, start?: number, end?: number) => {
      const params = new URLSearchParams();
      if (start !== undefined) params.set('start', String(start));
      if (end !== undefined) params.set('end', String(end));
      const qs = params.toString();
      return fetchJson<{ entity_id: string; events: TimelineEvent[] }>(
        `/entity/${id}/timeline${qs ? `?${qs}` : ''}`
      );
    },
    narrative: (id: string) => fetchJson<Narrative>(`/entity/${id}/narrative`),
    reputation: (id: string) => fetchJson<ReputationData>(`/entity/${id}/reputation`),
    streak: (id: string) => fetchJson<StreakData>(`/entity/${id}/streak`),
    entities: (type?: string, limit = 20) =>
      fetchJson<{ entities: Entity[]; total: number }>(
        `/entities?limit=${limit}${type ? `&entity_type=${type}` : ''}`
      ),

    // Feed & Discovery
    feed: (limit = 20, before?: number) =>
      fetchJson<{ items: FeedItem[] }>(`/feed?limit=${limit}${before ? `&before=${before}` : ''}`),
    leaderboard: (category: string) =>
      fetchJson<{ entries: { entity_id: string; display_name: string; score: number }[] }>(
        `/leaderboard/${category}`
      ),

    // Tactical
    compare: (id1: string, id2: string) =>
      fetchJson<CompareResult>(`/fingerprint/compare?entity_1=${id1}&entity_2=${id2}`),
    killGraph: (entityId?: string) =>
      fetchJson<KillGraphData>(`/kill-graph${entityId ? `?entity_id=${entityId}` : ''}`),
    hotzones: (window = 'all') =>
      fetchJson<{ window: string; hotzones: HotzoneData[] }>(`/hotzones?window=${window}`),
    hotStreaks: () => fetchJson<{ streaks: StreakData[] }>('/streaks'),

    // Corporation
    corps: () => fetchJson<{ corps: CorpData[] }>('/corps'),
    corp: (corpId: string) => fetchJson<CorpProfile>(`/corp/${corpId}`),
    corpRivalries: () => fetchJson<{ rivalries: CorpRivalry[] }>('/corps/rivalries'),

    // System
    systemDossier: (systemId: string) => fetchJson<SystemDossier>(`/system/${systemId}`),
    systemNarrative: (systemId: string) =>
      fetchJson<{ system_id: string; narrative: string }>(`/system/${systemId}/narrative`),

    // Assemblies
    assemblies: () => fetchJson<AssemblyStats>('/assemblies'),

    // Subscription & Payment
    subscription: (wallet: string) => fetchJson<SubscriptionData>(`/subscription/${wallet}`),
    subscribe: (wallet: string, tier: number) =>
      postJson<SubscriptionData>('/subscribe', { wallet_address: wallet, tier }),
    pricing: () => fetchJson<PricingData>('/pricing'),
    createCheckout: (tier: number) => postJson<{ url: string }>('/checkout/create', { tier }),

    // Watches & Alerts
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

    // Auth
    walletChallenge: () =>
      postJson<{ nonce: string; message: string }>('/auth/wallet/challenge', {}),
    walletConnect: (walletAddress: string, signature: string, message: string) =>
      postJson<WalletConnectResponse>('/auth/wallet/connect', {
        wallet_address: walletAddress, signature, message,
      }),
    walletMe: () => fetchJson<WalletMeResponse>('/auth/wallet/me'),
    walletDisconnect: () => postJson<{ status: string }>('/auth/wallet/disconnect', {}),

    // NEXUS
    nexusQuota: () => fetchJson<NexusQuota>('/nexus/quota'),
    nexusSubscribe: (name: string, endpointUrl: string, filters: Record<string, unknown> = {}) =>
      postJson<NexusSubscribeResponse>('/nexus/subscribe', {
        name, endpoint_url: endpointUrl, filters,
      }),
    nexusSubscriptions: (apiKey: string) =>
      fetchJson<{ subscriptions: NexusSubscription[] }>(
        `/nexus/subscriptions?api_key=${encodeURIComponent(apiKey)}`
      ),
    nexusDeleteSubscription: (subId: number, apiKey: string) =>
      deleteJson<{ status: string }>(
        `/nexus/subscriptions/${subId}?api_key=${encodeURIComponent(apiKey)}`
      ),
    nexusDeliveries: (apiKey: string, limit = 50) =>
      fetchJson<{ deliveries: NexusDelivery[] }>(
        `/nexus/deliveries?api_key=${encodeURIComponent(apiKey)}&limit=${limit}`
      ),

    // Cycle 5
    cycle: () => fetchJson<CycleEnvelope<CycleInfo>>('/cycle'),
    orbitalZones: (threatLevel?: string) =>
      fetchJson<CycleEnvelope<OrbitalZone[]>>(
        `/orbital-zones${threatLevel ? `?threat_level=${threatLevel}` : ''}`
      ),
    zoneHistory: (zoneId: string) =>
      fetchJson<CycleEnvelope<unknown[]>>(`/orbital-zones/${zoneId}/history`),
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
      fetchJson<CycleEnvelope<Clone[]>>(`/clones${corpId ? `?corp_id=${corpId}` : ''}`),
    cloneQueue: () => fetchJson<CycleEnvelope<Clone[]>>('/clones/queue'),
    crowns: (corpId?: string) =>
      fetchJson<CycleEnvelope<CrownEntry[]>>(`/crowns${corpId ? `?corp_id=${corpId}` : ''}`),
    crownRoster: (corpId?: string) =>
      fetchJson<CycleEnvelope<CrownRoster>>(
        `/crowns/roster${corpId ? `?corp_id=${corpId}` : ''}`
      ),

    // Admin
    analytics: () => fetchJson<AnalyticsData>('/admin/analytics'),
    sseStatus: () => fetchJson<{ subscribers: number; timestamp: number }>('/events/status'),
  };
}

export type WatchTowerClient = ReturnType<typeof createClient>;
