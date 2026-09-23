import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { usePactLine } from "../context/PactLineContext";
import { GEN, MIN_APPEAL_BOND, formatGen } from "../config";

const SAMPLE_TERMS = `Acceptance terms (all machine-checkable): the delivered page must
contain the exact marker string PACTLINE-001 and the exact phrase
'delivery accepted'. A page missing either string is a FAIL.`;

export function NewDeal() {
  const { run, busy, wallet } = usePactLine();
  const navigate = useNavigate();

  const [escrow, setEscrow] = useState("1");
  const [terms, setTerms] = useState(SAMPLE_TERMS);
  const [days, setDays] = useState("14");
  const [bond, setBond] = useState("0.1");
  const [localError, setLocalError] = useState<string | null>(null);

  const escrowWei = (() => {
    try {
      const f = parseFloat(escrow);
      if (!isFinite(f) || f <= 0) return 0n;
      return BigInt(Math.round(f * 1e6)) * (GEN / 1000000n);
    } catch {
      return 0n;
    }
  })();

  const bondWei = (() => {
    try {
      const f = parseFloat(bond);
      if (!isFinite(f) || f === 0) return 0n;
      return BigInt(Math.round(f * 1e6)) * (GEN / 1000000n);
    } catch {
      return 0n;
    }
  })();

  const deadlineSec = Math.floor(Date.now() / 1000) + Math.max(1, parseInt(days || "1", 10)) * 86400;

  async function submit() {
    setLocalError(null);
    if (escrowWei <= 0n) {
      setLocalError("The escrow must be a positive amount of GEN.");
      return;
    }
    if (terms.trim().length === 0 || terms.length > 4000) {
      setLocalError("The terms need 1 to 4000 characters.");
      return;
    }
    if (bondWei !== 0n && bondWei < MIN_APPEAL_BOND) {
      setLocalError("The appeal bond is below the 0.1 GEN minimum. Raise it or set it to zero.");
      return;
    }
    if (bondWei > escrowWei) {
      setLocalError("The appeal bond cannot exceed the escrow itself.");
      return;
    }
    const ok = await run("Funding the escrow", (c) =>
      c.createDeal(terms, deadlineSec, bondWei, escrowWei),
    );
    if (ok) navigate("/");
  }

  return (
    <div className="page narrow">
      <h1>Fund a deal</h1>
      <p className="lede">
        You lock the escrow now and write the acceptance terms. The money only leaves
        this contract when validators agree the delivered work meets the terms, or
        back to you, fee-free, if it does not.
      </p>

      {!wallet.address && (
        <div className="note">Connect a wallet to fund a deal. Reading needs no wallet.</div>
      )}

      <div className="form">
        <label className="field">
          <span>Escrow (GEN)</span>
          <input
            className="mono"
            value={escrow}
            onChange={(e) => setEscrow(e.target.value)}
            inputMode="decimal"
            placeholder="1"
          />
          <small>The full amount the seller can earn, held by the contract.</small>
        </label>

        <label className="field">
          <span>Acceptance terms</span>
          <textarea
            className="mono"
            rows={7}
            value={terms}
            onChange={(e) => setTerms(e.target.value)}
            maxLength={4000}
          />
          <small>
            Machine-checkable only: strings the page must contain, counts, formats.
            The validators judge the work against exactly this text.
          </small>
        </label>

        <div className="field-pair">
          <label className="field">
            <span>Deadline (days from now)</span>
            <input
              className="mono"
              value={days}
              onChange={(e) => setDays(e.target.value)}
              inputMode="numeric"
            />
            <small>Delivery must happen before this clock runs out.</small>
          </label>

          <label className="field">
            <span>Appeal bond (GEN, 0 to disable appeals)</span>
            <input
              className="mono"
              value={bond}
              onChange={(e) => setBond(e.target.value)}
              inputMode="decimal"
            />
            <small>
              The seller stakes this to challenge a FAIL. A lost appeal pays it to
              you; an overturned one returns it and settles the deal.
            </small>
          </label>
        </div>
      </div>

      {(localError || null) && <div className="note bad">{localError}</div>}

      <div className="cta-row">
        <button
          className="btn primary"
          onClick={submit}
          disabled={!!busy || !wallet.address}
        >
          {busy ? "Working…" : `Fund ${formatGen(escrowWei)} GEN escrow`}
        </button>
      </div>
    </div>
  );
}
