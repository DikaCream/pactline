import { Link } from "react-router-dom";
import { usePactLine } from "../context/PactLineContext";
import { DealLamp } from "../components/Chrome";
import { CONTRACT_ADDRESS, EXPLORER_ADDR, formatGen, untilClock } from "../config";
import { DealSummary } from "../lib/types";

function nextAction(d: DealSummary): string {
  switch (d.status) {
    case "CREATED":
      return "Take the deal";
    case "DELIVERED":
      return "Run the review";
    case "FAILED":
      return d.verdict === "FAIL" ? "Appeal or finalize" : "Finalize";
    case "APPEALED":
      return "Re-review pending";
    default:
      return "Closed";
  }
}

export function Board() {
  const { deals, stats, loading, error } = usePactLine();
  const nowSec = Math.floor(Date.now() / 1000);

  return (
    <div className="page">
      <section className="hero">
        <h1>Every deal on the line, in one ledger</h1>
        <p>
          A buyer locks escrow and writes the acceptance terms. A seller delivers a
          public page of finished work. Validators fetch the page themselves and must
          agree on the verdict before a single wei moves.
        </p>
      </section>

      <section className="stats-row" aria-label="Escrow totals">
        <div className="stat">
          <i className="stat-num mono">{formatGen(stats.escrow)}</i>
          <span>GEN held in escrow</span>
        </div>
        <div className="stat">
          <i className="stat-num mono">{formatGen(stats.settledAmount)}</i>
          <span>GEN earned by sellers</span>
        </div>
        <div className="stat">
          <i className="stat-num mono">{formatGen(stats.fees)}</i>
          <span>GEN in settlement fees</span>
        </div>
        <div className="stat">
          <i className="stat-num mono">{stats.overturned}</i>
          <span>appeals overturned the first verdict</span>
        </div>
      </section>

      <section className="board-head">
        <h2>Deals</h2>
        <Link className="btn primary" to="/new">
          Fund a deal
        </Link>
      </section>

      {loading && <div className="empty">Reading the escrow…</div>}
      {error && !loading && <div className="empty bad">Could not read the escrow: {error}</div>}
      {!loading && !error && deals.length === 0 && (
        <div className="empty">
          No deal stands on the ledger yet. Fund the first one.
        </div>
      )}

      <div className="deal-list">
        {deals.map((d) => (
          <Link to={`/deals/${d.id}`} key={d.id} className="deal-row">
            <span className="deal-id mono">#{d.id}</span>
            <DealLamp status={d.status} />
            <span className="deal-amount mono">{formatGen(d.amount)} GEN</span>
            <span className="deal-parties mono">
              {d.hasSeller ? "taken" : "open"} · ends {untilClock(d.deadline, nowSec)}
            </span>
            <span className="deal-action">{nextAction(d)}</span>
          </Link>
        ))}
      </div>

      <p className="foot-note mono">
        Escrow contract:{" "}
        <a href={EXPLORER_ADDR(CONTRACT_ADDRESS)} target="_blank" rel="noreferrer">
          {CONTRACT_ADDRESS.slice(0, 8)}…{CONTRACT_ADDRESS.slice(-5)}
        </a>{" "}
        on GenLayer StudioNet
      </p>
    </div>
  );
}
