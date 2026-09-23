"""PactLine direct-mode tests: the escrow state machine, exhaustively.

Everything here runs in a local VM with mocked validators, so the guards are
covered deterministically. The consensus path (validators fetching a real
deliverable page) is covered by the StudioNet integration tests.

Clock discipline: in the direct VM, assigning ``vm.sender`` rebuilds the
message context and restores the block time to the wall clock, so every test
finishes its sender/value assignments BEFORE warping time.
"""

import time
from datetime import datetime, timezone

import pytest

from tests.direct.conftest import set_time

DAY = 24 * 3600
BASE_TS = int(time.time())  # the direct VM's clock is the wall clock
DEADLINE = BASE_TS + 30 * DAY

ESCROW = 10**18  # 1 GEN
FEE = ESCROW * 1 // 200  # 0.5%
NET = ESCROW - FEE  # what the seller actually receives
BOND = 10**17  # 0.1 GEN

TERMS = "A text page of at least 200 words titled 'Quarterly Report', with a revenue table."
SELLER_NOTE = "The page is done, see the attached word count."
GOOD_BODY = "Quarterly Report. Revenue by region, 480 words, tables included."
DELIVER_URL = "https://deliverable.example/work"


def _reset():
    import genlayer.gl.genvm_contracts as gvc

    gvc.__known_contract__ = None  # the direct loader does not reset this


@pytest.fixture()
def pact(direct_vm, direct_deploy):
    c = direct_deploy("contracts/pact_line.py")
    yield c
    _reset()


# ----------------------------------------------------------------- helpers
def _warp(vm, ts: int) -> None:
    """Move the block time to the given epoch second. Call AFTER any
    sender/value assignment: they reset the clock to the wall clock."""
    iso = datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")
    set_time(iso)


def _create(pact, vm, buyer, escrow=ESCROW, bond=BOND, deadline=DEADLINE, terms=TERMS):
    vm.sender = buyer
    vm.value = escrow
    did = int(pact.create_deal(terms, deadline, bond))
    vm.value = 0
    return did


def _deliver(pact, vm, seller, did, url=DELIVER_URL, reason=SELLER_NOTE):
    vm.sender = seller
    pact.accept_and_deliver(did, url, reason)


def _clear_and_mock_pass(vm, body=GOOD_BODY):
    """Mocks are first-match-wins, so a verdict flip needs the old ones gone."""
    vm.clear_mocks()
    _mock_pass(vm, body)


def _mock_pass(vm, body=GOOD_BODY):
    vm.mock_web(r"https://deliverable\.example/work", {"status": 200, "body": body})
    vm.mock_llm(
        r".*acceptance reviewer.*",
        '{"verdict": "PASS", "reasoning": "The work shows the full report with the table."}',
    )


def _mock_fail(vm, body=GOOD_BODY):
    vm.mock_web(r"https://deliverable\.example/work", {"status": 200, "body": body})
    vm.mock_llm(
        r".*acceptance reviewer.*",
        '{"verdict": "FAIL", "reasoning": "The page is a landing page, not the work."}',
    )


def _appeal(pact, vm, seller, did, bond=BOND):
    vm.sender = seller
    vm.value = bond
    pact.appeal(did)
    vm.value = 0


# ------------------------------------------------------------------ create
def test_create_deal(pact, direct_vm, direct_alice):
    did = _create(pact, direct_vm, direct_alice)
    d = pact.get_deal(did)
    assert d["status"] == "CREATED"
    assert not d["has_seller"]
    assert int(d["amount"]) == ESCROW
    assert int(d["appeal_bond"]) == BOND
    stats = pact.get_stats()
    assert int(stats["escrow"]) == ESCROW
    assert int(stats["deals"]) == 1


def test_create_reverts_zero_escrow(pact, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    with pytest.raises(Exception, match="escrow amount must be positive"):
        pact.create_deal(TERMS, DEADLINE, BOND)


def test_create_reverts_blank_terms(pact, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    direct_vm.value = ESCROW
    with pytest.raises(Exception, match="terms"):
        pact.create_deal("   ", DEADLINE, BOND)
    direct_vm.value = 0


def test_create_reverts_oversized_terms(pact, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    direct_vm.value = ESCROW
    with pytest.raises(Exception, match="terms"):
        pact.create_deal("x" * 4001, DEADLINE, BOND)
    direct_vm.value = 0


def test_create_reverts_near_deadline(pact, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    direct_vm.value = ESCROW
    with pytest.raises(Exception, match="deadline"):
        pact.create_deal(TERMS, BASE_TS + 1800, BOND)
    direct_vm.value = 0


def test_create_reverts_tiny_bond(pact, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    direct_vm.value = ESCROW
    with pytest.raises(Exception, match="appeal bond"):
        pact.create_deal(TERMS, DEADLINE, 10**16)
    direct_vm.value = 0


def test_create_reverts_bond_over_escrow(pact, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    direct_vm.value = ESCROW
    with pytest.raises(Exception, match="exceed the escrow"):
        pact.create_deal(TERMS, DEADLINE, ESCROW + 1)
    direct_vm.value = 0


# ----------------------------------------------------------------- deliver
def test_accept_and_deliver(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    d = pact.get_deal(did)
    assert d["status"] == "DELIVERED"
    assert d["has_seller"]
    assert d["deliverable_url"] == DELIVER_URL
    assert int(d["seconds_to_deadline"]) > 0


def test_deliver_reverts_second_seller(pact, direct_vm, direct_alice, direct_bob, direct_charlie):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    direct_vm.sender = direct_charlie
    # DELIVERED is not CREATED: the second seller cannot take the deal.
    with pytest.raises(Exception, match="not open for delivery"):
        pact.accept_and_deliver(did, DELIVER_URL, "me too")


def test_deliver_reverts_past_deadline(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    direct_vm.sender = direct_bob  # sender first: assignments reset the clock
    _warp(direct_vm, DEADLINE + 60)
    with pytest.raises(Exception, match="deadline passed"):
        pact.accept_and_deliver(did, DELIVER_URL, "late")


@pytest.mark.parametrize("url", ["ftp://x.example/a", "not a url", ""])
def test_deliver_reverts_bad_url(pact, direct_vm, direct_alice, direct_bob, url):
    did = _create(pact, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    with pytest.raises(Exception):
        pact.accept_and_deliver(did, url, "note")


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8080/work",
        "http://127.0.0.1/work",
        "http://10.0.0.5/work",
        "http://172.16.0.9/work",
        "http://172.31.255.1/work",
        "http://192.168.1.1/work",
        "http://169.254.10.9/work",
        "http://100.64.0.1/work",
        "http://work.internal/report",
        "http://page.local/report",
        "http://[::1]/work",
        "http://0.0.0.0/work",
    ],
)
def test_deliver_reverts_private_url(pact, direct_vm, direct_alice, direct_bob, url):
    """A page only the seller can reach can never be judged; rejecting it at
    delivery spares the buyer four rounds of unreadable reviews."""
    did = _create(pact, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    with pytest.raises(Exception, match="publicly reachable"):
        pact.accept_and_deliver(did, url, "note")
    d = pact.get_deal(did)
    assert d["status"] == "CREATED"  # nothing was consumed


# ------------------------------------------------------------------ review
def test_pass_review_settles_seller(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_pass(direct_vm)
    verdict = pact.run_review(did)
    assert verdict == "PASS"
    d = pact.get_deal(did)
    assert d["status"] == "SETTLED"
    assert d["verdict"] == "PASS"
    stats = pact.get_stats()
    assert int(stats["escrow"]) == 0
    assert int(stats["fees"]) == FEE
    assert int(stats["settled_amount"]) == NET
    assert int(stats["settled_count"]) == 1
    # the seller was paid exactly the net amount, not the whole escrow
    assert int(stats["payouts"]) == NET


def test_fail_review_opens_appeal_window(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    verdict = pact.run_review(did)
    assert verdict == "FAIL"
    d = pact.get_deal(did)
    assert d["status"] == "FAILED"
    stats = pact.get_stats()
    # nothing moved yet: the seller still has the window to stake an appeal
    assert int(stats["escrow"]) == ESCROW
    assert int(stats["fees"]) == 0
    assert int(stats["settled_amount"]) == 0


def test_review_reverts_on_undelivered_deal(pact, direct_vm, direct_alice):
    did = _create(pact, direct_vm, direct_alice)
    with pytest.raises(Exception, match="no review pending"):
        pact.run_review(did)


def test_review_cooldown(pact, direct_vm, direct_alice, direct_bob):
    """Cooldown needs a deal that stays reviewable, so use unreadable fetches:
    a verdict would leave DELIVERED and hit the status guard instead."""
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    assert pact.run_review(did) == "UNREADABLE"  # no mocks: fetch fails
    with pytest.raises(Exception, match="cooldown"):
        pact.run_review(did)


def test_review_rounds_are_bounded(pact, direct_vm, direct_alice, direct_bob):
    """No deliverable is ever readable: four UNREADABLE rounds, then refund."""
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    # no mock_web at all: the fetch fails, the deal burns a round each call
    for i in range(3):
        result = pact.run_review(did)
        assert result == "UNREADABLE"
        # advance past the cooldown each round (a constant warp would not)
        _warp(direct_vm, BASE_TS + 10 * 60 * (i + 1))
    result = pact.run_review(did)
    assert result == "REFUNDED"
    d = pact.get_deal(did)
    assert d["status"] == "REFUNDED"
    stats = pact.get_stats()
    assert int(stats["escrow"]) == 0
    assert int(stats["fees"]) == 0  # refunds are fee-free
    # a fifth review is rejected: the deal is terminal
    with pytest.raises(Exception, match="no review pending"):
        pact.run_review(did)


def test_unreadable_deliverable_is_retryable(pact, direct_vm, direct_alice, direct_bob):
    """A flaky deliverable gets its rounds back before the cap."""
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    result = pact.run_review(did)  # fetch fails, round burns
    assert result == "UNREADABLE"
    _warp(direct_vm, BASE_TS + 10 * 60)
    _mock_pass(direct_vm)
    verdict = pact.run_review(did)
    assert verdict == "PASS"  # recovery pays in full
    stats = pact.get_stats()
    assert int(stats["settled_amount"]) == NET


def test_garbled_reviews_never_wedge_the_deal(pact, direct_vm, direct_alice, direct_bob):
    """A model that keeps answering valid JSON with no verdict burns rounds
    like an unreadable fetch and force-refunds instead of wedging forever."""
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    direct_vm.mock_web(r"https://deliverable\.example/work", {"status": 200, "body": GOOD_BODY})
    direct_vm.mock_llm(r".*acceptance reviewer.*", '{"status": "confused"}')
    for i in range(3):
        assert pact.run_review(did) == "INVALID"
        _warp(direct_vm, BASE_TS + 10 * 60 * (i + 1))
    assert pact.run_review(did) == "REFUNDED"
    d = pact.get_deal(did)
    assert d["status"] == "REFUNDED"
    stats = pact.get_stats()
    assert int(stats["escrow"]) == 0
    assert int(stats["fees"]) == 0


# ------------------------------------------------------------------ appeal
def test_seller_appeal_overturns_fail_and_settles(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    _appeal(pact, direct_vm, direct_bob, did)
    d = pact.get_deal(did)
    assert d["status"] == "APPEALED"
    assert int(d["appeal_staked"]) == BOND
    _warp(direct_vm, BASE_TS + 10 * 60)  # past the review cooldown
    _clear_and_mock_pass(direct_vm)  # the appeal review sees a PASS this time
    verdict = pact.run_review(did)
    assert verdict == "PASS"
    d = pact.get_deal(did)
    assert d["status"] == "SETTLED"
    stats = pact.get_stats()
    assert int(stats["escrow"]) == 0
    assert int(stats["fees"]) == FEE
    assert int(stats["appeals"]) == 1
    assert int(stats["overturned"]) == 1


def test_seller_appeal_upheld_means_fail_stands(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    _appeal(pact, direct_vm, direct_bob, did)
    _warp(direct_vm, BASE_TS + 10 * 60)
    _mock_fail(direct_vm)
    verdict = pact.run_review(did)
    assert verdict == "FAIL"
    d = pact.get_deal(did)
    assert d["status"] == "REFUNDED"
    stats = pact.get_stats()
    # fee-free refund plus the staked bond back to the buyer
    assert int(stats["escrow"]) == 0
    assert int(stats["fees"]) == 0
    assert int(stats["settled_amount"]) == 0
    assert int(stats["appeals"]) == 1
    assert int(stats["overturned"]) == 0


def test_appeal_reverts_for_non_seller(pact, direct_vm, direct_alice, direct_bob, direct_charlie):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    direct_vm.sender = direct_charlie
    direct_vm.value = BOND
    with pytest.raises(Exception, match="only the seller can appeal"):
        pact.appeal(did)
    direct_vm.value = 0


def test_appeal_reverts_wrong_bond(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    direct_vm.sender = direct_bob
    direct_vm.value = BOND - 1
    with pytest.raises(Exception, match="exactly the deal's appeal bond"):
        pact.appeal(did)
    direct_vm.value = 0


def test_appeal_reverts_without_bond(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice, bond=0)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    direct_vm.sender = direct_bob
    direct_vm.value = BOND
    with pytest.raises(Exception, match="carries no appeal bond"):
        pact.appeal(did)
    direct_vm.value = 0


def test_appeal_reverts_after_window(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    direct_vm.sender = direct_bob  # sender first: assignments reset the clock
    direct_vm.value = BOND
    _warp(direct_vm, BASE_TS + 3 * DAY + 60)
    with pytest.raises(Exception, match="appeal window closed"):
        pact.appeal(did)
    direct_vm.value = 0


def test_appeal_is_single_shot(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    _appeal(pact, direct_vm, direct_bob, did)
    direct_vm.sender = direct_bob
    direct_vm.value = BOND
    with pytest.raises(Exception, match="nothing to appeal"):
        pact.appeal(did)
    direct_vm.value = 0


def test_force_refund_returns_staked_bond(pact, direct_vm, direct_alice, direct_bob):
    """A staked appeal that runs out of review rounds unwinds completely:
    the bond goes back to the seller and the escrow refunds fee-free."""
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)  # round 1: the FAIL verdict
    _appeal(pact, direct_vm, direct_bob, did)
    direct_vm.clear_mocks()  # the appeal fetch now fails: rounds burn unreadable
    # the FAIL verdict consumed round 1, so only two unreadable rounds fit
    for i in range(2):
        _warp(direct_vm, BASE_TS + 10 * 60 * (i + 1))
        assert pact.run_review(did) == "UNREADABLE"  # rounds 2-3 burn
    _warp(direct_vm, BASE_TS + 10 * 60 * 3)
    assert pact.run_review(did) == "REFUNDED"  # round 4 hits the cap
    d = pact.get_deal(did)
    assert d["status"] == "REFUNDED"
    stats = pact.get_stats()
    assert int(stats["escrow"]) == 0
    assert int(stats["fees"]) == 0
    # the seller's bond returned and the buyer got every wei of escrow back
    assert int(stats["payouts"]) == BOND + ESCROW
    assert int(stats["appeals"]) == 1


# ---------------------------------------------------------------- finalize
def test_finalize_refunds_after_window(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception, match="appeal window still open"):
        pact.finalize(did)
    _warp(direct_vm, BASE_TS + 3 * DAY + 60)
    pact.finalize(did)
    d = pact.get_deal(did)
    assert d["status"] == "REFUNDED"
    stats = pact.get_stats()
    assert int(stats["escrow"]) == 0
    assert int(stats["fees"]) == 0


def test_finalize_is_immediate_without_bond(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice, bond=0)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    direct_vm.sender = direct_alice
    pact.finalize(did)
    d = pact.get_deal(did)
    assert d["status"] == "REFUNDED"


def test_finalize_unwinds_an_unreviewed_appeal(pact, direct_vm, direct_alice, direct_bob):
    """A seller who stakes and then never re-runs the review must not leave
    the deal stuck in APPEALED: finalize returns the bond and the escrow."""
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    _appeal(pact, direct_vm, direct_bob, did)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception, match="appeal window still open"):
        pact.finalize(did)  # the staked clock is running: seller still has time
    _warp(direct_vm, BASE_TS + 3 * DAY + 60)
    pact.finalize(did)
    d = pact.get_deal(did)
    assert d["status"] == "REFUNDED"
    stats = pact.get_stats()
    assert int(stats["escrow"]) == 0
    assert int(stats["fees"]) == 0
    # the seller's bond returned and the buyer got the full escrow back
    assert int(stats["payouts"]) == BOND + ESCROW


def test_appeal_restarts_the_window(pact, direct_vm, direct_alice, direct_bob):
    """Staking near the end of the window must not leave the seller with no
    time to run the re-review: the staked bond starts a fresh window, and
    once it closes, only finalize remains."""
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    _warp(direct_vm, BASE_TS + 3 * DAY - 60)  # minutes before the window closes
    _appeal(pact, direct_vm, direct_bob, did)
    # now past the ORIGINAL window, but the fresh one is running
    _warp(direct_vm, BASE_TS + 3 * DAY + DAY)
    _clear_and_mock_pass(direct_vm)
    verdict = pact.run_review(did)
    assert verdict == "PASS"
    d = pact.get_deal(did)
    assert d["status"] == "SETTLED"


def test_late_appeal_review_is_rejected_after_window(pact, direct_vm, direct_alice, direct_bob):
    """An APPEALED deal past its re-review window is frozen: the review
    refuses to run and only finalize can still unwind it."""
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    _appeal(pact, direct_vm, direct_bob, did)
    _warp(direct_vm, BASE_TS + 3 * DAY + 60)
    _clear_and_mock_pass(direct_vm)
    with pytest.raises(Exception, match="appeal window closed"):
        pact.run_review(did)
    # the stuck deal is still unwound by finalize, not stuck forever
    direct_vm.sender = direct_alice
    pact.finalize(did)
    assert pact.get_deal(did)["status"] == "REFUNDED"


# ------------------------------------------------------------- open exits
def test_buyer_cancel_releases_undelivered_deal(pact, direct_vm, direct_alice):
    did = _create(pact, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    pact.buyer_cancel(did)
    d = pact.get_deal(did)
    assert d["status"] == "CANCELED"
    stats = pact.get_stats()
    assert int(stats["escrow"]) == 0
    assert int(stats["fees"]) == 0


def test_buyer_cancel_reverts_after_delivery(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception, match="only open deals"):
        pact.buyer_cancel(did)


def test_buyer_cancel_reverts_for_stranger(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    with pytest.raises(Exception, match="only the buyer"):
        pact.buyer_cancel(did)


def test_expire_returns_escrow_after_slack(pact, direct_vm, direct_alice, direct_charlie):
    did = _create(pact, direct_vm, direct_alice)
    direct_vm.sender = direct_charlie  # anyone may expire
    with pytest.raises(Exception, match="slack not elapsed"):
        pact.expire(did)
    _warp(direct_vm, DEADLINE + 6 * 3600 + 60)
    pact.expire(did)
    d = pact.get_deal(did)
    assert d["status"] == "EXPIRED"
    stats = pact.get_stats()
    assert int(stats["escrow"]) == 0
    assert int(stats["fees"]) == 0


def test_expire_releases_a_delivered_deal_nobody_reviewed(pact, direct_vm, direct_alice, direct_bob, direct_charlie):
    """Delivery alone locks nothing forever: if the permissionless review
    never runs by deadline + slack, anyone can hand the escrow back."""
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    direct_vm.sender = direct_charlie
    _warp(direct_vm, DEADLINE + 6 * 3600 + 60)
    pact.expire(did)
    d = pact.get_deal(did)
    assert d["status"] == "EXPIRED"  # the clock ran out; refund via expiry
    stats = pact.get_stats()
    assert int(stats["escrow"]) == 0
    assert int(stats["fees"]) == 0  # refunds are fee-free
    assert int(stats["payouts"]) == ESCROW


def test_delivered_deal_that_gets_reviewed_cannot_expire(pact, direct_vm, direct_alice, direct_bob, direct_charlie):
    """Once a verdict lands, the deal has left the open lane: expiry is the
    exit for ABANDONED deals, not a second bite at reviewed work."""
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_pass(direct_vm)
    pact.run_review(did)  # SETTLED
    direct_vm.sender = direct_charlie
    _warp(direct_vm, DEADLINE + 6 * 3600 + 60)
    with pytest.raises(Exception, match="only open deals can expire"):
        pact.expire(did)
    assert int(pact.get_stats()["escrow"]) == 0


# ----------------------------------------------------------- state machine
def test_terminal_states_accept_nothing(pact, direct_vm, direct_alice, direct_bob):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_pass(direct_vm)
    pact.run_review(did)  # SETTLED
    with pytest.raises(Exception, match="no review pending"):
        pact.run_review(did)
    direct_vm.sender = direct_bob
    direct_vm.value = BOND
    with pytest.raises(Exception, match="nothing to appeal"):
        pact.appeal(did)
    direct_vm.value = 0
    with pytest.raises(Exception, match="only open deals"):
        pact.buyer_cancel(did)
    with pytest.raises(Exception, match="only open deals"):
        pact.expire(did)


def test_deliver_reverts_on_failed_deal(pact, direct_vm, direct_alice, direct_bob, direct_charlie):
    did = _create(pact, direct_vm, direct_alice)
    _deliver(pact, direct_vm, direct_bob, did)
    _mock_fail(direct_vm)
    pact.run_review(did)
    direct_vm.sender = direct_charlie
    with pytest.raises(Exception, match="not open for delivery"):
        pact.accept_and_deliver(did, DELIVER_URL, "too late")


# ------------------------------------------------------------------- views
def test_list_deals_pagination_and_mine(pact, direct_vm, direct_alice, direct_bob, direct_charlie):
    dids = []
    for who in (direct_alice, direct_bob, direct_charlie):
        dids.append(_create(pact, direct_vm, who, deadline=DEADLINE + 100 * len(dids)))
    page = pact.list_deals(0, 2, False)
    assert len(page) == 2
    assert int(page[0]["id"]) == dids[2]  # newest first
    direct_vm.sender = direct_bob
    mine_bob = pact.list_deals(0, 50, True)
    assert len(mine_bob) == 1
    assert int(mine_bob[0]["id"]) == dids[1]


def test_list_deals_reverts_bad_pagination(pact, direct_vm, direct_alice):
    with pytest.raises(Exception, match="bad pagination"):
        pact.list_deals(0, 51, False)


def test_get_deal_missing(pact, direct_vm, direct_alice):
    with pytest.raises(Exception, match="deal not found"):
        pact.get_deal(999)
