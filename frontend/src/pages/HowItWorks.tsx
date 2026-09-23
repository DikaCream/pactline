import { REPO_URL, RAW_FIXTURE_URL } from "../config";

const STEPS = [
  {
    n: "1",
    title: "The buyer locks escrow and writes the terms",
    body: "The GEN goes into the contract, not to anyone. The terms are machine-checkable: exact strings the page must contain, counts, formats. Vague promises cannot be judged, so the form asks for terms a validator can verify from the work alone.",
  },
  {
    n: "2",
    title: "The seller delivers a public page",
    body: "Delivery points at a URL anyone on the internet can fetch. localhost and private addresses are rejected at the contract level, because a page only the seller can see can never be judged.",
  },
  {
    n: "3",
    title: "Anyone runs the review",
    body: "Review is permissionless and each run burns one of four rounds. Two validators independently fetch the deliverable and judge it strictly against the written terms. The deliverable and the seller note are fenced as untrusted: they are evidence, never instructions.",
  },
  {
    n: "4",
    title: "Equivalence before anything moves",
    body: "The two verdicts are equivalent only if both say PASS or both say FAIL. Error objects never count as verdicts. No agreement, no movement; the round is spent and another can run after a five minute cooldown.",
  },
  {
    n: "5",
    title: "The money moves by rule, not by request",
    body: "PASS pays the seller the escrow minus a 0.5% settlement fee, the only fee in the system. FAIL opens a three day window where the seller can stake the appeal bond once. A lost appeal pays the bond to the buyer and refunds the escrow fee-free. Every stuck path unwinds: nobody can abandon a deal and freeze the money.",
  },
];

const GUARANTEES = [
  {
    title: "Fees only on success",
    body: "Refunds, cancels, expiries, force-refunds, appeal settlements: all fee-free. The 0.5% exists to price a successful settlement, so a buyer never loses escrow value on a deal they did not get.",
  },
  {
    title: "Payouts capped by the deal's own escrow",
    body: "The contract pays from what that deal holds, never from other deals' funds. Each settled deal is asserted to the wei in the test suite, including the fee split.",
  },
  {
    title: "No state can trap the money",
    body: "Delivered but never reviewed: expiry after deadline + 6h. Failed with no bond: finalize at once. Failed with a bond: finalize after the window. Appealed but never re-reviewed: finalize unwinds it, bond back to the seller. Review rounds are bounded; a garbled model force-refunds instead of wedging.",
  },
  {
    title: "Appeals are single-shot and priced",
    body: "One bond, one re-review. The stake restarts the clock so a seller who stakes late still gets a full window, and a re-review outside the window is refused.",
  },
];

export function HowItWorks() {
  return (
    <div className="page narrow">
      <h1>How PactLine works</h1>
      <p className="lede">
        PactLine is an escrow that opens when a deliverable meets the written terms.
        Nothing here is a metaphor: every claim below points at a function in a
        deployed contract.
      </p>

      <ol className="steps">
        {STEPS.map((s) => (
          <li key={s.n} className="step">
            <i className="step-n mono">{s.n}</i>
            <div>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <h2>What the contract guarantees</h2>
      <div className="grid-two">
        {GUARANTEES.map((g) => (
          <div key={g.title} className="card">
            <h3>{g.title}</h3>
            <p>{g.body}</p>
          </div>
        ))}
      </div>

      <div className="read-box">
        <h2>Read the machine for yourself</h2>
        <ul className="link-list">
          <li>
            <a href={REPO_URL} target="_blank" rel="noreferrer">
              Read the full source tree ↗
            </a>
            <span>contract, tests, and this frontend, all public</span>
          </li>
          <li>
            <a href={RAW_FIXTURE_URL} target="_blank" rel="noreferrer">
              The escrow contract, exactly as deployed ↗
            </a>
            <span>contracts/pact_line.py — every guard lives in code</span>
          </li>
        </ul>
        <p className="mini-note">
          56 direct tests cover the state machine, and every guard was
          mutation-checked: disabled one at a time, the matching test failed, then
          restored. The StudioNet end-to-end moved 1 GEN of escrow to a seller on
          live consensus and walked the appeal path back.
        </p>
      </div>
    </div>
  );
}
