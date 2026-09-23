"""Steward simulation on deal #6: run the re-review, capture the tx where the
staked bond moves to the buyer, then stage a fresh APPEALED deal (#7) so the
board keeps a live one for the next visitor."""

import time
import urllib.request

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

PACT = "0xD5Efa2b53B8C60AcB1A742e42f2cb22AC68ff953"
REVIEW_COOLDOWN = 300


def test_steward_deal6():
    accounts = get_accounts()
    steward = accounts[0]  # review is permissionless: any wallet works
    buyer, seller = accounts[0], accounts[1]
    pact = get_contract_factory("PactLine").build_contract(PACT)

    # ---- preflight: the staged page must still be the placeholder ---------
    d6 = pact.get_deal(args=[6]).call()
    s0 = pact.get_stats(args=[]).call()
    print(f"\nBEFORE deal6: status={d6['status']} verdict={d6['verdict']!r} staked={int(d6['appeal_staked']) / GEN} GEN")
    print(f"BEFORE stats: payouts={int(s0['payouts']) / GEN} escrow={int(s0['escrow']) / GEN} appeals={s0['appeals']} overturned={s0['overturned']}")
    assert d6["status"] == "APPEALED", f"deal 6 must sit in APPEALED, got {d6['status']}"
    assert int(d6["appeal_staked"]) == BOND
    page = urllib.request.urlopen(d6["deliverable_url"], timeout=30).read().decode()
    assert "PACTLINE-SEED-F6" not in page, "the page must not carry the marker, or this would overturn"
    print("preflight: page is still the placeholder -> the re-review should uphold the FAIL")

    # ---- the steward's click ----------------------------------------------
    receipt = pact.connect(steward).run_review(args=[6]).transact(
        wait_interval=10000, wait_retries=30
    )
    assert tx_execution_succeeded(receipt)
    tx = receipt["hash"]
    print(f"\nTX HASH: {tx}")

    d6 = pact.get_deal(args=[6]).call()
    s1 = pact.get_stats(args=[]).call()
    print(f"AFTER deal6: status={d6['status']} verdict={d6['verdict']} staked={int(d6['appeal_staked']) / GEN} GEN")
    print(f"AFTER reasoning: {str(d6['reasoning'])[:220]}")
    print(f"AFTER stats: payouts={int(s1['payouts']) / GEN} escrow={int(s1['escrow']) / GEN} appeals={s1['appeals']} overturned={s1['overturned']}")

    assert d6["status"] == "REFUNDED", f"upheld appeal must refund, got {d6['status']}"
    assert d6["verdict"] == "FAIL"
    assert int(d6["appeal_staked"]) == 0, "the bond must have left the deal"
    assert int(s1["payouts"]) == int(s0["payouts"]) + BOND + ESCROW, "buyer receives bond + escrow"
    assert int(s1["escrow"]) == int(s0["escrow"]) - ESCROW
    assert int(s1["appeals"]) == int(s0["appeals"]), "re-review does not add an appeal"
    assert int(s1["overturned"]) == int(s0["overturned"]), "upheld, not overturned"
    print("UPHELD CONFIRMED: bond 0.1 GEN -> buyer, escrow 1.0 GEN -> buyer, fee-free")

    # ---- stage deal 7: a fresh APPEALED deal for the next visitor ---------
    deadline = int(time.time()) + 30 * 24 * 3600
    did = int(pact.get_stats(args=[]).call()["deals"]) + 1
    r = pact.connect(buyer).create_deal(args=[_terms(f"PACTLINE-SEED-G{did}"), deadline, BOND]).transact(
        value=ESCROW, wait_interval=10000, wait_retries=15
    )
    assert tx_execution_succeeded(r)
    url = _new_webhook_url()
    _write_page(url, _placeholder_page(did, pact.address))
    r = pact.connect(seller).accept_and_deliver(args=[did, url, "Still believe the work meets the terms; re-review will confirm."]).transact(
        wait_interval=10000, wait_retries=15
    )
    assert tx_execution_succeeded(r)
    r = pact.connect(buyer).run_review(args=[did]).transact(wait_interval=10000, wait_retries=30)
    assert tx_execution_succeeded(r)
    d = pact.get_deal(args=[did]).call()
    assert d["status"] == "FAILED", f"deal {did} must fail first, got {d['status']}"
    r = pact.connect(seller).appeal(args=[did]).transact(value=BOND, wait_interval=10000, wait_retries=15)
    assert tx_execution_succeeded(r)
    d = pact.get_deal(args=[did]).call()
    assert d["status"] == "APPEALED", f"deal {did} must be staged in APPEALED, got {d['status']}"
    print(f"\nSTAGED DEAL={did} (APPEALED, bond staked, placeholder up: {url})")

    s = pact.get_stats(args=[]).call()
    print(
        f"FINAL stats: deals={s['deals']} settled={s['settled_count']} appeals={s['appeals']} "
        f"overturned={s['overturned']} payouts={int(s['payouts']) / GEN} GEN escrow={int(s['escrow']) / GEN} GEN"
    )
    print(f"\nCAPTURED TX (bond to buyer): {tx}")
    print("SIMULATION DONE")
