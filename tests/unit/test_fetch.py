"""HTTP fetching (spec §8, §13.4).

Requests go to a local HTTPS server with real TLS; sleeps and the clock are
fake unless a test is about elapsed time.
"""

import json
import socket
import time
from datetime import UTC, datetime
from pathlib import Path

import certifi
import pytest
import requests
import urllib3

from elections_calendar.fetch import (
    ATTEMPT_TIMEOUT_S,
    BROWSER_UA,
    INVALID_API_CODE,
    MAX_BYTES,
    WIKIPEDIA_UA,
    Deadline,
    Fetcher,
    FetchResult,
    TrustBundleError,
    outcome_for,
    parse_retry_after,
    redact_text,
    redact_url,
    trust_bundle,
    user_agent,
)
from tests.support.http_server import Reply, TestServer, serve
from tests.unit.conftest import Pki

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


class FakeTime:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def fake() -> FakeTime:
    return FakeTime()


def fetcher(
    pki: Pki,
    fake: FakeTime,
    *,
    attempt_timeout: float = ATTEMPT_TIMEOUT_S,
    max_bytes: int = MAX_BYTES,
) -> Fetcher:
    return Fetcher(
        verify=str(pki.bundle),
        clock=fake.clock,
        sleep=fake.sleep,
        wall_clock=lambda: NOW,
        attempt_timeout=attempt_timeout,
        max_bytes=max_bytes,
    )


def get(
    pki: Pki,
    fake: FakeTime,
    url: str,
    *,
    mediawiki: bool = False,
    attempt_timeout: float = ATTEMPT_TIMEOUT_S,
    max_bytes: int = MAX_BYTES,
) -> FetchResult:
    """One request with the full source deadline (4 min) on the fake clock."""
    with fetcher(pki, fake, attempt_timeout=attempt_timeout, max_bytes=max_bytes) as f:
        return f.get(url, deadline=Deadline.after(240, fake.clock), mediawiki=mediawiki)


# -- success ----------------------------------------------------------------


def test_ok_returns_the_body_and_diagnostics(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    url = server.route("/page", Reply(body="<p>Grüße</p>".encode()))
    result = get(pki, fake, url)
    assert result.ok
    assert result.text() == "<p>Grüße</p>"
    assert (result.http_status, result.attempts, result.final_url) == (200, 1, url)
    assert result.diagnostics()["bytes"] == len("<p>Grüße</p>".encode())
    assert result.diagnostics()["stage"] == "done"
    assert fake.sleeps == []


def test_text_uses_the_declared_charset(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    url = server.route(
        "/cp1252",
        Reply(body="Sí, São Tomé".encode("cp1252"), content_type='text/html; charset="windows-1252"'),
    )
    assert get(pki, fake, url).text() == "Sí, São Tomé"


def test_text_falls_back_to_utf8_for_an_unknown_charset() -> None:
    result = FetchResult(
        "u", "u", "ok", "done", 200, "text/html; charset=x-nonsense", "é".encode(), 0, 1
    )
    assert result.text() == "é"


def test_hosts_get_their_user_agent(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    get(pki, fake, server.route("/ua", Reply(body=b"ok")))
    assert server.requests[0].headers["User-Agent"] == BROWSER_UA
    assert user_agent("en.wikipedia.org") == WIKIPEDIA_UA
    assert user_agent("EN.Wikipedia.ORG") == WIKIPEDIA_UA
    assert user_agent("notwikipedia.org") == BROWSER_UA
    assert user_agent("wikipedia.org.example.net") == BROWSER_UA
    assert "@" not in WIKIPEDIA_UA  # no personal email


# -- retries ----------------------------------------------------------------


def test_transient_statuses_are_retried_with_backoff(
    pki: Pki, fake: FakeTime, server: TestServer
) -> None:
    url = server.route("/flaky", Reply(status=503), Reply(status=502), Reply(body=b"ok"))
    result = get(pki, fake, url)
    assert result.ok and result.attempts == 3
    assert fake.sleeps == [2.0, 4.0]


def test_retries_stop_after_three_attempts(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    url = server.route("/down", Reply(status=503))
    result = get(pki, fake, url)
    assert (result.outcome, result.http_status, result.attempts) == ("http_error", 503, 3)
    assert len(server.requests) == 3
    assert fake.sleeps == [2.0, 4.0]


@pytest.mark.parametrize("status", [400, 403, 404, 410])
def test_client_errors_are_not_retried(
    pki: Pki, fake: FakeTime, server: TestServer, status: int
) -> None:
    result = get(pki, fake, server.route("/gone", Reply(status=status)))
    assert (result.outcome, result.http_status, result.attempts) == ("http_error", status, 1)
    assert fake.sleeps == []


@pytest.mark.parametrize(
    ("header", "sleeps"),
    [
        ("7", [7.0, 7.0]),
        ("3600", [60.0, 60.0]),  # capped
        ("soon", [2.0, 4.0]),  # unreadable: default back-off
        ("Fri, 16 Oct 2026 12:00:10 GMT", [10.0, 10.0]),  # HTTP-date, 10 s after NOW
    ],
)
def test_retry_after_is_honoured_and_capped(
    pki: Pki, fake: FakeTime, server: TestServer, header: str, sleeps: list[float]
) -> None:
    url = server.route("/busy", Reply(status=429, headers={"Retry-After": header}))
    result = get(pki, fake, url)
    assert (result.outcome, result.attempts) == ("http_error", 3)
    assert fake.sleeps == sleeps


@pytest.mark.parametrize(
    ("header", "seconds"),
    [
        (None, None),
        ("", None),
        (" 5 ", 5.0),
        ("-1", None),
        ("1.5", None),
        ("Fri, 16 Oct 2026 12:00:10 -0000", 10.0),  # no zone named: UTC
        ("Fri, 16 Oct 2026 14:00:10 +0200", 10.0),
        ("Thu, 15 Oct 2026 12:00:00 GMT", 0.0),  # in the past
        ("Fri, 32 Oct 2026 12:00:00 GMT", None),
        ("\u00b2", None),  # a superscript two is a digit to str.isdigit, not a number
        ("0" * 20 + "5", 5.0),
        ("9" * 5000, float("inf")),  # past any cap; int() would refuse it
        ("Mon, 01 Jan " + "9" * 20 + " 00:00:00 GMT", None),  # a year too large for C
        ("Mon, 01 Jan 2026 00:00:00 +" + "9" * 20, None),  # an offset too large for C
    ],
)
def test_parse_retry_after(header: str | None, seconds: float | None) -> None:
    assert parse_retry_after(header, lambda: NOW) == seconds


@pytest.mark.parametrize(
    ("header", "sleeps"),
    [
        ("\u00b2", [2.0, 4.0]),  # unreadable: default back-off
        ("9" * 400, [60.0, 60.0]),  # too large for a float: capped
        ("9" * 5000, [60.0, 60.0]),  # too long for int(): capped
        ("Mon, 01 Jan " + "9" * 20 + " 00:00:00 GMT", [2.0, 4.0]),  # unreadable date
    ],
)
def test_a_malformed_retry_after_never_escapes_the_result(
    pki: Pki, fake: FakeTime, server: TestServer, header: str, sleeps: list[float]
) -> None:
    url = server.route("/busy", Reply(status=503, headers={"Retry-After": header}))
    result = get(pki, fake, url)
    assert (result.outcome, result.http_status, result.attempts) == ("http_error", 503, 3)
    assert fake.sleeps == sleeps


def test_timeouts_are_retried(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    url = server.route("/slow", Reply(delay=1.0, body=b"late"), Reply(body=b"ok"))
    result = get(pki, fake, url, attempt_timeout=0.3)
    assert result.ok and result.attempts == 2 and result.body == b"ok"
    assert fake.sleeps == [2.0]


def test_a_dripping_body_cannot_outlast_the_attempt_limit(
    pki: Pki, fake: FakeTime, server: TestServer
) -> None:
    url = server.route("/drip", Reply(body=b"x" * 400, drip=0.05))  # 2 s to send
    started = time.monotonic()
    with Fetcher(verify=str(pki.bundle), sleep=fake.sleep, attempt_timeout=0.3) as f:
        result = f.get(url, deadline=Deadline.after(30))
    assert (result.outcome, result.stage, result.attempts) == ("timeout", "read", 3)
    assert time.monotonic() - started < 3 * 0.3 + 1.0


def test_an_oversized_body_is_refused(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    result = get(pki, fake, server.route("/big", Reply(body=b"x" * 5000)), max_bytes=1000)
    assert (result.outcome, result.stage, result.attempts) == ("fetch_failed", "read", 1)
    assert result.body == b""


def test_a_body_completed_by_the_read_that_crossed_the_limit_is_kept(
    pki: Pki, fake: FakeTime, server: TestServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_read1 = urllib3.HTTPResponse.read1

    def late_read1(
        self: urllib3.HTTPResponse, amt: int | None = None, decode_content: bool | None = None
    ) -> bytes:
        data = real_read1(self, amt, decode_content)
        if data and self.length_remaining == 0:
            fake.now += 100  # the read that brought the last byte ended after the limit
        return data

    monkeypatch.setattr(urllib3.HTTPResponse, "read1", late_read1)
    result = get(pki, fake, server.route("/page", Reply(body=b"x" * 30)))
    assert (result.outcome, result.body, result.attempts) == ("ok", b"x" * 30, 1)


# -- deadlines --------------------------------------------------------------


def test_the_deadline_stops_a_wait_it_cannot_afford(
    pki: Pki, fake: FakeTime, server: TestServer
) -> None:
    url = server.route("/busy", Reply(status=503, headers={"Retry-After": "30"}))
    with fetcher(pki, fake) as f:
        result = f.get(url, deadline=Deadline.after(40, fake.clock))
    assert (result.outcome, result.attempts, result.http_status) == ("deadline", 2, 503)
    assert fake.sleeps == [30.0]
    assert result.error is not None and "http_error" in result.error


def test_no_request_is_sent_once_the_attempt_limit_has_passed(
    pki: Pki, fake: FakeTime, server: TestServer
) -> None:
    url = server.route("/a", Reply(status=302, headers={"Location": "/b"}))
    server.route("/b", Reply(body=b"ok"))

    def clock() -> float:  # 100 s pass while /a is answered
        return fake.now + (100.0 if server.requests else 0.0)

    with Fetcher(verify=str(pki.bundle), clock=clock, sleep=fake.sleep) as f:
        result = f.get(url, deadline=Deadline.after(90, clock))
    assert (result.outcome, result.attempts) == ("deadline", 1)
    assert result.error == "deadline reached; last attempt: timeout at redirect"
    assert [r.path for r in server.requests] == ["/a"]


def test_a_spent_deadline_makes_no_request(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    url = server.route("/page", Reply(body=b"ok"))
    with fetcher(pki, fake) as f:
        result = f.get(url, deadline=Deadline(fake.now, fake.clock))
    assert (result.outcome, result.attempts) == ("deadline", 0)
    assert server.requests == []


def test_deadline_helpers(fake: FakeTime) -> None:
    short, long = Deadline.after(10, fake.clock), Deadline.after(20, fake.clock)
    assert short.earliest(long) is short and long.earliest(short) is short
    fake.sleep(4)
    assert short.remaining() == 6


# -- redirects --------------------------------------------------------------


def test_relative_redirects_are_followed(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    url = server.route("/a", Reply(status=302, headers={"Location": "/b"}))
    server.route("/b", Reply(status=301, headers={"Location": "c"}))
    server.route("/c", Reply(body=b"here"))
    result = get(pki, fake, url)
    assert result.ok and result.final_url == server.url("/c")
    assert [r.path for r in server.requests] == ["/a", "/b", "/c"]


def test_more_than_five_redirects_fail(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    url = server.route("/loop", Reply(status=302, headers={"Location": "/loop"}))
    result = get(pki, fake, url)
    assert (result.outcome, result.stage, result.attempts) == ("fetch_failed", "redirect", 1)
    assert len(server.requests) == 6  # the request and five redirects
    assert result.error == "more than 5 redirects"


def test_a_redirect_body_is_never_read(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    slow = Reply(status=302, headers={"Location": "/b"}, body=b"x" * 100, drip=0.5)  # 5 s
    url = server.route("/a", slow)
    server.route("/b", Reply(body=b"here"))
    started = time.monotonic()
    result = get(pki, fake, url)
    assert result.ok and result.body == b"here"
    assert time.monotonic() - started < 2.0


def test_cookies_set_by_a_redirect_are_sent_on(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    headers = {"Location": "/b", "Set-Cookie": "consent=yes; Path=/"}
    url = server.route("/a", Reply(status=302, headers=headers))
    server.route("/b", Reply(body=b"here"))
    assert get(pki, fake, url).ok
    assert server.requests[1].headers.get("Cookie") == "consent=yes"


def test_a_redirect_to_http_is_refused(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    plain = server.url("/plain").replace("https://", "http://")
    url = server.route("/down", Reply(status=301, headers={"Location": plain}))
    result = get(pki, fake, url)
    assert (result.outcome, result.stage) == ("fetch_failed", "redirect")
    assert [r.path for r in server.requests] == ["/down"]
    assert get(pki, fake, plain).outcome == "fetch_failed"
    assert len(server.requests) == 1


# -- content checks ---------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        b"<html><head><title>Just a moment...</title></head></html>",
        b"<html><head><TITLE>Access denied | example.org</TITLE></head></html>",
        b"<html><head><title>Attention Required! | Cloudflare</title></head></html>",
        b"<html><script>window._cf_chl_opt={}</script></html>",
        b"<html><title>Sucuri WebSite Firewall - Access Denied</title></html>",
    ],
)
def test_challenge_pages_are_detected(
    pki: Pki, fake: FakeTime, server: TestServer, body: bytes
) -> None:
    result = get(pki, fake, server.route("/cf", Reply(body=body)))
    assert (result.outcome, result.attempts) == ("challenge_page", 1)


def test_challenge_words_outside_a_title_or_in_json_are_content(
    pki: Pki, fake: FakeTime, server: TestServer
) -> None:
    prose = server.route("/prose", Reply(body=b"<p>Access denied to observers, says EISA</p>"))
    data = server.route("/json", Reply(body=b'{"note": "cf-chl-"}', content_type="application/json"))
    assert get(pki, fake, prose).ok
    assert get(pki, fake, data).ok


def test_a_challenge_with_an_error_status_is_an_http_error(
    pki: Pki, fake: FakeTime, server: TestServer
) -> None:
    url = server.route("/cf", Reply(status=403, body=b"<title>Just a moment...</title>"))
    assert get(pki, fake, url).outcome == "http_error"


JSON = "application/json; charset=utf-8"


def test_mediawiki_success(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    url = server.route("/api", Reply(body=b'{"parse": {"title": "X"}}', content_type=JSON))
    assert get(pki, fake, url, mediawiki=True).ok


def test_mediawiki_errors_are_api_errors(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    body = b'{"error": {"code": "missingtitle", "info": "The page does not exist."}}'
    result = get(pki, fake, server.route("/api", Reply(body=body, content_type=JSON)), mediawiki=True)
    assert (result.outcome, result.api_code, result.attempts) == ("api_error", "missingtitle", 1)
    assert result.error == "MediaWiki error missingtitle: The page does not exist."


def test_mediawiki_maxlag_is_retried(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    body = b'{"error": {"code": "maxlag", "info": "Waiting for a database server"}}'
    url = server.route("/api", Reply(body=body, content_type=JSON, headers={"Retry-After": "5"}))
    result = get(pki, fake, url, mediawiki=True)
    assert (result.outcome, result.api_code, result.attempts) == ("api_error", "maxlag", 3)
    assert fake.sleeps == [5.0, 5.0]


def test_mediawiki_non_json_is_an_api_error(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    url = server.route("/api", Reply(body=b"<html>maintenance</html>"))
    assert get(pki, fake, url, mediawiki=True).outcome == "api_error"
    assert get(pki, fake, url).ok  # only MediaWiki requests expect JSON


# -- TLS, DNS and exception mapping -------------------------------------------


@pytest.mark.parametrize("cert", ["expired", "wrong_host", "other_ca"])
def test_bad_certificates_are_tls_errors(pki: Pki, fake: FakeTime, cert: str) -> None:
    with serve(getattr(pki, cert)) as bad:
        result = get(pki, fake, bad.route("/page?api_key=s3cret", Reply(body=b"ok")))
    assert (result.outcome, result.stage, result.attempts) == ("tls_error", "tls", 1)
    assert result.error_type == "SSLError"
    assert result.error is not None and "s3cret" not in result.error
    assert "s3cret" not in result.url
    assert fake.sleeps == []


def test_the_explicit_bundle_beats_requests_ca_bundle(
    pki: Pki, fake: FakeTime, server: TestServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(pki.other_bundle))
    assert get(pki, fake, server.route("/page", Reply(body=b"ok"))).ok


def test_verification_cannot_be_switched_off() -> None:
    with pytest.raises(ValueError, match="CA bundle"):
        Fetcher(verify="")


def test_name_resolution_failures_are_dns_errors(
    pki: Pki, fake: FakeTime, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_dns(*args: object, **kwargs: object) -> list[object]:
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", no_dns)
    result = get(pki, fake, "https://elections.example/page")
    assert (result.outcome, result.stage, result.attempts) == ("dns_error", "request", 3)
    assert fake.sleeps == [2.0, 4.0]


def _caused_by(exc: Exception, cause: BaseException) -> Exception:
    exc.__cause__ = cause
    return exc


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (requests.exceptions.SSLError("bad cert"), ("tls_error", False)),
        (urllib3.exceptions.SSLError("bad record mac"), ("tls_error", False)),
        (requests.exceptions.ConnectTimeout("connect"), ("timeout", True)),
        (requests.exceptions.ReadTimeout("read"), ("timeout", True)),
        (urllib3.exceptions.ReadTimeoutError(None, "/", "Read timed out."), ("timeout", True)),  # type: ignore[arg-type]
        (requests.exceptions.ConnectionError("refused"), ("fetch_failed", True)),
        (urllib3.exceptions.ProtocolError("Connection broken"), ("fetch_failed", True)),
        (
            _caused_by(requests.exceptions.ConnectionError("x"), socket.gaierror(-2, "unknown")),
            ("dns_error", True),
        ),
        (requests.exceptions.InvalidURL("bad"), ("fetch_failed", False)),
        (urllib3.exceptions.DecodeError("bad gzip"), ("fetch_failed", False)),
        (ValueError("Invalid IPv6 URL"), ("fetch_failed", False)),
    ],
)
def test_outcome_for(exc: Exception, expected: tuple[str, bool]) -> None:
    assert outcome_for(exc) == expected


# -- redaction ----------------------------------------------------------------


WIKIPEDIA_API = (
    "https://en.wikipedia.org/w/api.php?action=parse&page=2026_national_electoral_calendar"
    "&prop=text|revid&format=json&formatversion=2&maxlag=5"
)
EISA_TABLE = (
    "https://www.eisa.org/wp-admin/admin-ajax.php?action=wp_ajax_ninja_tables_public_action"
    "&table_id=12&target_action=get-all-data"
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # the sources' own parameters are kept
        (WIKIPEDIA_API, WIKIPEDIA_API),
        (EISA_TABLE, EISA_TABLE),
        ("https://www.aweb.org/eng/bbs/B0000007/list.do?menuNo=300052&option=all", "https://www.aweb.org/eng/bbs/B0000007/list.do?menuNo=300052&option=all"),
        ("https://www.ndi.org/elections-calendar?page=2", "https://www.ndi.org/elections-calendar?page=2"),
        # any other parameter is replaced whole; user info and the fragment are dropped
        ("https://user:pw@Example.org:8443/p?q=1&api_key=abc&token=x#frag", "https://example.org:8443/p?REDACTED&REDACTED&REDACTED"),
        ("https://x.org/p?__cf_chl_tk=abc.123-xyz&page=2", "https://x.org/p?REDACTED&page=2"),  # Cloudflare
        ("https://x.org/p?page=1&page=2&sid=a&sid=b", "https://x.org/p?page=1&page=2&REDACTED&REDACTED"),
        ("https://x.org/p?%2561ction=parse&Page=2&%74oken=abc", "https://x.org/p?%2561ction=parse&Page=2&REDACTED"),
        ("https://x.org/p?dG9rZW4=", "https://x.org/p?REDACTED"),  # a token where a key would be
        ("https://x.org/p?next=https://y.org/%3Ftoken%3Dabc", "https://x.org/p?REDACTED"),
        ("https://x.org/p?action%3Dparse%26token%3Dabc", "https://x.org/p?REDACTED"),
        ("https://[::1]:8080/x?Session=1", "https://[::1]:8080/x?REDACTED"),
        ("https://[::1/x", "<unparseable URL>"),
    ],
)
def test_redact_url(url: str, expected: str) -> None:
    assert redact_url(url) == expected


def test_redact_text_handles_full_urls_bare_queries_and_fragments() -> None:
    marker = "s3cr3tMARKER"
    text = (
        "HTTPSConnectionPool(host='x.org', port=443): Max retries exceeded with url: "
        f"/w/api.php?action=parse&token={marker} (Caused by ...) see "
        f"https://u:{marker}@x.org/?sig={marker} and /cb#access_token={marker} and ?{marker}"
    )
    redacted = redact_text(text)
    assert marker not in redacted
    assert "url: /w/api.php?action=parse&REDACTED (Caused by" in redacted
    assert redacted.endswith("see https://x.org/?REDACTED and /cb#REDACTED and ?REDACTED")
    assert len(redact_text("x" * 2000)) == 500


def test_no_query_secret_reaches_the_result(pki: Pki, fake: FakeTime, server: TestServer) -> None:
    marker = "s3cr3tMARKER"
    target = f"/b?__cf_chl_tk={marker}&page=2"
    url = server.route(f"/a?token={marker}", Reply(status=302, headers={"Location": target}))
    server.route(target, Reply(status=403, body=b"denied"))
    result = get(pki, fake, url)
    assert (result.outcome, result.http_status) == ("http_error", 403)
    assert result.final_url == server.url("/b?REDACTED&page=2")
    assert marker not in repr(result) and marker not in repr(result.diagnostics())


def test_no_query_secret_reaches_the_published_diagnostics(
    pki: Pki, fake: FakeTime, server: TestServer
) -> None:
    marker = "s3cr3tMARKER"
    error = {"code": f"bad?token={marker}", "info": f"see ?token={marker}"}
    body = json.dumps({"error": error}).encode()
    result = get(pki, fake, server.route("/api", Reply(body=body, content_type=JSON)), mediawiki=True)
    assert (result.outcome, result.api_code) == ("api_error", INVALID_API_CODE)
    assert marker not in json.dumps(result.diagnostics())
    assert marker.encode() in result.body  # the raw body keeps it: never publish the body


def test_an_api_code_outside_its_grammar_is_not_published(
    pki: Pki, fake: FakeTime, server: TestServer
) -> None:
    marker = "s3cr3tMARKER"
    body = json.dumps({"error": {"code": f"token={marker}", "info": "x"}}).encode()
    result = get(pki, fake, server.route("/api", Reply(body=body, content_type=JSON)), mediawiki=True)
    assert (result.outcome, result.api_code) == ("api_error", INVALID_API_CODE)
    assert marker not in json.dumps(result.diagnostics())


def test_mediawiki_json_nested_too_deep_is_an_api_error(
    pki: Pki, fake: FakeTime, server: TestServer
) -> None:
    body = b"[" * 200_000  # far under MAX_BYTES, but json.loads raises RecursionError
    result = get(pki, fake, server.route("/api", Reply(body=body, content_type=JSON)), mediawiki=True)
    assert (result.outcome, result.stage) == ("api_error", "api")


# -- trust bundle -------------------------------------------------------------


def test_trust_bundle_is_certifi_alone_without_machine_settings(tmp_path: Path) -> None:
    bundle = trust_bundle(tmp_path / "out" / "ca.pem", environ={})
    assert bundle.sources == ("certifi",)
    assert bundle.path.read_bytes() == Path(certifi.where()).read_bytes()


def test_the_first_configured_bundle_is_the_machine_bundle(pki: Pki, tmp_path: Path) -> None:
    environ = {
        "REQUESTS_CA_BUNDLE": "",  # set but empty: not configured
        "SSL_CERT_FILE": str(pki.bundle),
        "CURL_CA_BUNDLE": str(pki.other_bundle),  # ignored: SSL_CERT_FILE comes first
    }
    bundle = trust_bundle(tmp_path / "ca.pem", environ=environ)
    assert bundle.sources == ("certifi", "SSL_CERT_FILE")
    content = bundle.path.read_bytes()
    assert content.startswith(Path(certifi.where()).read_bytes())
    assert content.count(pki.bundle.read_bytes()) == 1
    assert pki.other_bundle.read_bytes() not in content


@pytest.mark.parametrize("problem", ["missing", "directory", "not a certificate"])
def test_a_configured_bundle_that_cannot_be_used_is_an_error(
    pki: Pki, tmp_path: Path, problem: str
) -> None:
    notes = tmp_path / "notes.pem"
    notes.write_text("not a certificate\n", encoding="utf-8")
    configured = {"missing": tmp_path / "missing.pem", "directory": tmp_path}.get(problem, notes)
    environ = {"REQUESTS_CA_BUNDLE": str(configured), "SSL_CERT_FILE": str(pki.bundle)}
    with pytest.raises(TrustBundleError, match="REQUESTS_CA_BUNDLE"):
        trust_bundle(tmp_path / "out" / "ca.pem", environ=environ)
    assert not (tmp_path / "out" / "ca.pem").exists()


def test_trust_bundle_error_names_its_variable(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pem"
    with pytest.raises(TrustBundleError) as caught:
        trust_bundle(tmp_path / "ca.pem", environ={"SSL_CERT_FILE": str(missing)})
    assert caught.value.variable == "SSL_CERT_FILE"
    assert str(caught.value).startswith(f"SSL_CERT_FILE={missing} is not a usable CA bundle: ")


@pytest.mark.parametrize(("configured", "outcome"), [("bundle", "ok"), ("other_bundle", "tls_error")])
def test_a_combined_bundle_trusts_only_what_it_lists(
    pki: Pki, fake: FakeTime, server: TestServer, tmp_path: Path, configured: str, outcome: str
) -> None:
    machine = str(getattr(pki, configured))
    bundle = trust_bundle(tmp_path / "ca.pem", environ={"SSL_CERT_FILE": machine})
    url = server.route("/page", Reply(body=b"ok"))
    with Fetcher(verify=str(bundle.path), clock=fake.clock, sleep=fake.sleep) as f:
        assert f.get(url, deadline=Deadline.after(60, fake.clock)).outcome == outcome
