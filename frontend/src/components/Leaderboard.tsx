import { useEffect, useState } from 'react';
import { api } from '../api';

interface Entry {
  entity_id: string;
  display_name: string;
  score: number;
}

const CATEGORIES = [
  { key: 'most_active_gates', label: 'Most Active Gates' },
  { key: 'deadliest_gates', label: 'Deadliest Gates' },
  { key: 'top_killers', label: 'Top Killers' },
  { key: 'most_deaths', label: 'Most Deaths' },
  { key: 'most_traveled', label: 'Most Traveled' },
];

interface Props {
  onSelect: (entityId: string) => void;
}

export function Leaderboard({ onSelect }: Props) {
  const [category, setCategory] = useState('most_active_gates');
  const [entries, setEntries] = useState<Entry[]>([]);

  useEffect(() => {
    api.leaderboard(category).then((d) => setEntries(d.entries)).catch(() => setEntries([]));
  }, [category]);

  return (
    <div className="space-y-3">
      <h3 className="text-xs uppercase tracking-wider text-[var(--eve-orange)] font-bold">
        Leaderboard
      </h3>
      <div className="flex gap-1 flex-wrap">
        {CATEGORIES.map((c) => (
          <button
            key={c.key}
            onClick={() => setCategory(c.key)}
            className={`px-2 py-1 rounded text-xs ${
              category === c.key
                ? 'bg-[var(--eve-green)] text-black font-bold'
                : 'bg-[var(--eve-border)] text-[var(--eve-dim)] hover:text-[var(--eve-text)]'
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>
      <div className="space-y-1">
        {entries.slice(0, 10).map((e, i) => (
          <button
            key={e.entity_id}
            onClick={() => onSelect(e.entity_id)}
            className="w-full flex justify-between items-center px-3 py-1.5 rounded hover:bg-[var(--eve-border)] text-sm text-left"
          >
            <span>
              <span className="text-[var(--eve-dim)] w-6 inline-block">{i + 1}.</span>
              {e.display_name || e.entity_id.slice(0, 16)}
            </span>
            <span className="text-[var(--eve-green)] font-mono">{e.score}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
