"""HTTP fetching (spec §8).

One ``Fetcher`` per source; requests within a source run one at a time.
Every request ends in a ``FetchResult`` with an outcome; nothing raises to
the adapter and nothing returns ``None`` silently. The one exception is
local configuration: a ``verify`` path that does not exist raises ``OSError``.

- 3 attempts in total (first try + 2 retries), waiting 2 s then 4 s, or
  ``Retry-After`` (seconds or HTTP-date, capped at 60 s). Only transient
  failures are retried: timeouts, connection and DNS errors, 429/5xx and
  MediaWiki ``maxlag``.
- Each attempt has a time limit (60 s). It is checked before every request,
  redirect hops included, and between reads of the body, so a server that
  drips bytes cannot hold an attempt open; a single socket read waits at most
  the time that was left when its request was sent. If the limit passes
  during the read that brings the last byte of a body with a Content-Length,
  the body is complete and is kept.
- Bodies over ``max_bytes`` are refused. A redirect's body is never read.
- At most 5 redirects, https only; TLS is verified on every hop.
- The caller's ``Deadline`` (4 min per source, 12 min per scrape) bounds
  attempts and back-off waits.
- These are inactivity limits and cooperative checks, not a wall-clock
  bound. Name resolution (``getaddrinfo`` takes no timeout), connecting to
  each resolved address in turn (each try has its own connect timeout) and a
  server that sends its headers a few bytes at a time can all run longer.
  The hard bound will be the runner (a later plan; not built yet), which
  fetches each source in a child process and kills it at the source's
  deadline.
- URLs and error texts are redacted before they are stored: only values of
  the sources' own query keys (``SAFE_QUERY_KEYS``) are kept. A MediaWiki
  error code outside its grammar becomes ``INVALID_API_CODE``. The body is
  kept raw, so ``diagnostics()`` is what may be published.
"""

import email.utils
import json
import os
import re
import socket
import ssl
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self
from urllib.parse import unquote_plus, urljoin, urlsplit, urlunsplit

import certifi
import requests
import urllib3
from requests.utils import resolve_proxies

from elections_calendar.model import FetchOutcome

ATTEMPTS = 3
BACKOFF_S = (2.0, 4.0)
RETRY_AFTER_CAP_S = 60.0
ATTEMPT_TIMEOUT_S = 60.0
MAX_REDIRECTS = 5
MAX_BYTES = 20 * 1024 * 1024
SOURCE_DEADLINE_S = 4 * 60.0
SCRAPE_DEADLINE_S = 12 * 60.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
WIKIPEDIA_UA = (
    "global-elections-calendar/2.0 (+https://github.com/newscorp-ghfb/global-elections-calendar)"
)
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)
ENV_CA_BUNDLES = ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE")

_READ_SIZE = 65536
_CHALLENGE = re.compile(
    rb"<title>\s*(?:just a moment|access denied|attention required)"
    rb"|cf-chl-|_cf_chl_opt|/cdn-cgi/challenge-platform/"
    rb"|sucuri website firewall|sucuri_cloudproxy",
    re.IGNORECASE,
)
# The sources' own query keys (spec §7); diagnostics keep their values. Any
# other parameter is replaced whole, key included: a token can stand where a
# key would ("?dG9rZW4=").
SAFE_QUERY_KEYS = frozenset({
    "action", "page", "prop", "format", "formatversion", "maxlag",  # Wikipedia API; NDI page
    "menuno", "option",  # A-WEB
    "table_id", "target_action",  # EISA
})  # fmt: skip
REDACTED = "REDACTED"
INVALID_API_CODE = "(invalid)"
_API_CODE = re.compile(r"[A-Za-z0-9_-]{1,64}")
_URL_IN_TEXT = re.compile(r"https?://[^\s'\"<>]+")
_QUERY_IN_TEXT = re.compile(r"(?P<lead>[?#])(?P<query>[^\s'\"<>]+)")
_PAIR_SEPARATOR = re.compile(r"([&;])")


@dataclass(frozen=True, slots=True)
class Deadline:
    """An absolute limit on the monotonic clock."""

    expires_at: float
    clock: Callable[[], float] = time.monotonic

    @classmethod
    def after(cls, seconds: float, clock: Callable[[], float] = time.monotonic) -> Deadline:
        return cls(clock() + seconds, clock)

    def remaining(self) -> float:
        return self.expires_at - self.clock()

    def earliest(self, other: Deadline) -> Deadline:
        return self if self.expires_at <= other.expires_at else other


@dataclass(frozen=True, slots=True)
class FetchResult:
    """What ``Fetcher.get`` returns.

    ``url``, ``final_url``, ``error`` and ``api_code`` are redacted. ``body`` is
    the raw response and may echo anything the request carried: publish
    ``diagnostics()``, never the result or its body.
    """

    url: str
    final_url: str
    outcome: FetchOutcome
    stage: str
    http_status: int | None
    content_type: str | None
    body: bytes
    elapsed_ms: int
    attempts: int
    error_type: str | None = None
    error: str | None = None
    api_code: str | None = None

    @property
    def ok(self) -> bool:
        return self.outcome == "ok"

    def text(self) -> str:
        """The body decoded with the Content-Type charset (UTF-8 if none or unknown)."""
        charset = "utf-8"
        if self.content_type and "charset=" in self.content_type.casefold():
            declared = self.content_type.casefold().split("charset=", 1)[1]
            charset = declared.split(";")[0].strip()
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    def diagnostics(self) -> dict[str, object]:
        return {
            "outcome": self.outcome,
            "stage": self.stage,
            "http_status": self.http_status,
            "final_url": self.final_url,
            "content_type": self.content_type,
            "bytes": len(self.body),
            "elapsed_ms": self.elapsed_ms,
            "attempts": self.attempts,
            "error_type": self.error_type,
            "error": self.error,
            "api_code": self.api_code,
        }


@dataclass(frozen=True, slots=True)
class _Attempt:
    outcome: FetchOutcome
    stage: str
    final_url: str
    http_status: int | None = None
    content_type: str | None = None
    body: bytes = b""
    error_type: str | None = None
    error: str | None = None
    api_code: str | None = None
    retryable: bool = False
    retry_after: float | None = None


class Fetcher:
    def __init__(
        self,
        *,
        verify: str,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        attempt_timeout: float = ATTEMPT_TIMEOUT_S,
        max_bytes: int = MAX_BYTES,
    ) -> None:
        if not verify:
            raise ValueError("TLS verification needs a CA bundle path")
        self._verify = verify
        self._clock = clock
        self._sleep = sleep
        self._wall_clock = wall_clock
        self._attempt_timeout = attempt_timeout
        self._max_bytes = max_bytes
        self._session = requests.Session()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._session.close()

    def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult:
        started = self._clock()
        attempt: _Attempt | None = None
        for number in range(1, ATTEMPTS + 1):
            remaining = deadline.remaining()
            if remaining <= 0:
                return self._result(url, started, number - 1, _deadline(url, attempt))
            attempt = self._attempt(url, min(self._attempt_timeout, remaining), mediawiki)
            if attempt.outcome == "ok" or not attempt.retryable or number == ATTEMPTS:
                return self._result(url, started, number, attempt)
            wait = BACKOFF_S[number - 1] if attempt.retry_after is None else attempt.retry_after
            wait = min(wait, RETRY_AFTER_CAP_S)
            if wait >= deadline.remaining():
                return self._result(url, started, number, _deadline(url, attempt))
            self._sleep(wait)
        raise AssertionError("unreachable: the last attempt always returns")

    def _result(self, url: str, started: float, attempts: int, a: _Attempt) -> FetchResult:
        return FetchResult(
            url=redact_url(url),
            final_url=a.final_url,
            outcome=a.outcome,
            stage=a.stage,
            http_status=a.http_status,
            content_type=a.content_type,
            body=a.body,
            elapsed_ms=int((self._clock() - started) * 1000),
            attempts=attempts,
            error_type=a.error_type,
            error=a.error,
            api_code=a.api_code,
        )

    def _attempt(self, url: str, timeout: float, mediawiki: bool) -> _Attempt:
        current = url
        attempt_ends = self._clock() + timeout
        for hop in range(MAX_REDIRECTS + 1):
            left = attempt_ends - self._clock()
            if left <= 0:
                return _Attempt(
                    "timeout", "redirect" if hop else "request", redact_url(current),
                    error="attempt time limit reached before the request was sent",
                    retryable=True,
                )  # fmt: skip
            try:
                parts = urlsplit(current)
                if parts.scheme != "https":
                    return _Attempt(
                        "fetch_failed", "redirect", redact_url(current),
                        error=f"refusing a non-https URL: {redact_url(current)}",
                    )  # fmt: skip
                response = self._send(current, parts.hostname or "", left)
            except (requests.exceptions.RequestException, ValueError) as exc:
                return _failure(exc, "request", current)
            with response:  # closing an unread response drops its connection
                if response.is_redirect:
                    try:
                        current = urljoin(current, response.headers["Location"])
                    except ValueError as exc:
                        return _failure(exc, "redirect", current)
                    continue
                return self._read(response, current, attempt_ends, mediawiki)
        return _Attempt(
            "fetch_failed", "redirect", redact_url(current),
            error=f"more than {MAX_REDIRECTS} redirects",
        )  # fmt: skip

    def _send(self, url: str, host: str, timeout: float) -> requests.Response:
        """One GET through the session's adapter, with no redirect handling.

        ``Session.send`` reads a redirect's whole body even with
        ``allow_redirects=False`` (requests 2.34 prepares ``Response.next``),
        with no size or time limit, so the adapter sends the request. The
        session's cookies and proxy settings apply as they would there.
        """
        session = self._session
        request = session.prepare_request(
            requests.Request("GET", url, headers={"User-Agent": user_agent(host)})
        )
        proxies = resolve_proxies(request, dict(session.proxies), session.trust_env)
        response = session.get_adapter(url).send(
            request, stream=True, timeout=timeout, verify=self._verify, proxies=proxies
        )
        session.cookies.update(response.cookies)
        return response

    def _read(
        self, response: requests.Response, url: str, attempt_ends: float, mediawiki: bool
    ) -> _Attempt:
        final_url = redact_url(url)
        status = response.status_code
        content_type = response.headers.get("Content-Type")
        chunks: list[bytes] = []
        size = 0
        try:
            while True:
                if self._clock() >= attempt_ends and not _received_all(response):
                    return _Attempt(
                        "timeout", "read", final_url, status, content_type,
                        error="attempt time limit reached while reading the body",
                        retryable=True,
                    )  # fmt: skip
                # read1 returns what one socket read brings; read() would wait
                # for a whole chunk and let a dripping server outlast the limit.
                chunk = response.raw.read1(_READ_SIZE, decode_content=True)
                if not chunk:
                    break
                size += len(chunk)
                if size > self._max_bytes:
                    return _Attempt(
                        "fetch_failed", "read", final_url, status, content_type,
                        error=f"response larger than {self._max_bytes} bytes",
                    )  # fmt: skip
                chunks.append(chunk)
        except (requests.exceptions.RequestException, urllib3.exceptions.HTTPError) as exc:
            failed = _failure(exc, "read", url)
            return _Attempt(
                failed.outcome, "read", final_url, status, content_type,
                error_type=failed.error_type, error=failed.error, retryable=failed.retryable,
            )  # fmt: skip
        body = b"".join(chunks)
        if status >= 400:
            retry_after = parse_retry_after(response.headers.get("Retry-After"), self._wall_clock)
            return _Attempt(
                "http_error", "http", final_url, status, content_type, body,
                error=f"HTTP {status}",
                retryable=status in RETRY_STATUSES,
                retry_after=retry_after,
            )  # fmt: skip
        if _is_html(content_type) and _CHALLENGE.search(body[:_READ_SIZE]):
            return _Attempt(
                "challenge_page", "challenge", final_url, status, content_type, body,
                error="challenge or block page instead of content",
            )  # fmt: skip
        if mediawiki:
            return _mediawiki(final_url, status, content_type, body, response, self._wall_clock)
        return _Attempt("ok", "done", final_url, status, content_type, body)


def _received_all(response: requests.Response) -> bool:
    """Whether every byte of a body with a Content-Length has arrived."""
    return response.raw.length_remaining == 0


def _deadline(url: str, last: _Attempt | None) -> _Attempt:
    detail = f"; last attempt: {last.outcome} at {last.stage}" if last else ""
    return _Attempt(
        "deadline",
        "deadline",
        last.final_url if last else redact_url(url),
        http_status=last.http_status if last else None,
        error=f"deadline reached{detail}",
    )


def _mediawiki(
    final_url: str,
    status: int,
    content_type: str | None,
    body: bytes,
    response: requests.Response,
    wall_clock: Callable[[], datetime],
) -> _Attempt:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):  # nested too deep for json
        return _Attempt(
            "api_error", "api", final_url, status, content_type, body,
            error="MediaWiki response is not JSON",
        )  # fmt: skip
    error = data.get("error") if isinstance(data, dict) else None
    if error is None:
        return _Attempt("ok", "done", final_url, status, content_type, body)
    code = str(error.get("code", "")) if isinstance(error, dict) else ""
    info = str(error.get("info", "")) if isinstance(error, dict) else str(error)
    return _Attempt(
        "api_error", "api", final_url, status, content_type, body,
        error=redact_text(f"MediaWiki error {_api_code(code) or ''}: {info}"),
        api_code=_api_code(code),
        retryable=code == "maxlag",
        retry_after=parse_retry_after(response.headers.get("Retry-After"), wall_clock),
    )  # fmt: skip


def _api_code(code: str) -> str | None:
    """A MediaWiki error code fit to publish: its own grammar, else ``INVALID_API_CODE``."""
    if not code:
        return None
    return code if _API_CODE.fullmatch(code) else INVALID_API_CODE


def outcome_for(exc: Exception) -> tuple[FetchOutcome, bool]:
    """The outcome of a failed request and whether it is worth retrying.

    TLS errors and timeouts are checked first: requests raises both as
    subclasses of ConnectionError.
    """
    if isinstance(exc, (requests.exceptions.SSLError, urllib3.exceptions.SSLError)):
        return "tls_error", False
    if isinstance(exc, (requests.exceptions.Timeout, urllib3.exceptions.ReadTimeoutError)):
        return "timeout", True
    if isinstance(exc, (requests.exceptions.ConnectionError, urllib3.exceptions.ProtocolError)):
        return ("dns_error" if _is_dns_failure(exc) else "fetch_failed"), True
    return "fetch_failed", False


def _failure(exc: Exception, stage: str, url: str) -> _Attempt:
    outcome, retryable = outcome_for(exc)
    return _Attempt(
        outcome,
        "tls" if outcome == "tls_error" else stage,
        redact_url(url),
        error_type=type(exc).__name__,
        error=redact_text(str(exc)),
        retryable=retryable,
    )


def _is_dns_failure(exc: BaseException) -> bool:
    """Whether a name-resolution error is anywhere in the exception's chain."""
    seen: set[int] = set()
    stack: list[BaseException] = [exc]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, (urllib3.exceptions.NameResolutionError, socket.gaierror)):
            return True
        linked = [current.__cause__, current.__context__, getattr(current, "reason", None)]
        linked.extend(current.args)
        stack.extend(e for e in linked if isinstance(e, BaseException))
    return False


def _is_html(content_type: str | None) -> bool:
    return content_type is None or "html" in content_type.casefold()


def user_agent(host: str) -> str:
    """Wikipedia gets the project's bot User-Agent (no personal email); others a browser's."""
    host = host.casefold()
    if host == "wikipedia.org" or host.endswith(".wikipedia.org"):
        return WIKIPEDIA_UA
    return BROWSER_UA


def parse_retry_after(value: str | None, wall_clock: Callable[[], datetime]) -> float | None:
    """Seconds to wait from a Retry-After header (delta-seconds or HTTP-date).

    None when the header is missing or unreadable; the caller then uses its
    own back-off. Only ASCII digits are seconds; a number too large for a
    float is ``inf``, which the caller's cap turns into 60 s.
    """
    if not value:
        return None
    text = value.strip()
    if text.isascii() and text.isdigit():  # isdigit alone also accepts other scripts' digits
        return float(text)  # int() would refuse thousands of digits
    try:
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):  # a number too large for C
        return None
    if when.utcoffset() is None:
        when = when.replace(tzinfo=UTC)  # "-0000" dates are UTC with no zone named
    return max(0.0, (when - wall_clock()).total_seconds())


def redact_url(url: str) -> str:
    """Drop user info and the fragment; redact the query (``redact_query``)."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "<unparseable URL>"
    if ":" in host:
        host = f"[{host}]"  # IPv6
    query = redact_query(parts.query) if parts.query else ""
    return urlunsplit((parts.scheme, host + port, parts.path, query, ""))


def redact_query(query: str) -> str:
    """Keep the parameters whose key is in SAFE_QUERY_KEYS; replace each other one whole.

    Keys are compared percent-decoded (repeatedly) and case-folded, so
    ``%61ction`` and ``Action`` are ``action``.
    """
    parts = _PAIR_SEPARATOR.split(query)  # pairs at even positions, separators between
    return "".join(
        part if i % 2 or not part or _query_key(part) in SAFE_QUERY_KEYS else REDACTED
        for i, part in enumerate(parts)
    )


def _query_key(pair: str) -> str:
    key = pair.partition("=")[0]
    while (decoded := unquote_plus(key)) != key:
        key = decoded
    return key.casefold()


def redact_text(text: str, limit: int = 500) -> str:
    """Redact every URL in ``text`` and every bare ``?query`` or ``#fragment``; cap its length.

    Error texts quote URLs without a scheme ("url: /w/api.php?token=...").
    """
    text = _URL_IN_TEXT.sub(lambda m: redact_url(m.group()), text)
    text = _QUERY_IN_TEXT.sub(lambda m: m["lead"] + redact_query(m["query"]), text)
    return text[:limit]


class TrustBundleError(Exception):
    """The file a CA-bundle variable names cannot be read or holds no PEM certificate."""


@dataclass(frozen=True, slots=True)
class TrustBundle:
    path: Path
    sources: tuple[str, ...]  # "certifi", then the variable that named the machine bundle


def trust_bundle(dest: Path, environ: Mapping[str, str] = os.environ) -> TrustBundle:
    """Write one CA file: certifi's roots plus the machine's configured bundle.

    certifi alone should verify every source on a plain network such as CI
    (OSCE's emSign chain included); the branch CI run is still to confirm it.
    On a machine whose TLS is intercepted by a corporate proxy, the proxy's
    root is only in the machine bundle, and that
    bundle alone lacks roots for the sites the proxy lets through untouched.

    The machine bundle is the PEM file named by the first of
    REQUESTS_CA_BUNDLE, SSL_CERT_FILE and CURL_CA_BUNDLE that is set and not
    empty; the others are ignored. A named file that is missing, unreadable or
    holds no certificate raises TrustBundleError instead of being skipped.
    Verification stays on everywhere; nothing is trusted that neither file lists.
    """
    parts, sources = [Path(certifi.where()).read_bytes()], ["certifi"]
    name = next((n for n in ENV_CA_BUNDLES if environ.get(n)), None)
    if name is not None:
        configured = Path(environ[name])
        try:
            ssl.create_default_context().load_verify_locations(cafile=configured)
            parts.append(configured.read_bytes())
        except OSError as exc:  # ssl.SSLError is an OSError
            raise TrustBundleError(f"{name}={configured} is not a usable CA bundle: {exc}") from exc
        sources.append(name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\n".join(parts))
    return TrustBundle(dest, tuple(sources))
