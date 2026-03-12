import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { api } from '../api';
import type { FeedItem } from '../api';

function timeAgo(ts: number): string {
  const delta = Math.floor(Date.now() / 1000) - ts;
  if (delta < 60) return 'just now';
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  return `${Math.floor(delta / 86400)}d ago`;
}

function formatTimestamp(ts: number): string {
  return new Date(ts * 1000).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
}

const EVENT_LABELS: Record<string, string> = {
  engagement: 'SIGINT',
  new_entity: 'NEW CONTACT',
  milestone: 'MILESTONE',
  title: 'DESIGNATION',
  streak: 'THREAT ALERT',
};

const SEVERITY_STYLES: Record<string, { border: string; indicator: string; label: string }> = {
  critical: {
    border: 'border-l-[var(--eve-red)]',
    indicator: 'bg-[var(--eve-red)]',
    label: 'CRITICAL',
  },
  warning: {
    border: 'border-l-[var(--eve-orange)]',
    indicator: 'bg-[var(--eve-orange)]',
    label: 'ELEVATED',
  },
  info: {
    border: 'border-l-[var(--eve-green)]',
    indicator: 'bg-[var(--eve-green)]',
    label: 'ROUTINE',
  },
};

export function StoryFeed() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.feed(20).then((data) => {
      setItems(data.items);
      setHasMore(data.items.length >= 20);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const loadMore = () => {
    if (!hasMore || loadingMore || items.length === 0) return;
    setLoadingMore(true);
    const oldest = items[items.length - 1].timestamp;
    fetch(`/api/feed?limit=20&before=${oldest}`, {
      headers: { ...getAuthHeadersInline() },
    })
      .then((r) => r.json())
      .then((data: { items: FeedItem[] }) => {
        setItems(prev => [...prev, ...data.items]);
        setHasMore(data.items.length >= 20);
        setLoadingMore(false);
      }).catch(() => setLoadingMore(false));
  };

  const handleEntityClick = (entityId: string) => {
    navigate(`/entity/${entityId}`);
  };

  if (loading) {
    return (
      <div className="font-mono text-xs text-[var(--eve-dim)] animate-pulse">
        INITIALIZING FEED...
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="font-mono text-xs text-[var(--eve-dim)]">
        NO INTELLIGENCE AVAILABLE
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {/* Feed header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[var(--eve-green)] animate-pulse" />
          <h3 className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--eve-orange)] font-bold">
            Intelligence Feed
          </h3>
        </div>
        <span className="font-mono text-[10px] text-[var(--eve-dim)]">
          {items.length} entries
        </span>
      </div>

      {/* Feed items */}
      {items.map((item) => {
        const style = SEVERITY_STYLES[item.severity] || SEVERITY_STYLES.info;
        const eventLabel = EVENT_LABELS[item.event_type] || item.event_type.toUpperCase();

        return (
          <div
            key={item.id}
            className={`bg-[var(--eve-surface)] border border-[var(--eve-border)] border-l-2 ${style.border} rounded-sm p-3 hover:bg-[#1a1a2a] transition-colors`}
          >
            {/* Meta line */}
            <div className="flex items-center gap-2 mb-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${style.indicator}`} />
              <span className="font-mono text-[10px] tracking-wider text-[var(--eve-dim)]">
                {eventLabel}
              </span>
              <span className="font-mono text-[10px] text-[var(--eve-dim)] opacity-50">
                //
              </span>
              <span className="font-mono text-[10px] text-[var(--eve-dim)]">
                {style.label}
              </span>
              <span className="ml-auto font-mono text-[10px] text-[var(--eve-dim)]" title={formatTimestamp(item.timestamp)}>
                {timeAgo(item.timestamp)}
              </span>
            </div>

            {/* Headline */}
            <p className="text-sm text-[var(--eve-text)] leading-snug">
              {item.headline}
            </p>

            {/* Body */}
            {item.body && (
              <p className="text-xs text-[var(--eve-dim)] mt-1.5 leading-relaxed">
                {item.body}
              </p>
            )}

            {/* Entity links */}
            {item.entity_ids && item.entity_ids.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {item.entity_ids.map((eid) => (
                  <button
                    key={eid}
                    onClick={() => handleEntityClick(eid)}
                    className="font-mono text-[10px] text-[var(--eve-green)] hover:text-[var(--eve-orange)] hover:underline cursor-pointer bg-transparent border-none p-0 transition-colors"
                    title={`View dossier: ${eid}`}
                  >
                    [{eid.slice(0, 12)}]
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}

      {/* Load more */}
      {hasMore && (
        <button
          onClick={loadMore}
          disabled={loadingMore}
          className="w-full font-mono text-[10px] uppercase tracking-wider text-[var(--eve-dim)] hover:text-[var(--eve-green)] py-2 bg-transparent border border-[var(--eve-border)] rounded-sm cursor-pointer transition-colors disabled:opacity-50"
        >
          {loadingMore ? 'DECRYPTING...' : 'LOAD MORE INTELLIGENCE'}
        </button>
      )}
    </div>
  );
}

function getAuthHeadersInline(): Record<string, string> {
  const headers: Record<string, string> = {};
  const session = localStorage.getItem('watchtower_session');
  if (session) headers['X-Session'] = session;
  const wallet = localStorage.getItem('watchtower_wallet');
  if (wallet) headers['X-Wallet-Address'] = wallet;
  return headers;
}
