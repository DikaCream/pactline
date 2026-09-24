# PactLine

Escrow that opens when a deliverable meets the written terms. A buyer locks GEN into the contract and writes acceptance terms a machine can check. A seller takes the deal and delivers a public page of finished work. Validators fetch that page themselves and judge it strictly against the terms. Both validators must land on the same verdict before a single wei moves. There is no operator in the middle and no arbitration desk.

It runs on [GenLayer](https://genlayer.com), so the verdict itself is consensus output. The deliverable page is an input, never an authority. Validators read the same public bytes anyone on the internet would see, and the equivalence principle refuses to write anything until their verdicts match.

## Try it

- App: https://pactline-rouge.vercel.app (routes like `/#/deals/1`, `/#/new`, `/#/how`)
- Mirror: https://dikacream.github.io/pactline/
- Escrow contract on StudioNet: `0xD5Efa2b53B8C60AcB1A742e42f2cb22AC68ff953`
- Repo: https://github.com/DikaCream/pactline

The seeded board carries every state at once. Stats at the time of writing: 7 deals, 3 appeals, 0 overturned, 3.195 GEN paid out, 4 GEN still in escrow, 0.005 GEN collected in fees.

- **Deal 1, SETTLED.** A consensus PASS moved 1 GEN of escrow to the seller on chain. The 0.5% settlement fee came off the top.
- **Deal 2, DELIVERED.** A good page is up and the review has not run yet. Anyone can run the review from the deal page and watch validators fetch it, agree, and move the money.
- **Deal 3, CREATED.** Funded and open. Any wallet can deliver against its terms.
- **Deal 4, FAILED.** A placeholder page failed review with no appeal bond, so the buyer can finalize the refund right away. Refunds carry no fee.
- **Deal 5, REFUNDED.** The placeholder failed, the seller staked the 0.1 GEN bond, the second review said FAIL again. The bond paid the buyer and the escrow refunded with no fee. The accounting was asserted per wei on chain.
- **Deal 6, REFUNDED** the same way through an upheld appeal run against the live board. Proof tx: `0xa47d9eec6bfff3aa34f64cf9d8d086cbef37d7a41fbeb05db3ee3183238f5c4b`. Payouts rose by exactly bond plus escrow and the deal ended in REFUNDED.
- **Deal 7, APPEALED, staged for you.** The seller staked the bond and the placeholder page is still up. Run the review again and the verdict stays FAIL, so the bond moves to the buyer live. If nobody runs it, anyone can finalize after the three day window and the bond goes back to the seller instead.

## How the machine works

1. **Fund.** The buyer locks escrow and writes the acceptance terms. Terms must be checkable by a machine: exact strings, counts, formats. Vague promises cannot be judged.
2. **Deliver.** The seller points at a public http(s) page. The contract rejects localhost and private range URLs at delivery time. A page only the seller can see can never be judged.
3. **Review.** Permissionless. Each run burns one of four rounds per deal. Two validators fetch the deliverable on their own and judge it strictly against the written terms. The deliverable and the seller note are treated as untrusted evidence, never as instructions.
4. **Equivalence.** The verdicts agree only if both say PASS or both say FAIL. Error objects count as agreement only with other error objects. With no agreement nothing moves: the round is spent and the next run waits five minutes.
5. **Settle.** A PASS pays the seller the escrow minus a 0.5% settlement fee, the only fee in the system. A FAIL opens a three day appeal window.
6. **Appeal.** The seller stakes the deal bond once. The stake restarts the window, so a late staker still gets the full window to run the second review inside it. If that review overturns, the bond returns and the deal settles. If it upholds, the bond pays the buyer and the escrow refunds with no fee.
7. **Nothing gets stuck.** A delivered deal nobody reviews expires after the deadline plus six hours of grace. A failed deal with no bond finalizes at once. A failed deal with a bond finalizes after the window. An appealed deal never reviewed again is unwound by finalize and the bond goes back to the seller. A model that keeps returning no verdict burns rounds down to the same force refund as an unreadable page.

## Design rules enforced in code, not by the model

- State moves forward only. Terminal states accept nothing.
- Every payout is capped by the deal escrow.
- Refunds, cancels, expiries, force refunds and appeal settlements carry no fee. The 0.5% fee prices successful settlement, so a buyer never loses escrow value on a deal they did not get.
- Appeal bonds are single shot and bounded. Review rounds are bounded. The cooldown gates retries.
- Force refund paths always return a staked bond before the escrow leaves.

## The contract

`contracts/pact_line.py` is the whole machine: the state machine, the review prompt with injection fencing, the equivalence check, the escrow accounting, and every exit path. The demo terms in the app are deliberately mechanical: the page must contain an exact marker string and the phrase "delivery accepted", so a reader can rerun the judgment in seconds.

## Tests

56 direct tests cover the state machine in a local VM with mocked validators: `tests/direct/test_pact_line.py`.

Every guard was mutation checked: each guard was disabled one at a time, the matching test failed, then the guard came back. 15 of 15 mutations killed.

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

It deploys a fresh PactLine and walks one deal to a consensus PASS, where the seller is paid net of fee on chain. Then it walks a second deal through a FAIL, an appeal, a fixed deliverable page, and an overturned re-review, asserting the full accounting: 2 settles, 1 appeal overturned, bond returned, exact fees, escrow at zero.

The board seed is `tests/deploy_seed_pactline.py` with the same runner shape. It appends the appeal upheld arc and the staged appeal from `tests/seed_appeal_upheld.py`:

```bash
gltest --network studionet tests/deploy_seed_pactline.py -v -s
```

## Frontend

`frontend/` is a Vite + React app on the same primitives as the contract. Fund a deal, take and deliver one, run reviews, stake appeals, finalize. Pages: board, deal detail with actions per state, funding, delivery, and how it works.

```bash
cd frontend && npm install && npm run dev
```

The app is deployed on Vercel at https://pactline-rouge.vercel.app. GitHub Pages mirrors the same build from `.github/workflows/deploy.yml` on every push to `main` that touches `frontend/`.

## Contract constants

- `FEE_NUM / FEE_DEN`: 1 / 200. The 0.5% settlement fee, success path only.
- `APPEAL_WINDOW`: 3 days. The seller window to stake and run the second review.
- `REVIEW_COOLDOWN`: 5 minutes. Minimum spacing between review runs.
- `MAX_ROUNDS`: 4. Review rounds before a force refund.
- `MIN_APPEAL_BOND`: 0.1 GEN. Minimum bond a deal may require.
- `DEADLINE_SLACK`: 6 hours. Grace before an unreviewed delivery can expire.

## License

MIT.
