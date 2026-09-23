"""Deploy PactLine on StudioNet and seed a live demo board.

Run: gltest --network studionet tests/deploy_seed_pactline.py -v -s

The seed leaves the board with every state represented:

  deal 1  SETTLED    - the flagship: consensus PASS moved 1 GEN of escrow
                       to the seller on-chain, fee 0.5% taken
  deal 2  DELIVERED  - a good page, review not run yet: a visitor can click
                       "Run the review" in the dapp and watch consensus pay
  deal 3  CREATED    - funded, open for a seller to take and deliver
  deal 4  FAILED     - placeholder page failed review, no bond, buyer can
                       finalize the fee-free refund at once

Print the contract address at the end; it goes into the frontend config.
"""

import json
import time
import urllib.request

from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_succeeded

GEN = 10**18
ESCROW = GEN
BOND = GEN // 10
FEE = ESCROW * 1 // 200
NET = ESCROW - FEE


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


def _new_webhook_url() -> str:
    req = urllib.request.Request(
        "https://webhook.site/token",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    token = json.loads(urllib.request.urlopen(req, timeout=30).read())["uuid"]
    return f"https://webhook.site/{token}"


def _write_page(url: str, body: str) -> None:
    token = url.rsplit("/", 1)[1]
    req = urllib.request.Request(
        f"https://webhook.site/token/{token}",
        data=json.dumps({"default_content": body, "status": 200}).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    urllib.request.urlopen(req, timeout=30)
    served = urllib.request.urlopen(url, timeout=30).read().decode()
    assert body in served, "the endpoint did not take the content"


def _terms(marker: str) -> str:
    return (
        f"Acceptance terms (all machine-checkable): the delivered page must "
        f"contain the exact marker string {marker} and the exact phrase "
        f"'delivery accepted'. A page missing either string is a FAIL."
    )


def _good_page(marker: str, deal_id: int, pact_addr: str) -> str:
    return f"""DELIVERY - PactLine demo deal {deal_id}

delivery accepted

Marker (required by the acceptance terms): {marker}

WHAT WAS DELIVERED

A plain text delivery page for PactLine deal {deal_id} on the escrow
contract at {pact_addr}. The page exists so the validators can fetch it
themselves and check the two strings the terms require: the marker
{marker} and the phrase 'delivery accepted'. Both appear in this page
exactly as written.

The work itself is intentionally minimal: PactLine judges deliverables
against the written terms and nothing else, so the honest deliverable for
a demo is a page that states its own compliance in plain text. Everything
a reviewer needs is on this page: the marker, the phrase, the deal id and
the escrow contract address. No external resources, no scripts, nothing
that renders differently per reader.
"""


def _placeholder_page(deal_id: int, pact_addr: str) -> str:
    return f"""DELIVERY (incomplete) - PactLine demo deal {deal_id}

Status: the work for deal {deal_id} on escrow contract {pact_addr} is
still in progress. This placeholder page will be replaced by the final
deliverable once the remaining sections are done. The acceptance marker
is not included yet because the content that carries it has not been
written. Reviewers should judge this page as it stands: it does not meet
terms that require the marker string to be present.
"""


def test_seed():
    accounts = get_accounts()
    buyer, seller = accounts[0], accounts[1]

    pact = get_contract_factory("PactLine").deploy(account=buyer)
    print(f"\nPactLine deployed at {pact.address}")
    deadline = int(time.time()) + 30 * 24 * 3600

    # ---- deal 1: the full arc, settled on consensus -----------------------
    receipt = _retry(
        lambda: pact.connect(buyer)
        .create_deal(args=[_terms("PACTLINE-SEED-A1"), deadline, BOND])
        .transact(value=ESCROW, wait_interval=10000, wait_retries=15),
        what="create_deal 1",
    )
    assert tx_execution_succeeded(receipt)
    did1 = 1
    url1 = _new_webhook_url()
    _write_page(url1, _good_page("PACTLINE-SEED-A1", did1, pact.address))
    receipt = _retry(
        lambda: pact.connect(seller)
        .accept_and_deliver(args=[did1, url1, "Page is up; it carries the marker and the phrase."])
        .transact(wait_interval=10000, wait_retries=15),
        what="deliver 1",
    )
    assert tx_execution_succeeded(receipt)
    receipt = _retry(
        lambda: pact.connect(buyer)
        .run_review(args=[did1])
        .transact(wait_interval=10000, wait_retries=30),
        what="review 1",
    )
    assert tx_execution_succeeded(receipt)
    d1 = pact.get_deal(args=[did1]).call()
    assert d1["status"] == "SETTLED", f"deal 1 must settle, got {d1['status']}"
    print(f"deal {did1} SETTLED: seller paid {NET / GEN} GEN net on consensus PASS")

    # ---- deal 2: delivered, awaiting a visitor's review -------------------
    receipt = _retry(
        lambda: pact.connect(buyer)
        .create_deal(args=[_terms("PACTLINE-SEED-B2"), deadline, BOND])
        .transact(value=ESCROW, wait_interval=10000, wait_retries=15),
        what="create_deal 2",
    )
    assert tx_execution_succeeded(receipt)
    did2 = 2
    url2 = _new_webhook_url()
    _write_page(url2, _good_page("PACTLINE-SEED-B2", did2, pact.address))
    receipt = _retry(
        lambda: pact.connect(seller)
        .accept_and_deliver(args=[did2, url2, "Done and live; run the review when ready."])
        .transact(wait_interval=10000, wait_retries=15),
        what="deliver 2",
    )
    assert tx_execution_succeeded(receipt)
    print(f"deal {did2} DELIVERED: {url2} (run the review in the dapp)")

    # ---- deal 3: open for a seller ----------------------------------------
    receipt = _retry(
        lambda: pact.connect(buyer)
        .create_deal(args=[_terms("PACTLINE-SEED-C3"), deadline, BOND])
        .transact(value=ESCROW, wait_interval=10000, wait_retries=15),
        what="create_deal 3",
    )
    assert tx_execution_succeeded(receipt)
    print(f"deal 3 CREATED: open for a seller to take (escrow 1 GEN locked)")

    # ---- deal 4: failed review, no bond, refundable now -------------------
    receipt = _retry(
        lambda: pact.connect(buyer)
        .create_deal(args=[_terms("PACTLINE-SEED-D4"), deadline, 0])
        .transact(value=ESCROW, wait_interval=10000, wait_retries=15),
        what="create_deal 4",
    )
    assert tx_execution_succeeded(receipt)
    did4 = 4
    url4 = _new_webhook_url()
    _write_page(url4, _placeholder_page(did4, pact.address))
    receipt = _retry(
        lambda: pact.connect(seller)
        .accept_and_deliver(args=[did4, url4, "Placeholder up; final content follows."])
        .transact(wait_interval=10000, wait_retries=15),
        what="deliver 4",
    )
    assert tx_execution_succeeded(receipt)
    receipt = _retry(
        lambda: pact.connect(buyer)
        .run_review(args=[did4])
        .transact(wait_interval=10000, wait_retries=30),
        what="review 4",
    )
    assert tx_execution_succeeded(receipt)
    d4 = pact.get_deal(args=[did4]).call()
    assert d4["status"] == "FAILED", f"deal 4 must fail, got {d4['status']}"
    print(f"deal {did4} FAILED: placeholder page, no bond, buyer can finalize")

    stats = pact.get_stats(args=[]).call()
    print(
        f"\nFINAL stats: deals={stats['deals']} settled={stats['settled_count']} "
        f"fees={int(stats['fees']) / GEN} GEN payouts={int(stats['payouts']) / GEN} "
        f"GEN escrow={int(stats['escrow']) / GEN} GEN"
    )
    print(f"\nPACTLINE_ADDRESS={pact.address}")
    print("SEED DONE")


if __name__ == "__main__":
    test_seed()
