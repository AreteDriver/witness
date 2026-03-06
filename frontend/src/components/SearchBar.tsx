import { useState } from 'react';
import { api, SearchResult } from '../api';

interface Props {
  onSelect: (entityId: string) => void;
}

export function SearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);

  const search = async (q: string) => {
    setQuery(q);
    if (q.length < 2) { setResults([]); setOpen(false); return; }
    try {
      const data = await api.search(q);
      setResults(data.results);
      setOpen(true);
    } catch { setResults([]); }
  };

  return (
    <div className="relative">
      <input
        type="text"
        value={query}
        onChange={(e) => search(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder="Search entities..."
        className="w-full bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded px-4 py-2 text-[var(--eve-text)] placeholder-[var(--eve-dim)] focus:border-[var(--eve-green)] focus:outline-none"
      />
      {open && results.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-[var(--eve-surface)] border border-[var(--eve-border)] rounded shadow-lg max-h-60 overflow-y-auto">
          {results.map((r) => (
            <button
              key={r.entity_id}
              onClick={() => { onSelect(r.entity_id); setOpen(false); setQuery(r.display_name || r.entity_id); }}
              className="w-full text-left px-4 py-2 hover:bg-[var(--eve-border)] flex justify-between items-center"
            >
              <span>
                <span className="text-[var(--eve-green)] text-xs mr-2">{r.entity_type.toUpperCase()}</span>
                {r.display_name || r.entity_id.slice(0, 16)}
              </span>
              <span className="text-[var(--eve-dim)] text-xs">{r.event_count} events</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
