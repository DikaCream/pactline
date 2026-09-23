# PactLine

Escrow that opens when a deliverable meets the written terms. A buyer locks GEN into the contract and writes machine-checkable acceptance terms. A seller takes the deal and delivers a public page of finished work. Validators fetch that page themselves, judge it strictly against the terms, and both must land on the same verdict before a single wei moves. No marketplace operator, no arbitration desk, no office hours.

It runs on [GenLayer](https://genlayer.com), so the verdict itself is consensus output. The deliverable page is an input, never an authority: the validators read the same public bytes anyone on the internet would see, and the equivalence principle refuses to write anything until their verdicts match.

## Try it

- App: https://dikacream.github.io/pactline/ (routes like `/#/deals/1`, `/#/new`, `/#/how`)
- Escrow contract on StudioNet: `0xD5Efa2b53B8C60AcB1A742e42f2cb22AC68ff953`
- Repo: https://github.com/DikaCream/pactline

The seeded board carries every state at once:

- **Deal 1 — SETTLED.** Consensus PASS moved 1 GEN of escrow to the seller on-chain; the 0.5% settlement fee came off the top.
- **Deal 2 — DELIVERED.** A good page, review not run yet. Anyone can click **Run the review** in the app and watch validators fetch the page, agree, and move the money.
- **Deal 3 — CREATED.** Funded and open. Any wallet can deliver against its terms.
- **Deal 4 — FAILED.** A placeholder page failed review with no appeal bond, so the buyer can finalize the fee-free refund immediately.

## How the machine works

1. **Fund.** The buyer locks escrow and writes the acceptance terms. Terms must be machine-checkable: exact strings, counts, formats. Vague promises cannot be judged.
2. **Deliver.** The seller points at a public http(s) page. The contract rejects localhost and private-range URLs at delivery time: a page only the seller can see can never be judged.
3. **Review.** Permissionless. Each run burns one of four rounds per deal. Two validators independently fetch the deliverable and judge it strictly against the written terms. The deliverable and the seller note are fenced as untrusted evidence, never instructions.
4. **Equivalence.** The two verdicts are equivalent only if both say PASS or both say FAIL. Error objects are equivalent only to other error objects. No agreement, no movement; the round is spent and the next run waits a five minute cooldown.
5. **Settle.** PASS pays the seller escrow minus a 0.5% settlement fee, the only fee in the system. FAIL opens a three day appeal window.
6. **Appeal.** The seller stakes the deal's bond once. The stake restarts the window so a late staker still gets a full window to re-review inside it. Overturned: the bond returns and the deal settles. Upheld: the bond pays the buyer and the escrow refunds fee-free.
7. **Nothing sticks.** Delivered but never reviewed: expiry after deadline + 6h grace. Failed with no bond: finalize at once. Failed with a bond: finalize after the window. Appealed but never re-reviewed: finalize unwinds it, bond back to the seller. A model that keeps returning verdict-less output burns rounds to the same force-refund as an unreadable page.

## Design rules enforced in code, not by the model

- State moves forward only; terminal states accept nothing.
- Every payout is capped by the deal's own escrow.
- Refunds, cancels, expiries, force-refunds and appeal settlements are fee-free. The 0.5% exists to price successful settlement, so a buyer never loses escrow value on a deal they did not get.
- Appeal bonds are single-shot and bounded; review rounds are bounded; the cooldown gates retries.
- Force-refund paths always return a staked bond before the escrow leaves.

## The contract

`contracts/pact_line.py` is the whole machine: state machine, review prompt with injection fencing, equivalence check, escrow accounting, and the exit paths. The demo terms in the app are deliberately mechanical ("the page must contain the exact marker string X and the phrase 'delivery accepted'") so a reader can re-run the judgment themselves in seconds.

## Tests

56 direct tests cover the state machine exhaustively in a local VM with mocked validators: `tests/direct/test_pact_line.py`.

Every guard was mutation-checked: disabled one at a time, the matching test failed, then restored. 15/15 mutations killed.

Run them:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/direct/test_pact_line.py -q
```

The StudioNet integration run is `tests/e2e_pact_line.py`:

```bash
gltest --network studionet tests/e2e_pact_line.py -v -s
```

It deploys a fresh PactLine, walks a deal to consensus PASS (the seller is paid net of fee on-chain), then walks a second deal through FAIL, appeal, a fixed deliverable page, an overturned re-review, and settles, asserting the full accounting: 2 settles, 1 appeal overturned, bond returned, fees exact, escrow at zero.

The board seed is `tests/deploy_seed_pactline.py` (same runner shape):

```bash
gltest --network studionet tests/deploy_seed_pactline.py -v -s
```

## Frontend

`frontend/` is a Vite + React app on the same primitives as the contract: fund a deal, take and deliver one, run reviews, stake appeals, finalize. Pages: board, deal detail with state-specific actions, funding, delivery, and how-it-works.

```bash
cd frontend && npm install && npm run dev
```

Deployed to GitHub Pages from `.github/workflows/deploy.yml` on every push to `main` that touches `frontend/`.

## Contract constants

| Constant | Value | Meaning |
|---|---|---|
| `FEE_NUM / FEE_DEN` | 1 / 200 | 0.5% settlement fee, success path only |
| `APPEAL_WINDOW` | 3 days | seller window to stake and re-review |
| `REVIEW_COOLDOWN` | 5 min | minimum spacing between review runs |
| `MAX_ROUNDS` | 4 | review rounds before force-refund |
| `MIN_APPEAL_BOND` | 0.1 GEN | minimum bond a deal may require |
| `DEADLINE_SLACK` | 6 h | grace before an unreviewed delivery can expire |

## License

MIT.
