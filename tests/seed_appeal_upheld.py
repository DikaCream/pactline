"""Add the appeal-upheld story to an existing PactLine demo board.

Run against the live board (the address the frontend points at):

  PACT_ADDR=0x... gltest --network studionet tests/seed_appeal_upheld.py -v -s

Two deals are appended to whatever the board already holds:

  deal A  FAILED -> APPEALED -> re-review FAIL again (upheld):
          the staked bond pays the buyer and the escrow refunds fee-free.
          Final state REFUNDED with the bond transfer on-chain in the stats.
  deal B  FAILED -> APPEALED and left there: the page is still the
          placeholder, so a steward clicking "Run the re-review" in the app
          watches the bond move to the buyer live. If nobody clicks, the
          3-day window closing lets anyone finalize: bond back to the seller.

The re-review of deal A must wait out the 300s per-deal review cooldown,
which is why this run takes a few minutes.
"""

import os
import time

from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_succeeded

from tests.deploy_seed_pactline import (
    BOND,
    ESCROW,
    GEN,
    _new_webhook_url,
    _placeholder_page,
    _terms,
    _write_page,
)

PACT_ADDR = os.environ.get("PACT_ADDR", "0xD5Efa2b53B8C60AcB1A742e42f2cb22AC68ff953")
REVIEW_COOLDOWN = 300


def _retry(fn, tries=4, pause=8, what="call"):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - any transient error retries
            last = e
            print(f"  [retry] {what} attempt {i + 1} failed: {str(e)[:120]}")
            time.sleep(pause)
    raise last


def add_appeal_deals(pact, buyer, seller):
    """Append the upheld-appeal arc (finished) and the staged appeal (live)."""
    deadline = int(time.time()) + 30 * 24 * 3600
    stats0 = pact.get_stats(args=[]).call()
    first_id = int(stats0["deals"]) + 1
    did_a, did_b = first_id, first_id + 1

    # ================= deal A: full upheld arc =================
    receipt = _retry(
        lambda: pact.connect(buyer)
        .create_deal(args=[_terms(f"PACTLINE-SEED-E{did_a}"), deadline, BOND])
        .transact(value=ESCROW, wait_interval=10000, wait_retries=15),
        what=f"create_deal {did_a}",
    )
    assert tx_execution_succeeded(receipt)
    url_a = _new_webhook_url()
    _write_page(url_a, _placeholder_page(did_a, pact.address))
    receipt = _retry(
        lambda: pact.connect(seller)
        .accept_and_deliver(args=[did_a, url_a, "Placeholder up; final content follows."])
        .transact(wait_interval=10000, wait_retries=15),
        what=f"deliver {did_a}",
    )
    assert tx_execution_succeeded(receipt)
    t_review = time.time()
    receipt = _retry(
        lambda: pact.connect(buyer)
        .run_review(args=[did_a])
        .transact(wait_interval=10000, wait_retries=30),
        what=f"review {did_a} (FAIL)",
    )
    assert tx_execution_succeeded(receipt)
    d = pact.get_deal(args=[did_a]).call()
    assert d["status"] == "FAILED", f"deal {did_a} must fail first, got {d['status']}"
    print(f"deal {did_a} FAILED on the placeholder page")

    receipt = _retry(
        lambda: pact.connect(seller)
        .appeal(args=[did_a])
        .transact(value=BOND, wait_interval=10000, wait_retries=15),
        what=f"appeal {did_a}",
    )
    assert tx_execution_succeeded(receipt)
    print(f"deal {did_a} APPEALED, bond {BOND / GEN} GEN staked")

    # ================= deal B: staged mid-appeal =================
    receipt = _retry(
        lambda: pact.connect(buyer)
        .create_deal(args=[_terms(f"PACTLINE-SEED-F{did_b}"), deadline, BOND])
        .transact(value=ESCROW, wait_interval=10000, wait_retries=15),
        what=f"create_deal {did_b}",
    )
    assert tx_execution_succeeded(receipt)
    url_b = _new_webhook_url()
    _write_page(url_b, _placeholder_page(did_b, pact.address))
    receipt = _retry(
        lambda: pact.connect(seller)
        .accept_and_deliver(args=[did_b, url_b, "Still believe the work meets the terms; re-review will confirm."])
        .transact(wait_interval=10000, wait_retries=15),
        what=f"deliver {did_b}",
    )
    assert tx_execution_succeeded(receipt)
    receipt = _retry(
        lambda: pact.connect(buyer)
        .run_review(args=[did_b])
        .transact(wait_interval=10000, wait_retries=30),
        what=f"review {did_b} (FAIL)",
    )
    assert tx_execution_succeeded(receipt)
    receipt = _retry(
        lambda: pact.connect(seller)
        .appeal(args=[did_b])
        .transact(value=BOND, wait_interval=10000, wait_retries=15),
        what=f"appeal {did_b}",
    )
    assert tx_execution_succeeded(receipt)
    d = pact.get_deal(args=[did_b]).call()
    assert d["status"] == "APPEALED", f"deal {did_b} must sit in APPEALED, got {d['status']}"
    print(f"deal {did_b} staged in APPEALED: run the re-review in the app to watch the bond move")

    # ================= finish deal A after the cooldown =================
    wait = max(0.0, (t_review + REVIEW_COOLDOWN + 10) - time.time())
    if wait > 0:
        print(f"waiting {int(wait)}s out of deal {did_a}'s review cooldown...")
        time.sleep(wait)

    receipt = _retry(
        lambda: pact.connect(buyer)
        .run_review(args=[did_a])
        .transact(wait_interval=10000, wait_retries=30),
        what=f"re-review {did_a} (expect FAIL again -> upheld)",
    )
    assert tx_execution_succeeded(receipt)

    d = pact.get_deal(args=[did_a]).call()
    s = pact.get_stats(args=[]).call()
    print(f"deal {did_a} after re-review: status={d['status']} verdict={d['verdict']}")
    print(f"  reasoning: {str(d['reasoning'])[:220]}")
    assert d["status"] == "REFUNDED", f"upheld appeal must refund, got {d['status']}"
    assert d["verdict"] == "FAIL"
    assert int(d["appeal_staked"]) == 0, "the bond must have left the deal"

    # the bond moved to the buyer and the escrow refunded fee-free
    payout_delta = int(s["payouts"]) - int(stats0["payouts"])
    assert payout_delta == BOND + ESCROW, (
        f"payouts must rise by bond + escrow ({(BOND + ESCROW) / GEN} GEN), rose {payout_delta / GEN}"
    )
    assert int(s["appeals"]) == int(stats0["appeals"]) + 2
    assert int(s["overturned"]) == int(stats0["overturned"]), "this appeal is upheld, not overturned"
    print(
        f"accounting: buyer received {BOND / GEN} GEN bond + {ESCROW / GEN} GEN escrow "
        f"fee-free; payouts {int(stats0['payouts']) / GEN} -> {int(s['payouts']) / GEN} GEN"
    )
    return did_a, did_b


def test_add_appeal_upheld():
    accounts = get_accounts()
    buyer, seller = accounts[0], accounts[1]
    pact = get_contract_factory("PactLine").build_contract(PACT_ADDR)
    print(f"\nboard: {PACT_ADDR}")
    did_a, did_b = add_appeal_deals(pact, buyer, seller)
    s = pact.get_stats(args=[]).call()
    print(
        f"\nFINAL stats: deals={s['deals']} settled={s['settled_count']} "
        f"appeals={s['appeals']} overturned={s['overturned']} "
        f"payouts={int(s['payouts']) / GEN} GEN escrow={int(s['escrow']) / GEN} GEN"
    )
    print(f"\nUPHELD DEAL={did_a} (REFUNDED, bond paid to buyer)")
    print(f"STAGED DEAL={did_b} (APPEALED, re-review left for a visitor)")
    print("ADDER DONE")


if __name__ == "__main__":
    test_add_appeal_upheld()
