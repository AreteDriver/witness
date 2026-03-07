import { useEffect, useState } from 'react';
import { api } from '../api';
import type { TimelineEvent } from '../api';

interface Props {
  entityId: string;
}

function eventIcon(type: string): string {
  if (type === 'killmail') return '\u{1F480}';
  return '\u{1F539}';
}

function eventColor(type: string): string {
  if (type === 'killmail') return 'var(--eve-red)';
  return 'var(--eve-green)';
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toISOString().replace('T', ' ').slice(0, 16);
}

export function EntityTimeline({ entityId }: Props) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const now = Math.floor(Date.now() / 1000);
    api.timeline(entityId, now - 14 * 86400, now).then((data) => {
      setEvents(data.events.slice(-50)); // Last 50
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [entityId]);

  if (loading) return <div className="text-[var(--eve-dim)] text-sm">Loading timeline...</div>;
  if (events.length === 0) return <div className="text-[var(--eve-dim)] text-sm">No recent events.</div>;

  return (
    <div className="space-y-2">
      <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
        Recent Activity
      </h3>
      <div className="max-h-80 overflow-y-auto space-y-1 pr-1">
        {events.map((e, i) => (
          <div key={i} className="flex items-start gap-2 text-xs group">
            <div className="flex flex-col items-center">
              <span className="text-sm">{eventIcon(e.event_type)}</span>
              {i < events.length - 1 && (
                <div className="w-px h-4 bg-[var(--eve-border)]" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex justify-between">
                <span style={{ color: eventColor(e.event_type) }} className="font-bold uppercase">
                  {e.event_type === 'killmail' ? 'Kill' : 'Transit'}
                </span>
                <span className="text-[var(--eve-dim)] shrink-0 ml-2">{formatTime(e.timestamp)}</span>
              </div>
              <div className="text-[var(--eve-dim)] truncate">
                {e.event_type === 'gate_transit'
                  ? `${e.gate_name || e.gate_id?.slice(0, 16) || 'Unknown gate'}`
                  : `System ${e.solar_system_id?.slice(0, 12) || 'unknown'}`}
                {e.delta_seconds > 0 && (
                  <span className="ml-1 text-[var(--eve-dim)]">
                    (+{e.delta_seconds < 60 ? `${e.delta_seconds}s` : e.delta_seconds < 3600 ? `${Math.floor(e.delta_seconds / 60)}m` : `${Math.floor(e.delta_seconds / 3600)}h`})
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
