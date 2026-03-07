import { useEffect, useState } from 'react';
import { api } from '../api';
import type { FeedItem } from '../api';

function timeAgo(ts: number): string {
  const delta = Math.floor(Date.now() / 1000) - ts;
  if (delta < 60) return 'just now';
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  return `${Math.floor(delta / 86400)}d ago`;
}

function severityColor(s: string): string {
  if (s === 'critical') return 'var(--eve-red)';
  if (s === 'warning') return 'var(--eve-orange)';
  return 'var(--eve-green)';
}

export function StoryFeed() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.feed(10).then((data) => { setItems(data.items); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-[var(--eve-dim)]">Loading feed...</div>;
  if (items.length === 0) return <div className="text-[var(--eve-dim)]">No stories yet.</div>;

  return (
    <div className="space-y-3">
      <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
        Story Feed
      </h3>
      {items.map((item) => (
        <div key={item.id} className="bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded p-3">
          <div className="flex justify-between items-start mb-1">
            <span className="text-sm font-bold" style={{ color: severityColor(item.severity) }}>
              {item.headline}
            </span>
            <span className="text-xs text-[var(--eve-dim)] shrink-0 ml-2">{timeAgo(item.timestamp)}</span>
          </div>
          {item.body && <p className="text-xs text-[var(--eve-dim)]">{item.body}</p>}
        </div>
      ))}
    </div>
  );
}
