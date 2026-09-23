import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { usePactLine } from "../context/PactLineContext";
import { DealLamp } from "../components/Chrome";
import {
  APPEAL_WINDOW,
  DEADLINE_SLACK,
  EXPLORER_ADDR,
  MIN_APPEAL_BOND,
  formatClock,
  formatGen,
  hexAddr,
  hostOf,
  untilClock,
} from "../config";
import { Deal, STATUS_LABEL } from "../lib/types";

function sameAddr(a: string | null | undefined, b: string | null | undefined): boolean {
  if (!a || !b) return false;
  return hexAddr(a).toLowerCase() === hexAddr(b).toLowerCase();
}

export function DealPage() {
  const { id } = useParams();
  const dealId = parseInt(id || "0", 10);
  const { read, run, busy, wallet, version } = usePactLine();
  const [deal, setDeal] = useState<Deal | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const nowSec = Math.floor(Date.now() / 1000);

  useEffect(() => {
    let alive = true;
    read.getDeal(dealId).then((d) => {
      if (!alive) return;
      if (!d) setLoadError("That deal does not exist on this escrow.");
      else setDeal(d);
    });
    return () => {
      alive = false;
    };
  }, [read, dealId, version]);

  if (loadError) return <div className="page narrow"><div className="note bad">{loadError}</div></div>;
  if (!deal) return <div className="page narrow"><div className="empty">Reading the deal…</div></div>;

  const me = wallet.address;
  const isBuyer = sameAddr(me, deal.buyer);
  const isSeller = sameAddr(me, deal.seller);
  const netToSeller = (deal.amount * 199n) / 200n;
  const slackOver = deal.deadline > 0 && deal.deadline + DEADLINE_SLACK < nowSec;
  const appealClosesAt = deal.verdictAt + APPEAL_WINDOW;

  async function action(label: string, fn: (c: any) => Promise<string>) {
    await run(label, fn);
  }

  return (
    <div className="page narrow">
      <div className="deal-top">
        <h1>Deal #{deal.id}</h1>
        <DealLamp status={deal.status} />
      </div>

      <div className="deal-facts">
        <div>
          <span>Escrow</span>
          <b className="mono">{formatGen(deal.amount)} GEN</b>
        </div>
        <div>
          <span>Seller receives on PASS</span>
          <b className="mono">{formatGen(netToSeller)} GEN</b>
        </div>
        <div>
          <span>Appeal bond</span>
          <b className="mono">{deal.appealBond === 0n ? "none" : `${formatGen(deal.appealBond)} GEN`}</b>
        </div>
        <div>
          <span>Deadline</span>
          <b>{formatClock(deal.deadline)}</b>
        </div>
        <div>
          <span>Buyer</span>
          <b>
            <a className="mono" href={EXPLORER_ADDR(hexAddr(deal.buyer))} target="_blank" rel="noreferrer">
              {hexAddr(deal.buyer).slice(0, 6)}…{hexAddr(deal.buyer).slice(-4)}
              {isBuyer ? " (you)" : ""}
            </a>
          </b>
        </div>
        <div>
          <span>Seller</span>
          <b>
            {deal.hasSeller ? (
              <a className="mono" href={EXPLORER_ADDR(hexAddr(deal.seller))} target="_blank" rel="noreferrer">
                {hexAddr(deal.seller).slice(0, 6)}…{hexAddr(deal.seller).slice(-4)}
                {isSeller ? " (you)" : ""}
              </a>
            ) : (
              "none yet"
            )}
          </b>
        </div>
      </div>

      <div className="terms-box">
        <h3>Acceptance terms</h3>
        <pre className="mono">{deal.terms}</pre>
      </div>

      {deal.hasSeller && (
        <div className="delivery-box">
          <h3>The delivered work</h3>
          <p>
            <a href={deal.deliverableUrl} target="_blank" rel="noreferrer" className="mono">
              {hostOf(deal.deliverableUrl)} ↗
            </a>
          </p>
          {deal.sellerReason && <blockquote>{deal.sellerReason}</blockquote>}
        </div>
      )}

      {deal.verdict && (
        <div className={`verdict ${deal.verdict === "PASS" ? "pass" : "fail"}`}>
          <b>{deal.verdict}</b>
          <span>{deal.reasoning || "No reasoning recorded."}</span>
        </div>
      )}

      {deal.rounds > 0 && !deal.isTerminal && (
        <p className="mini-note mono">Review attempts used: {deal.rounds} of 4</p>
      )}

      {/* ---------------- actions by state ---------------- */}
      {deal.status === "CREATED" && (
        <div className="actions">
          <Link className="btn primary" to={`/deals/${deal.id}/deliver`}>
            Take this deal
          </Link>
          {isBuyer && (
            <button
              className="btn ghost"
              disabled={!!busy}
              onClick={() => action("Canceling the deal", (c) => c.buyerCancel(deal.id))}
            >
              Cancel and take the escrow back
            </button>
          )}
          {slackOver && !isBuyer && (
            <button
              className="btn ghost"
              disabled={!!busy}
              onClick={() => action("Expiring the deal", (c) => c.expire(deal.id))}
            >
              Expire: the deadline passed untaken
            </button>
          )}
        </div>
      )}

      {deal.status === "DELIVERED" && (
        <div className="actions">
          <button
            className="btn primary"
            disabled={!!busy}
            onClick={() => action("Running the review", (c) => c.runReview(deal.id))}
          >
            Run the review
          </button>
          <p className="mini-note">
            The validators fetch the delivered page themselves and must both land on
            the same verdict.            PASS pays the seller {formatGen(netToSeller)} GEN; FAIL opens an
            appeal window for the seller.
          </p>
        </div>
      )}

      {deal.status === "FAILED" && (
        <div className="actions">
          {deal.appealBond > 0n && deal.secondsToAppealClose > 0 && (
            <>
              {isSeller ? (
                <button
                  className="btn primary"
                  disabled={!!busy || !wallet.address}
                  onClick={() => action("Staking the appeal", (c) => c.appeal(deal.id, MIN_APPEAL_BOND))}
                >
                  Appeal: stake {formatGen(deal.appealBond)} GEN and get re-reviewed
                </button>
              ) : (
                <p className="mini-note">
                  The seller can stake {formatGen(deal.appealBond)} GEN to challenge
                  this verdict until {formatClock(appealClosesAt)} (
                  {untilClock(appealClosesAt, nowSec)}).
                </p>
              )}
              <button
                className="btn ghost"
                disabled={!!busy || deal.secondsToAppealClose > 0}
                onClick={() => action("Finalizing the refund", (c) => c.finalize(deal.id))}
              >
                {deal.secondsToAppealClose > 0
                  ? `Refund unlocks in ${untilClock(appealClosesAt, nowSec)}`
                  : "Finalize: refund the buyer, fee-free"}
              </button>
            </>
          )}
          {deal.appealBond === 0n && (
            <button
              className="btn primary"
              disabled={!!busy}
              onClick={() => action("Finalizing the refund", (c) => c.finalize(deal.id))}
            >
              Finalize: refund the buyer, fee-free
            </button>
          )}
        </div>
      )}

      {deal.status === "APPEALED" && (
        <div className="actions">
          {deal.secondsToAppealClose > 0 ? (
            <>
              <button
                className="btn primary"
                disabled={!!busy}
                onClick={() => action("Running the re-review", (c) => c.runReview(deal.id))}
              >
                Run the re-review
              </button>
              <p className="mini-note">
                The seller staked {formatGen(deal.appealStaked)} GEN to challenge the
                FAIL. A PASS overturns it: the bond goes back and the deal settles.
                A FAIL stands: the bond pays the buyer and the escrow refunds
                fee-free. Window closes {formatClock(appealClosesAt)} (
                {untilClock(appealClosesAt, nowSec)}).
              </p>
            </>
          ) : (
            <button
              className="btn primary"
              disabled={!!busy}
              onClick={() => action("Finalizing the appeal", (c) => c.finalize(deal.id))}
            >
              Finalize: window passed, unwind the appeal
            </button>
          )}
        </div>
      )}

      {deal.isTerminal && (
        <div className="actions">
          <p className="mini-note">
            This deal is closed: {STATUS_LABEL[deal.status] ?? deal.status}.
            {deal.status === "SETTLED" &&
              ` The seller was paid ${formatGen(netToSeller)} GEN; the 0.5% settlement fee covered the review.`}
            {(deal.status === "REFUNDED" || deal.status === "CANCELED" || deal.status === "EXPIRED") &&
              " The escrow went back to the buyer in full; refunds carry no fee."}
          </p>
        </div>
      )}

      <p className="foot-note mono">
        Fee 0.5% on success only · refunds and appeals never charge a fee · every
        payout is capped by this deal's own escrow.
      </p>
    </div>
  );
}
