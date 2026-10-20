"""The fixture claims that the merge tests build on."""

from collections import Counter

from elections_calendar.ledger import check
from tests.support.fixture_claims import fixture_claims, fixture_results


def test_fixture_claims() -> None:
    claims = fixture_claims()
    assert Counter(c.source for c in claims) == {
        "electionguide": 243,
        "wikipedia": 543,
        "osce": 180,
        "ipu": 234,
        "aweb": 31,
        "carter": 18,
        "eeas": 23,
        "ndi": 38,
        "eisa": 25,
    }
    assert len(claims) == 1335
    for source, (raw, parsed) in fixture_results().items():
        assert check(raw, parsed).ok, source
    assert len({c.claim_id for c in claims}) == len(claims)
    assert fixture_claims() is fixture_claims()
