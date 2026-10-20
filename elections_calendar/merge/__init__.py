"""The merge (spec section 10): claims in, contests and cards out.

Modules: ``identity`` (source priority, roles, identity and date compatibility, rule F,
short ids), ``select`` (date selection and status), ``match`` (phases A-D, umbrellas,
aggregates), ``cards`` (children, cards, listings, attention items, dispositions) and
``conservation`` (the audit). ``merge`` runs them in that order and fails closed. The package
imports only from ``model``, ``text``, ``dates``, ``offices``, ``places`` and ``window``, and
from its own modules.
"""

from collections.abc import Iterable
from datetime import datetime

from elections_calendar.merge.cards import build
from elections_calendar.merge.conservation import check
from elections_calendar.merge.identity import MergeError
from elections_calendar.merge.match import match
from elections_calendar.model import Claim, MergeResult
from elections_calendar.places import PlaceRegistry
from elections_calendar.window import window_for

__all__ = ["MergeError", "merge"]


def merge(claims: Iterable[Claim], *, now: datetime, places: PlaceRegistry) -> MergeResult:
    """Merge claims into cards, then audit the result; any problem raises ``MergeError``.

    Any iterable of claims is accepted; it is read once, into a tuple.
    """
    claims = tuple(claims)
    window = window_for(now)
    matching = match(claims, now)
    result = build(matching, window=window, places=places)
    problems = check(claims, result)
    if problems:
        raise MergeError("conservation: " + "; ".join(problems))
    return result
