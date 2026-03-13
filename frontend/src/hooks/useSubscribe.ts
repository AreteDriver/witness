import { useState } from 'react';
import { useSignAndExecuteTransaction } from '@mysten/dapp-kit';
import { Transaction } from '@mysten/sui/transactions';

const WATCHTOWER_PACKAGE = '0x3ca7e3af5bf5b072157d02534f5e4013cf11a12b79385c270d97de480e7b7dca';
const SUBSCRIPTION_CONFIG = '0x7bd0e266d3c26665b13c432f70d9b7e5ecc266de993094f8ac8290020283be9d';
const SUBSCRIPTION_REGISTRY = '0x4bb5a6999fadd2039b8cfcb7a1b3de0f07973fe0ec74181b024edaaa6069d160';
const SUI_CLOCK = '0x6';

export function useSubscribe() {
  const { mutateAsync: signAndExecute } = useSignAndExecuteTransaction();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const subscribe = async (tier: 1 | 2 | 3, suiMist: bigint) => {
    setLoading(true);
    setError('');
    try {
      const tx = new Transaction();
      const [payment] = tx.splitCoins(tx.gas, [suiMist]);

      tx.moveCall({
        target: `${WATCHTOWER_PACKAGE}::subscription::subscribe`,
        arguments: [
          tx.object(SUBSCRIPTION_CONFIG),
          tx.object(SUBSCRIPTION_REGISTRY),
          tx.pure.u8(tier),
          payment,
          tx.object(SUI_CLOCK),
        ],
      });

      const result = await signAndExecute({ transaction: tx });
      return result;
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Transaction failed';
      setError(msg);
      throw e;
    } finally {
      setLoading(false);
    }
  };

  const renew = async (capId: string, suiMist: bigint) => {
    setLoading(true);
    setError('');
    try {
      const tx = new Transaction();
      const [payment] = tx.splitCoins(tx.gas, [suiMist]);

      tx.moveCall({
        target: `${WATCHTOWER_PACKAGE}::subscription::renew`,
        arguments: [
          tx.object(SUBSCRIPTION_CONFIG),
          tx.object(SUBSCRIPTION_REGISTRY),
          tx.object(capId),
          payment,
          tx.object(SUI_CLOCK),
        ],
      });

      const result = await signAndExecute({ transaction: tx });
      return result;
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Transaction failed';
      setError(msg);
      throw e;
    } finally {
      setLoading(false);
    }
  };

  return { subscribe, renew, loading, error };
}
