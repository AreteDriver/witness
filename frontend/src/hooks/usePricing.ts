import { useEffect, useState } from 'react';
import { api } from '../api';

export interface TierPricing {
  usd_per_week: number;
  sui_per_week: number;
  sui_mist: number;
  tier: number;
}

export interface PricingData {
  sui_usd: number;
  fetched_at: string;
  is_stale: boolean;
  tiers: Record<string, TierPricing>;
}

export function usePricing() {
  const [pricing, setPricing] = useState<PricingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchPricing = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await api.getPricing();
      setPricing(data);
    } catch (e) {
      setError('Failed to fetch pricing');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPricing();
  }, []);

  return { pricing, loading, error, refetch: fetchPricing };
}
