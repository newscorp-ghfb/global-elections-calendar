"""The request budget shared by the worker processes (P116, R30)."""

import multiprocessing
import pickle
from pathlib import Path

import pytest

from elections_calendar.fetch import RequestBudget
from tests.support.budget_workers import take_many

JOIN_S = 60


def test_request_budget_is_shared(tmp_path: Path) -> None:
    tokens = tmp_path / "budget"
    results = [tmp_path / f"result-{n}.txt" for n in range(4)]
    context = multiprocessing.get_context("spawn")
    children = [
        context.Process(target=take_many, args=(str(tokens), 40, 25, str(result)))
        for result in results
    ]
    try:
        for child in children:
            child.start()
        for child in children:
            child.join(JOIN_S)
        assert [child.exitcode for child in children] == [0, 0, 0, 0]
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
                child.join(JOIN_S)
    granted = [int(result.read_text(encoding="utf-8")) for result in results]
    assert sum(granted) == 40
    budget = RequestBudget(tokens, 40)
    assert budget.used() == 40
    assert len(list(tokens.glob("*.token"))) == 40
    assert budget.take() is False
    assert budget.used() == 40


def test_a_zero_budget_refuses_at_once_and_a_negative_one_is_an_error(tmp_path: Path) -> None:
    assert RequestBudget(tmp_path / "zero", 0).take() is False
    with pytest.raises(ValueError):
        RequestBudget(tmp_path / "negative", -1)


def test_a_pickled_budget_shares_the_count(tmp_path: Path) -> None:
    budget = RequestBudget(tmp_path / "budget", 3)
    copy = pickle.loads(pickle.dumps(budget))
    assert (copy.directory, copy.limit) == (budget.directory, 3)
    assert budget.take() and copy.take()
    assert (budget.used(), copy.used()) == (2, 2)
    assert budget.take() and not copy.take()


def test_used_counts_only_tokens_below_the_limit(tmp_path: Path) -> None:
    budget = RequestBudget(tmp_path / "budget", 2)
    (budget.directory / "5.token").write_bytes(b"")
    (budget.directory / "other.txt").write_bytes(b"")
    assert budget.used() == 0
    assert budget.take()
    assert budget.used() == 1
