import { usePactLine } from "../context/PactLineContext";
import { EXPLORER_TX, formatGen, shortAddr } from "../config";
import { DealStatus, STATUS_LABEL as STATUS_LABELS } from "../lib/types";

const LAMP_TONE: Record<string, string> = {
  CREATED: "open",
  DELIVERED: "ready",
  FAILED: "failed",
  APPEALED: "appealed",
  SETTLED: "paid",
  REFUNDED: "returned",
  CANCELED: "returned",
  EXPIRED: "returned",
};

export function WalletButton() {
  const { wallet } = usePactLine();

  if (!wallet.hasProvider) {
    return (
      <a
        className="btn ghost small"
        href="https://metamask.io/download/"
        target="_blank"
        rel="noreferrer"
      >
        Install a wallet
      </a>
    );
  }

  if (wallet.address) {
    return (
      <span className="wallet-chip" title={wallet.address}>
        <span className="mono">{formatGen(wallet.balance)} GEN</span>
        <span className="mono addr">{shortAddr(wallet.address)}</span>
      </span>
    );
  }

  return (
    <button className="btn primary small" onClick={wallet.connect} disabled={wallet.busy}>
      {wallet.busy ? "Connecting…" : "Connect wallet"}
    </button>
  );
}

export function DealLamp({ status }: { status: DealStatus }) {
  const tone = LAMP_TONE[status] ?? "open";
  return (
    <span className="lamp" title={STATUS_LABELS[status] ?? status}>
      <i className={`lamp-dot ${tone}`} aria-hidden="true" />
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

export function TxBanner() {
  const { txError, lastTx, dismissTx } = usePactLine();
  if (!txError && !lastTx) return null;
  return (
    <div className={`banner ${txError ? "bad" : "good"}`} role="status">
      <span>{txError ?? "The transaction landed."}</span>
      {lastTx && !txError && (
        <a href={EXPLORER_TX(lastTx)} target="_blank" rel="noreferrer" className="mono">
          {shortAddr(lastTx)}
        </a>
      )}
      <button className="x" onClick={dismissTx} aria-label="Dismiss">
        ×
      </button>
    </div>
  );
}

export function BusyLine() {
  const { busy } = usePactLine();
  if (!busy) return null;
  return <div className="busy-line">{busy}… waiting for the network</div>;
}
