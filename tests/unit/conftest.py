"""Fixtures shared by the fetch and runner tests: a throwaway PKI and a local HTTPS server."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.support.http_server import TestServer, serve
from tests.support.tls import ServerCert, authority, server_cert

PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


@dataclass(frozen=True)
class Pki:
    bundle: Path  # trusts the test CA only
    other_bundle: Path  # trusts an unrelated CA only
    good: ServerCert
    expired: ServerCert
    wrong_host: ServerCert
    other_ca: ServerCert


@pytest.fixture(scope="module")
def pki(tmp_path_factory: pytest.TempPathFactory) -> Pki:
    directory = tmp_path_factory.mktemp("pki")
    ca, other = authority("Test CA"), authority("Other CA")
    return Pki(
        bundle=ca.write(directory / "ca.pem"),
        other_bundle=other.write(directory / "other.pem"),
        good=server_cert(ca, directory, "good"),
        expired=server_cert(ca, directory, "expired", expired=True),
        wrong_host=server_cert(ca, directory, "wrong-host", hosts=("example.org",)),
        other_ca=server_cert(other, directory, "other-ca"),
    )


@pytest.fixture(autouse=True)
def no_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fetcher honours proxy variables, and runner workers inherit os.environ.
    for name in PROXY_VARS:
        monkeypatch.delenv(name, raising=False)
    # A non-empty *_proxy variable makes urllib ignore the Windows registry proxy,
    # and "*" bypasses every host.
    monkeypatch.setenv("NO_PROXY", "*")


@pytest.fixture
def server(pki: Pki) -> Iterator[TestServer]:
    with serve(pki.good) as running:
        yield running


@pytest.fixture
def ca_env(pki: Pki) -> dict[str, str]:
    """The environment a runner test passes: the test CA is the machine bundle."""
    return {"REQUESTS_CA_BUNDLE": str(pki.bundle)}
