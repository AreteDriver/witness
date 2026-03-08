import type { ReactNode } from 'react';
import { useAuth, TIER_LABELS } from '../contexts/AuthContext';

interface TierGateProps {
  requiredTier: number;
  children: ReactNode;
  featureName?: string;
}

export function TierGate({ requiredTier, children, featureName }: TierGateProps) {
  const { wallet, subscription } = useAuth();
  const currentTier = subscription?.tier ?? 0;

  if (wallet && subscription?.active && currentTier >= requiredTier) {
    return <>{children}</>;
  }

  const needed = TIER_LABELS[requiredTier] || TIER_LABELS[1];

  return (
    <div className="relative">
      <div className="opacity-20 pointer-events-none select-none blur-[2px]">
        {children}
      </div>
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="bg-[var(--eve-bg)]/90 border border-[var(--eve-border)] rounded-lg
                        px-4 py-3 text-center space-y-1 max-w-xs">
          <div className="text-xs font-bold" style={{ color: needed.color }}>
            {needed.name} Tier Required
          </div>
          <div className="text-[10px] text-[var(--eve-dim)]">
            {!wallet
              ? 'Connect your wallet to access this feature.'
              : featureName
                ? `${featureName} requires ${needed.name} tier or higher.`
                : `This feature requires ${needed.name} tier or higher.`}
          </div>
        </div>
      </div>
    </div>
  );
}
