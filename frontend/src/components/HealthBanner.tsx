import { useEffect, useState } from 'react';
import { api } from '../api';

export function HealthBanner() {
  const [tables, setTables] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    api.health().then((d) => setTables(d.tables)).catch(() => setTables(null));
    const id = setInterval(() => {
      api.health().then((d) => setTables(d.tables)).catch(() => {});
    }, 30000);
    return () => clearInterval(id);
  }, []);

  if (!tables) return null;

  return (
    <div className="flex gap-4 text-xs text-[var(--eve-dim)]">
      {Object.entries(tables).map(([k, v]) => (
        <span key={k}>
          <span className="text-[var(--eve-green)]">{v.toLocaleString()}</span> {k}
        </span>
      ))}
    </div>
  );
}
