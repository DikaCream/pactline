import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { createPactLineClient } from "../lib/client";
import { PactLine } from "../lib/contract";
import { DealSummary, Stats } from "../lib/types";
import { describeError } from "../lib/errors";
import { useWallet } from "../hooks/useWallet";

const EMPTY_STATS: Stats = {
  deals: 0,
  settledCount: 0,
  settledAmount: 0n,
  fees: 0n,
  appeals: 0,
  overturned: 0,
  payouts: 0n,
  escrow: 0n,
};

interface PactLineCtx {
  wallet: ReturnType<typeof useWallet>;
  read: PactLine;
  deals: DealSummary[];
  stats: Stats;
  loading: boolean;
  error: string | null;
  busy: string | null;
  txError: string | null;
  lastTx: string | null;
  version: number;
  refresh: () => void;
  dismissTx: () => void;
  run: (label: string, fn: (c: PactLine) => Promise<string>) => Promise<boolean>;
}

const Ctx = createContext<PactLineCtx | null>(null);

export function PactLineProvider({ children }: { children: ReactNode }) {
  const wallet = useWallet();
  const [deals, setDeals] = useState<DealSummary[]>([]);
  const [stats, setStats] = useState<Stats>(EMPTY_STATS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [txError, setTxError] = useState<string | null>(null);
  const [lastTx, setLastTx] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  const readClient = useMemo(() => new PactLine(createPactLineClient()), []);
  const writeClient = useMemo(
    () => new PactLine(createPactLineClient(wallet.address)),
    [wallet.address],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [d, s] = await Promise.all([
        readClient.listDeals(0, 50, false),
        readClient.getStats(),
      ]);
      setDeals(d);
      setStats(s);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }, [readClient]);

  useEffect(() => {
    load();
  }, [load, version]);

  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  const run = useCallback(
    async (label: string, fn: (c: PactLine) => Promise<string>) => {
      setBusy(label);
      setTxError(null);
      setLastTx(null);
      try {
        const txHash = await fn(writeClient);
        await writeClient.waitForReceipt(txHash);
        setLastTx(txHash);
        refresh();
        return true;
      } catch (e) {
        setTxError(describeError(e));
        return false;
      } finally {
        setBusy(null);
      }
    },
    [writeClient, refresh],
  );

  const dismissTx = useCallback(() => setTxError(null), []);

  const value: PactLineCtx = {
    wallet,
    read: readClient,
    deals,
    stats,
    loading,
    error,
    busy,
    txError,
    lastTx,
    version,
    refresh,
    dismissTx,
    run,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePactLine(): PactLineCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("usePactLine must be used inside PactLineProvider");
  return ctx;
}
