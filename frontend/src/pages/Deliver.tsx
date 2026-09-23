import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { usePactLine } from "../context/PactLineContext";
import { formatGen, hostOf } from "../config";
import { Deal } from "../lib/types";

export function Deliver() {
  const { id } = useParams();
  const dealId = parseInt(id || "0", 10);
  const { read, run, busy, wallet } = usePactLine();
  const navigate = useNavigate();

  const [deal, setDeal] = useState<Deal | null>(null);
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

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
  }, [read, dealId, busy]);

  async function submit() {
    setLocalError(null);
    const u = url.trim();
    if (u.length === 0 || u.length > 500) {
      setLocalError("The deliverable URL needs 1 to 500 characters.");
      return;
    }
    if (!/^https?:\/\//i.test(u)) {
      setLocalError("The URL must be a public http(s) page.");
      return;
    }
    if (note.length > 500) {
      setLocalError("Keep the seller note under 500 characters.");
      return;
    }
    const ok = await run("Delivering the work", (c) =>
      c.acceptAndDeliver(dealId, u, note),
    );
    if (ok) navigate(`/deals/${dealId}`);
  }

  if (loadError) return <div className="page narrow"><div className="note bad">{loadError}</div></div>;
  if (!deal) return <div className="page narrow"><div className="empty">Reading the deal…</div></div>;
  if (deal.status !== "CREATED") {
    return (
      <div className="page narrow">
        <div className="note">
          This deal is no longer open for delivery. Its state now: {deal.status}.
        </div>
      </div>
    );
  }

  return (
    <div className="page narrow">
      <h1>Take deal #{deal.id}</h1>
      <p className="lede">
        Deliver by pointing at a public page of finished work. The validators fetch
        that page themselves, so it must be reachable by anyone on the internet:
        localhost and private addresses are rejected.
      </p>

      <div className="deal-facts">
        <div><span>Escrow</span><b className="mono">{formatGen(deal.amount)} GEN</b></div>
        <div><span>Appeal bond</span><b className="mono">{formatGen(deal.appealBond)} GEN</b></div>
        <div><span>Fee on success</span><b className="mono">0.5%</b></div>
      </div>

      <div className="terms-box">
        <h3>Acceptance terms you must meet</h3>
        <pre className="mono">{deal.terms}</pre>
      </div>

      {!wallet.address && <div className="note">Connect a wallet to deliver.</div>}

      <div className="form">
        <label className="field">
          <span>Deliverable URL (public)</span>
          <input
            className="mono"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://…"
          />
          <small>{url ? `The validators will fetch: ${hostOf(url)}` : "One page that shows the finished work."}</small>
        </label>

        <label className="field">
          <span>Seller note (optional)</span>
          <textarea
            className="mono"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={500}
            placeholder="One line of context for the reviewers."
          />
          <small>Context only, never a substitute for the work itself.</small>
        </label>
      </div>

      {(localError || null) && <div className="note bad">{localError}</div>}

      <div className="cta-row">
        <button className="btn primary" onClick={submit} disabled={!!busy || !wallet.address}>
          {busy ? "Working…" : "Deliver this page"}
        </button>
      </div>
    </div>
  );
}
