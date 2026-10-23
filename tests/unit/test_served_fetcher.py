"""The served fetcher is bounded by the time it is given (Plan 5a Task 6; R2-06, R2-07)."""

import time
from pathlib import Path

import pytest

from elections_calendar.ci.publishing import served_fetcher
from elections_calendar.fetch import TrustBundleError
from tests.support.http_server import Reply, TestServer
from tests.unit.conftest import Pki


def test_served_fetcher_is_bounded(tmp_path: Path, pki: Pki, server: TestServer) -> None:
    environ = {"REQUESTS_CA_BUNDLE": str(pki.bundle)}
    feed = server.route("/feed", Reply(body=b"feed"))
    missing = server.url("/missing")
    dripped = server.route("/slow", Reply(body=b"x" * 400, drip=0.1))  # four seconds of body

    assert served_fetcher(environ, workdir=tmp_path, url=feed)(5.0) == b"feed"
    assert (tmp_path / "ca-bundle.pem").is_file()
    assert served_fetcher(environ, workdir=tmp_path, url=missing)(5.0) is None

    started = time.monotonic()
    assert served_fetcher(environ, workdir=tmp_path, url=dripped)(1.0) is None
    assert time.monotonic() - started < 2.0

    broken = {"REQUESTS_CA_BUNDLE": str(tmp_path / "missing.pem")}
    with pytest.raises(TrustBundleError):
        served_fetcher(broken, workdir=tmp_path, url=feed)
