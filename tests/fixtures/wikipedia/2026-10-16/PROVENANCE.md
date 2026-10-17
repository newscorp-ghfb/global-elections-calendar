# Wikipedia electoral calendars (MediaWiki parse API), revisions current on 2026-10-16

- **URLs:** `https://en.wikipedia.org/w/api.php?action=parse&oldid=<revid>&prop=text%7Crevid&format=json&formatversion=2`
  for the revisions current when the HTML pages were captured on 2026-10-16:
  national-2026 1380221397, local-2026 1380378807, national-2027 1379360216, local-2027 1379495387
- **Fetched:** 2026-10-17, 16:13 UTC, through `Fetcher` + `trust_bundle` (HTTP 200,
  `application/json; charset=utf-8`, one attempt each)
- **Shape:** `{"parse": {"title", "pageid", "revid", "text"}}`; `text` is the page HTML
- **SHA-256 of `national-2026.json`:** 9e7c66703fe4fbcfc61e147c30679068e34ac73df177d9c7ab37684dc9622955
- **SHA-256 of `local-2026.json`:** dca4cc6dfc6646e786400de68761c99816210d27a445ed49c73037253f46769c
- **SHA-256 of `national-2027.json`:** 878908fe27271753034ff856f13d717afdc3b2a97586d2d878839c561040fa64
- **SHA-256 of `local-2027.json`:** 9b24f2b85dde3231cd6e2e4b2b9b7eb77d74326b27b9a678fc61a8c3f43d6652
- **Used by:** `tests/adapters/test_wikipedia_*.py`, `tests/unit/test_ledger.py`
