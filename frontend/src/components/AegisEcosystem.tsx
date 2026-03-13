import { useEffect, useState } from 'react';
import { ChainIntegrity } from './ChainIntegrity';

const MONOLITH_API = 'https://monolith-evefrontier.fly.dev/api';

interface MonolithAnomaly {
  anomaly_id: string;
  anomaly_type: string;
  severity: string;
  detected_at: number;
}

interface MonolithBugReport {
  report_id: string;
  title: string;
  severity: string;
  category: string;
  summary: string;
  generated_at: number;
}

const STATS: { value: string; label: string }[] = [
  { value: '17', label: 'DETECTION RULES' },
  { value: '4', label: 'CHECKER MODULES' },
  { value: 'CRITICAL \u2192 LOW', label: 'SEVERITY SCALE' },
];

const TAGS: { label: string; variant: 'live' | 'default' }[] = [
  { label: 'LIVE', variant: 'live' },
  { label: 'SUI / MOVE', variant: 'default' },
  { label: 'FASTAPI', variant: 'default' },
  { label: 'DISCORD ALERTS', variant: 'default' },
];

export function AegisEcosystem() {
  const [anomalies, setAnomalies] = useState<MonolithAnomaly[]>([]);
  const [bugReports, setBugReports] = useState<MonolithBugReport[]>([]);

  useEffect(() => {
    fetch(`${MONOLITH_API}/anomalies?limit=10`)
      .then((r) => r.json())
      .then((d) => setAnomalies(d.data || []))
      .catch(() => setAnomalies([]));

    fetch(`${MONOLITH_API}/reports?limit=10`)
      .then((r) => r.json())
      .then((d) => setBugReports(d.data || []))
      .catch(() => setBugReports([]));
  }, []);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');

        @keyframes aegis-scan {
          0% { top: -4px; opacity: 0; }
          5% { opacity: 1; }
          95% { opacity: 1; }
          100% { top: 100%; opacity: 0; }
        }

        .aegis-card {
          font-family: 'Rajdhani', sans-serif;
        }

        .aegis-mono {
          font-family: 'Share Tech Mono', monospace;
        }

        .aegis-scan-container {
          position: relative;
          overflow: hidden;
        }

        .aegis-scan-container::after {
          content: '';
          position: absolute;
          top: -4px;
          left: 0;
          right: 0;
          height: 2px;
          background: linear-gradient(90deg, transparent, #7F77DD, transparent);
          animation: aegis-scan 4s ease-in-out infinite;
          pointer-events: none;
        }
      `}</style>

      <section className="aegis-card">
        {/* Section Header */}
        <div className="flex items-center gap-3 mb-4">
          <span
            className="aegis-mono text-xs tracking-[0.2em] font-bold"
            style={{ color: '#CCC9F8' }}
          >
            AEGIS STACK
          </span>
          <div className="flex-1 h-px" style={{ background: '#534AB7' }} />
          <span
            className="aegis-mono text-[10px] tracking-wider px-2 py-0.5 rounded border"
            style={{
              color: '#CCC9F8',
              borderColor: '#534AB7',
              background: '#26215C',
            }}
          >
            CLEARANCE: PUBLIC
          </span>
        </div>

        {/* Dossier Card */}
        <div
          className="aegis-scan-container rounded-lg p-4"
          style={{
            background: 'var(--eve-surface)',
            borderLeft: '2px solid #7F77DD',
            border: '1px solid var(--eve-border)',
            borderLeftWidth: '2px',
            borderLeftColor: '#7F77DD',
          }}
        >
          {/* Designation */}
          <div className="mb-1">
            <span className="aegis-mono text-[var(--eve-dim)] text-xs">
              DESIGNATION
            </span>
          </div>
          <h3
            className="aegis-mono text-lg tracking-wider mb-0.5"
            style={{ color: '#CCC9F8' }}
          >
            // MONOLITH
          </h3>
          <p
            className="text-xs tracking-[0.15em] font-semibold mb-3"
            style={{ color: '#7F77DD' }}
          >
            BLOCKCHAIN INTEGRITY MONITOR
          </p>

          {/* Clearance Badge */}
          <div className="mb-4">
            <span
              className="aegis-mono text-[10px] tracking-wider px-2 py-0.5 rounded border"
              style={{
                color: '#CCC9F8',
                borderColor: '#534AB7',
                background: '#26215C',
              }}
            >
              AEGIS-02 / ACTIVE
            </span>
          </div>

          {/* Summary */}
          <p className="text-sm leading-relaxed text-[var(--eve-text)] mb-5 max-w-2xl">
            Continuous chain surveillance for EVE Frontier on Sui. Detects state
            anomalies &mdash; orphaned objects, duplicate transactions, economic
            discrepancies &mdash; and generates structured bug reports with on-chain
            evidence. QA infrastructure for the Sui migration.
          </p>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 mb-5">
            {STATS.map((stat) => (
              <div
                key={stat.label}
                className="text-center py-2 rounded"
                style={{ background: 'rgba(127, 119, 221, 0.08)' }}
              >
                <div
                  className="aegis-mono text-base font-bold"
                  style={{ color: '#CCC9F8' }}
                >
                  {stat.value}
                </div>
                <div className="text-[10px] text-[var(--eve-dim)] tracking-wider font-semibold">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>

          {/* Tags */}
          <div className="flex flex-wrap gap-2 mb-4">
            {TAGS.map((tag) => (
              <span
                key={tag.label}
                className="aegis-mono text-[10px] tracking-wider px-2 py-0.5 rounded border"
                style={
                  tag.variant === 'live'
                    ? {
                        color: '#9FE1CB',
                        borderColor: '#1D9E75',
                        background: '#04342C',
                      }
                    : {
                        color: 'var(--eve-dim)',
                        borderColor: 'var(--eve-border)',
                        background: 'transparent',
                      }
                }
              >
                {tag.label}
              </span>
            ))}
          </div>

          {/* Access Link */}
          <div className="flex items-center gap-2">
            <span className="text-[var(--eve-dim)] text-xs">ACCESS</span>
            <a
              href="https://github.com/AreteDriver/monolith"
              target="_blank"
              rel="noopener noreferrer"
              className="aegis-mono text-xs hover:underline"
              style={{ color: '#7F77DD' }}
            >
              github.com/AreteDriver/monolith &rarr;
            </a>
          </div>
        </div>

        {/* Live Chain Integrity Feed from Monolith */}
        <div className="mt-4">
          <ChainIntegrity />
        </div>

        {/* Monolith Anomaly Feed */}
        {anomalies.length > 0 && (
          <div className="mt-4 rounded-lg p-4"
            style={{ background: 'var(--eve-surface)', borderLeft: '2px solid #7F77DD', border: '1px solid var(--eve-border)', borderLeftWidth: '2px', borderLeftColor: '#7F77DD' }}
          >
            <h3 className="aegis-mono text-[10px] uppercase tracking-[0.2em] font-bold mb-3"
              style={{ color: '#7F77DD' }}
            >
              Chain Integrity &mdash; Monolith ({anomalies.length})
            </h3>
            <div className="space-y-1.5">
              {anomalies.map((a) => {
                const sevColor = a.severity === 'CRITICAL' ? 'var(--eve-red)' :
                  a.severity === 'HIGH' ? '#f59e0b' : 'var(--eve-dim)';
                return (
                  <div key={a.anomaly_id} className="flex items-center justify-between text-xs py-0.5">
                    <div className="flex items-center gap-2">
                      <span className="aegis-mono font-bold" style={{ color: sevColor }}>
                        {a.severity}
                      </span>
                      <span className="text-[var(--eve-text)]">
                        {a.anomaly_type.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <span className="text-[var(--eve-dim)] aegis-mono text-[10px]">
                      {new Date(a.detected_at * 1000).toLocaleDateString()}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="text-[10px] text-[var(--eve-dim)] mt-2 opacity-60">
              Anomalies detected by Monolith integrity monitor
            </div>
          </div>
        )}
        {/* Monolith Bug Reports */}
        {bugReports.length > 0 && (
          <div className="mt-4 rounded-lg p-4"
            style={{ background: 'var(--eve-surface)', borderLeft: '2px solid #7F77DD', border: '1px solid var(--eve-border)', borderLeftWidth: '2px', borderLeftColor: '#7F77DD' }}
          >
            <h3 className="aegis-mono text-[10px] uppercase tracking-[0.2em] font-bold mb-3"
              style={{ color: '#7F77DD' }}
            >
              Bug Reports &mdash; Monolith ({bugReports.length})
            </h3>
            <div className="space-y-2">
              {bugReports.map((r) => {
                const sevColor = r.severity === 'CRITICAL' ? 'var(--eve-red)' :
                  r.severity === 'HIGH' ? '#f59e0b' :
                  r.severity === 'MEDIUM' ? 'var(--eve-orange)' : 'var(--eve-dim)';
                return (
                  <a
                    key={r.report_id}
                    href={`https://monolith-evefrontier.fly.dev/api/reports/${r.report_id}?fmt=markdown`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block px-3 py-2 rounded hover:opacity-80 transition-opacity"
                    style={{ background: 'rgba(127, 119, 221, 0.06)' }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="aegis-mono text-[10px] font-bold shrink-0" style={{ color: sevColor }}>
                          {r.severity}
                        </span>
                        <span className="text-xs text-[var(--eve-text)] truncate">
                          {r.title}
                        </span>
                      </div>
                      <span className="text-[var(--eve-dim)] aegis-mono text-[10px] shrink-0 ml-2">
                        {new Date(r.generated_at * 1000).toLocaleDateString()}
                      </span>
                    </div>
                    {r.summary && (
                      <div className="text-[10px] text-[var(--eve-dim)] mt-0.5 line-clamp-1">
                        {r.summary}
                      </div>
                    )}
                  </a>
                );
              })}
            </div>
            <div className="flex items-center justify-between mt-3 pt-2" style={{ borderTop: '1px solid var(--eve-border)' }}>
              <span className="text-[10px] text-[var(--eve-dim)] opacity-60">
                Auto-generated from on-chain evidence
              </span>
              <a
                href="https://github.com/AreteDriver/monolith/issues"
                target="_blank"
                rel="noopener noreferrer"
                className="aegis-mono text-[10px] hover:underline"
                style={{ color: '#7F77DD' }}
              >
                View GitHub Issues &rarr;
              </a>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
