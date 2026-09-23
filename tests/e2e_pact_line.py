"""E2E on live StudioNet: PactLine moves real money on real consensus.

Run: gltest --network studionet tests/e2e_pact_line.py -v -s

Each run deploys a fresh PactLine, then walks two full arcs exactly as the
dapp's users would:

  arc 1  buyer funds a deal with machine-readable terms, the seller delivers
         a page that plainly meets them, anyone runs the review, the
         validators fetch the page themselves and agree on PASS, the seller
         is paid from escrow (net of the 0.5% settlement fee) on-chain.

  arc 2  a second deal whose first page does NOT meet the terms: consensus
         FAIL, the seller stakes the appeal bond, fixes the page, and the
         re-review overturns the FAIL: the bond returns to the seller and
         the escrow settles to them. Every wei is accounted for at the end.

The deliverable pages are public webhook.site endpoints, so the validators
fetch the same bytes anyone on the internet would see.
"""

import json
import time
import urllib.request

from gltest import get_accounts, get_contract_factory
from gltest.assertions import tx_execution_succeeded

GEN = 10**18
ESCROW = GEN            # 1 GEN per deal
BOND = GEN // 10        # 0.1 GEN appeal bond
FEE = ESCROW * 1 // 200 # 0.5% settlement fee
NET = ESCROW - FEE

MARKER_OK = "PACTLINE-DEMO-1"
MARKER_LATE = "PACTLINE-DEMO-2"


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
more than once, exactly as written, with no formatting between the
characters.

The work itself is intentionally minimal: PactLine judges deliverables
against the written terms and nothing else, so the honest deliverable for
a demo is a page that states its own compliance in plain text. Everything
a reviewer needs is on this page: the marker, the phrase, the deal id and
the escrow contract address. No external resources, no scripts, nothing
that renders differently per reader.
"""


def _late_page(deal_id: int, pact_addr: str) -> str:
    return f"""DELIVERY (incomplete) - PactLine demo deal {deal_id}

Status: the work for deal {deal_id} on escrow contract {pact_addr} is
still in progress. This placeholder page will be replaced by the final
deliverable once the remaining sections are done. The acceptance marker
is not included yet because the content that carries it has not been
written. Reviewers should judge this page as it stands: it does not meet
terms that require the marker string to be present.
"""


def test_pact_line_e2e():
    """Arc 1: deliver, consensus PASS, seller paid. Arc 2: FAIL, appeal,
    fixed page, overturned, settled - every wei accounted for."""
    accounts = get_accounts()
    buyer, seller = accounts[0], accounts[1]

    pact = get_contract_factory("PactLine").deploy(account=buyer)
    print(f"\nPactLine deployed at {pact.address}")

    deadline = int(time.time()) + 7 * 24 * 3600

    # ================= arc 1: PASS settles in one review =================
    receipt = _retry(
        lambda: pact.connect(buyer)
        .create_deal(args=[_terms(MARKER_OK), deadline, BOND])
        .transact(value=ESCROW, wait_interval=10000, wait_retries=15),
        what="create_deal 1",
    )
    assert tx_execution_succeeded(receipt)
    did1 = int(pact.get_stats(args=[]).call()["deals"])
    print(f"deal {did1} created: escrow 1 GEN, bond 0.1 GEN")

    url1 = _new_webhook_url()
    _write_page(url1, _good_page(MARKER_OK, did1, pact.address))

    receipt = _retry(
        lambda: pact.connect(seller)
        .accept_and_deliver(args=[did1, url1, "Page is up; it carries the marker and the phrase."])
        .transact(wait_interval=10000, wait_retries=15),
        what="accept_and_deliver 1",
    )
    assert tx_execution_succeeded(receipt)
    print(f"deal {did1} delivered: {url1}")

    receipt = _retry(
        lambda: pact.connect(buyer)
        .run_review(args=[did1])
        .transact(wait_interval=10000, wait_retries=30),
        what="run_review 1",
    )
    assert tx_execution_succeeded(receipt)

    d1 = pact.get_deal(args=[did1]).call()
    print(f"deal {did1}: status={d1['status']} verdict={d1['verdict']}")
    print(f"  reasoning: {str(d1['reasoning'])[:200]}")
    assert d1["status"] == "SETTLED", f"expected SETTLED, got {d1['status']}"
    assert d1["verdict"] == "PASS", f"expected PASS, got {d1['verdict']}"

    stats1 = pact.get_stats(args=[]).call()
    assert int(stats1["escrow"]) == 0, "arc 1 must leave no escrow behind"
    assert int(stats1["fees"]) == FEE
    assert int(stats1["payouts"]) == NET
    print(f"seller paid {NET / GEN} GEN net, fee {FEE / GEN} GEN, escrow drained")

    # ========== arc 2: FAIL -> appeal -> fixed page -> overturned ==========
    receipt = _retry(
        lambda: pact.connect(buyer)
        .create_deal(args=[_terms(MARKER_LATE), deadline, BOND])
        .transact(value=ESCROW, wait_interval=10000, wait_retries=15),
        what="create_deal 2",
    )
    assert tx_execution_succeeded(receipt)
    did2 = int(pact.get_stats(args=[]).call()["deals"])

    url2 = _new_webhook_url()
    _write_page(url2, _late_page(did2, pact.address))

    receipt = _retry(
        lambda: pact.connect(seller)
        .accept_and_deliver(args=[did2, url2, "Placeholder up; final content follows."])
        .transact(wait_interval=10000, wait_retries=15),
        what="accept_and_deliver 2",
    )
    assert tx_execution_succeeded(receipt)
    print(f"deal {did2} delivered (placeholder page): {url2}")

    receipt = _retry(
        lambda: pact.connect(buyer)
        .run_review(args=[did2])
        .transact(wait_interval=10000, wait_retries=30),
        what="run_review 2 (expect FAIL)",
    )
    assert tx_execution_succeeded(receipt)

    d2 = pact.get_deal(args=[did2]).call()
    print(f"deal {did2}: status={d2['status']} verdict={d2['verdict']}")
    assert d2["status"] == "FAILED", f"expected FAILED, got {d2['status']}"
    assert d2["verdict"] == "FAIL", f"expected FAIL, got {d2['verdict']}"

    # the seller stakes the bond; the stake restarts the re-review window
    receipt = _retry(
        lambda: pact.connect(seller)
        .appeal(args=[did2])
        .transact(value=BOND, wait_interval=10000, wait_retries=15),
        what="appeal",
    )
    assert tx_execution_succeeded(receipt)
    print(f"deal {did2} appealed, bond {BOND / GEN} GEN staked")

    # the fix: the page now carries the marker the terms require
    _write_page(url2, _good_page(MARKER_LATE, did2, pact.address))
    print("deliverable page fixed in place (same URL, new content)")

    # the cooldown between reviews is 300s on-chain; wait it out
    print("waiting out the 300s review cooldown...")
    time.sleep(310)

    receipt = _retry(
        lambda: pact.connect(buyer)
        .run_review(args=[did2])
        .transact(wait_interval=10000, wait_retries=30),
        what="run_review 2 (re-review after appeal)",
    )
    assert tx_execution_succeeded(receipt)

    d2 = pact.get_deal(args=[did2]).call()
    stats2 = pact.get_stats(args=[]).call()
    print(f"deal {did2} after re-review: status={d2['status']} verdict={d2['verdict']}")
    assert d2["status"] == "SETTLED", f"expected SETTLED, got {d2['status']}"
    assert d2["verdict"] == "PASS", f"expected PASS, got {d2['verdict']}"

    # accounting across both arcs: two settles, one overturned appeal,
    # the bond went back to the seller, escrow fully drained
    assert int(stats2["deals"]) == 2
    assert int(stats2["settled_count"]) == 2
    assert int(stats2["appeals"]) == 1
    assert int(stats2["overturned"]) == 1
    assert int(stats2["fees"]) == 2 * FEE
    # payouts = 2x escrow net + the returned bond
    assert int(stats2["payouts"]) == 2 * NET + BOND
    assert int(stats2["escrow"]) == 0
    print(
        f"accounting: settled 2x{NET / GEN} GEN net, bond {BOND / GEN} GEN "
        f"returned, fees {2 * FEE / GEN} GEN, escrow 0"
    )

    print("\nE2E PASS: consensus settle, FAIL+appeal overturn, all funds accounted")


if __name__ == "__main__":
    test_pact_line_e2e()
