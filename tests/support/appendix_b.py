"""The 23 Appendix B rows of the fixture merge, shared by the merge and end-to-end tests."""

from typing import Any

WPN = "wikipedia:national-2026@rev1380221397"
WPL = "wikipedia:local-2026@rev1380378807"
DOT = " · "


def _eg(page: str, row: int) -> str:
    return f"served/electionguide:{page}/r{row}#0"


def _less(claim: str, reason: str = "less_certain") -> tuple[str, str]:
    return (claim, reason)


def _child(
    child_id: str,
    selected: str,
    *others: tuple[str, str],
    aggregate: bool = False,
    conflict: bool = False,
) -> tuple[Any, ...]:
    return (child_id, aggregate, conflict, ((selected, None), *others))


def _row(
    group_id: str,
    place: str,
    level: str,
    dates: str,
    date_status: str,
    status: str,
    type_: str,
    children: list[tuple[Any, ...]],
    umbrellas: list[str],
) -> tuple[Any, ...]:
    start, _, end = dates.partition(" to ")
    return (
        group_id,
        place,
        level,
        start,
        end or start,
        "day",
        "voting_period",
        date_status,
        status,
        type_,
        tuple(children),
        sorted(umbrellas),
    )


def appendix_b() -> list[tuple[Any, ...]]:
    n = f"served/{WPN}"
    local = f"served/{WPL}"
    governors = "2b844b3ca773 35eb32947fa0 073382e19da1 44bb208b4d0b 75fde6bff123 081cccbcc211 19387752fb15 1f89511d91cc d45e8a31e7a1 13df4c00d608 86e5eae386c7 876f29950cf7 6b25112ee8a5 fbfc708ccaaf 51f6dd2bcb50 e81e7ee84dc0 b8729ff253bf 3cfdd6789f20"
    return [
        _row("fcd48da30f32", "iso:SE", "national", "2026-09-13", "confirmed", "Held",
             "Swedish Parliament",
             [_child("451e4f4c0054", _eg("past", 13), _less("served/osce:elections/r34#0"),
                     _less(f"{n}/September/li[1]#0"))], []),
        _row("4f4a086286ed", "iso:SE", "subnational", "2026-09-13", "unknown", "Held",
             "regional and municipal elections",
             [_child("16b1e5c54480", f"{local}/September/li[4]/li[2]#0", aggregate=True)], []),
        _row("c7558bb61e25", "x:south-ossetia", "national", "2026-09-18", "unknown", "Held",
             "President", [_child("5f80a5eff1aa", f"{n}/September/li[2]#0")], []),
        _row("0854d007f42e", "iso:RU", "national", "2026-09-18 to 2026-09-20", "confirmed", "Held",
             "Russian State Duma",
             [_child("4856e73735ea", _eg("past", 12),
                     _less("served/osce:elections/r33#0", "not_covering"),
                     _less(f"{n}/September/li[3]#0"),
                     _less("served/aweb:calendar/r23#0", "not_covering"))], []),
        _row("af23c8e10357", "iso:MA", "national", "2026-09-23", "confirmed", "Held",
             "Moroccan Chamber of Representatives",
             [_child("b5e3f77c0c1b", _eg("past", 11), _less(f"{n}/September/li[4]#0"),
                     _less("served/ndi:p0/past-c5#0"), _less("served/eisa:y2026/r13#0"))], []),
        _row("2064e8f68b8c", "iso:IM", "national", "2026-09-24", "unknown", "Held",
             "House of Keys", [_child("b74251137bc8", f"{n}/September/li[5]#0")], []),
        _row("8818bc29cc27", "iso:ST", "national", "2026-09-27", "confirmed", "Held",
             "Sao Tomean National Assembly",
             [_child("2b76c271e7be", _eg("past", 10), _less(f"{n}/September/li[6]/li[1]#0"),
                     _less("served/ndi:p0/past-c4#0"), _less("served/eisa:y2026/r15#0"))], []),
        _row("54b356d5b5ea", "iso:BR", "national", "2026-10-04", "confirmed", "Held",
             f"Brazilian Presidency (1st round){DOT}Brazilian Chamber of Deputies{DOT}"
             "Brazilian Federal Senate",
             [_child("baa1bb5de7fe", _eg("past", 4), _less(f"{n}/October/li[2]/li[2]#0")),
              _child("219ff0785bdd", _eg("past", 7), _less(f"{n}/October/li[2]/li[2]#1")),
              _child("aefc0f383484", _eg("past", 3), _less(f"{n}/October/li[2]/li[2]#2"))],
             ["served/aweb:calendar/r25#0", "served/ndi:p0/past-c2#0"]),
        _row("c8c9844ab7a8", "iso:BR", "subnational", "2026-10-04", "unknown", "Held",
             "Governors: Alagoas, Amazonas, Bahia, Ceará, Espírito Santo, "
             "Federal District, Goiás, Maranhão, Minas Gerais, Pará, Paraíba, "
             "Paraná, Pernambuco, Rio de Janeiro, Rio Grande do Norte (+3 more) (18)",
             [_child(child_id, f"{local}/October/li[1]/li[1]/li[{i}]#0")
              for i, child_id in enumerate(governors.split(), start=1)],
             [f"{local}/October/li[1]/li[1]#0"]),
        _row("d01ed25c943e", "iso:PY", "subnational", "2026-10-04", "unknown", "Held",
             "municipal elections",
             [_child("9ea96cd48d74", f"{local}/October/li[1]/li[3]#0", aggregate=True)], []),
        _row("05f32126cb43", "iso:PE", "subnational", "2026-10-04", "unknown", "Held",
             "Lima: Mayor", [_child("1ba2f246cd98", f"{local}/October/li[1]/li[4]/li[1]#0")],
             ["served/ndi:p0/past-c1#0", f"{local}/October/li[1]/li[4]#0"]),
        _row("cc453aae6835", "iso:GB", "national", "2026-10-08", "unknown", "Held",
             "Holborn and St Pancras: House of Commons by-election",
             [_child("d5cc461fb60f", f"{local}/October/li[3]/li[2]#0")], []),
        _row("abf124b4c48f", "iso:CZ", "subnational", "2026-10-09 to 2026-10-10", "unknown",
             "Held", "municipal elections",
             [_child("fd0fffe821dc", f"{local}/October/li[4]#0", aggregate=True)], []),
        _row("d8b6179b8850", "iso:SK", "subnational", "2026-10-24", "unknown", "Upcoming",
             "regional and local elections",
             [_child("117d9dff3af3", f"{local}/October/li[9]/li[2]#0", aggregate=True)], []),
        _row("4b35f9d2401c", "iso:BR", "national", "2026-10-25", "confirmed", "Upcoming",
             "Brazilian Presidency (2nd round)",
             [_child("f90b0d7db440", _eg("upcoming", 3), _less(f"{n}/October/li[6]/li[3]#0"))],
             ["served/aweb:calendar/r27#0"]),
        _row("c5842ef99109", "iso:RS", "national", "2026-10-25", "confirmed", "Upcoming",
             "Serbian National Assembly",
             [_child("bcb7e2ccdf47", _eg("upcoming", 2), _less("served/osce:elections/r2#0"),
                     _less(f"{n}/October/li[6]/li[2]#0"),
                     _less("served/ndi:p0/upcoming-c2#0", "not_covering"),
                     _less("served/ipu:elections/r222#0", "lower_evidence"))], []),
        _row("f65719631682", "iso:GD", "national", "2026-11-05", "unknown", "Upcoming",
             "House of Representatives",
             [_child("1e8c23148913", f"{n}/November/li[2]#0",
                     _less("served/ipu:elections/r105#0", "lower_evidence"))], []),
        _row("32dd654de9aa", "iso:NZ", "national", "2026-11-07", "confirmed", "Upcoming",
             "New Zealand House of Representatives",
             [_child("1e8e1a5746c8", _eg("upcoming", 16), _less(f"{n}/November/li[3]#0"),
                     _less("served/ipu:elections/r180#0", "lower_evidence"))], []),
        _row("b65b9fe5b9b3", "iso:CV", "national", "2026-11-15", "confirmed", "Upcoming",
             "Cabo Verdean Presidency",
             [_child("eae5cc187a1a", _eg("upcoming", 17), _less(f"{n}/November/li[4]#0"),
                     _less("served/ndi:p0/upcoming-c4#0"),
                     _less("served/eisa:y2026/r7#0", "not_covering"), conflict=True)], []),
        _row("4e451911e2f5", "iso:SI", "subnational", "2026-11-15", "unknown", "Upcoming",
             "Local Elections",
             [_child("ca2bd502e0e0", "served/osce:elections/r4#0", aggregate=True)], []),
        _row("64539229886f", "iso:ES", "national", "2026-11-29", "confirmed", "Upcoming",
             f"Spanish Congress of Deputies{DOT}Spanish Senate",
             [_child("ad420bd35f9c", _eg("upcoming", 18), _less(f"{n}/November/li[5]/li[1]#1"),
                     _less("served/ipu:elections/r236#0", "lower_evidence")),
              _child("8199c9644471", _eg("upcoming", 19), _less(f"{n}/November/li[5]/li[1]#0"),
                     _less("served/ipu:elections/r237#0", "lower_evidence"))],
             ["served/osce:elections/r5#0"]),
        _row("4a02993930ce", "iso:CH", "national", "2026-11-29", "confirmed", "Upcoming",
             "Referendum",
             [_child("22e9f7b733fe", _eg("upcoming", 20), _less(f"{n}/November/li[5]/li[2]#0"))],
             []),
        _row("792ca8cad502", "iso:CZ", "national", "2026-10-09 to 2026-10-10", "confirmed",
             "Held", "Czech Senate (1st round)",
             [_child("d3df127ddfa9", _eg("past", 2), _less(f"{n}/October/li[3]#0"))], []),
    ]
