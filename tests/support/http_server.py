"""A local HTTPS server with scripted replies, for fetch tests.

Each path has a list of replies served in order; the last one repeats.
Unknown paths get 404. Every request is logged with its headers.
"""

import ssl
import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socket import socket
from typing import Any

from tests.support.tls import ServerCert


@dataclass(frozen=True)
class Reply:
    status: int = 200
    body: bytes = b""
    content_type: str = "text/html; charset=utf-8"
    headers: Mapping[str, str] = field(default_factory=dict)
    delay: float = 0.0  # seconds before the status line
    drip: float = 0.0  # seconds between 10-byte pieces of the body


@dataclass(frozen=True)
class Request:
    path: str
    headers: Mapping[str, str]


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, context: ssl.SSLContext) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.context = context
        self.replies: dict[str, list[Reply]] = {}
        self.requests: list[Request] = []
        self._lock = threading.Lock()

    def get_request(self) -> tuple[socket, Any]:
        sock, address = super().get_request()
        # The handshake runs in the handler thread, so a client that rejects
        # the certificate never blocks the accept loop.
        tls = self.context.wrap_socket(sock, server_side=True, do_handshake_on_connect=False)
        return tls, address

    def handle_error(self, request: Any, client_address: Any) -> None:
        pass  # failed handshakes and dropped clients are what the tests provoke

    def next_reply(self, path: str) -> Reply:
        with self._lock:
            queue = self.replies.get(path)
            if not queue:
                return Reply(status=404, body=b"not found")
            return queue.pop(0) if len(queue) > 1 else queue[0]


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: _Server

    def setup(self) -> None:
        self.request.do_handshake()
        super().setup()

    def do_GET(self) -> None:
        self.server.requests.append(Request(self.path, dict(self.headers.items())))
        reply = self.server.next_reply(self.path)
        time.sleep(reply.delay)
        try:
            self.send_response(reply.status)
            self.send_header("Content-Type", reply.content_type)
            self.send_header("Content-Length", str(len(reply.body)))
            for name, value in reply.headers.items():
                self.send_header(name, value)
            self.end_headers()
            if not reply.drip:
                self.wfile.write(reply.body)
                return
            for start in range(0, len(reply.body), 10):
                self.wfile.write(reply.body[start : start + 10])
                self.wfile.flush()
                time.sleep(reply.drip)
        except OSError:
            self.close_connection = True  # the client gave up, as the test intended

    def log_message(self, format: str, *args: Any) -> None:
        pass


class TestServer:
    __test__ = False  # not a pytest test class

    def __init__(self, server: _Server) -> None:
        self._server = server

    @property
    def requests(self) -> list[Request]:
        return self._server.requests

    def url(self, path: str) -> str:
        return f"https://127.0.0.1:{self._server.server_address[1]}{path}"

    def route(self, path: str, *replies: Reply) -> str:
        """Script the replies for ``path``; returns its URL."""
        self._server.replies[path] = list(replies)
        return self.url(path)


@contextmanager
def serve(cert: ServerCert) -> Iterator[TestServer]:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert.chain, cert.key)
    server = _Server(context)
    thread = threading.Thread(target=server.serve_forever, args=(0.02,), daemon=True)
    thread.start()
    try:
        yield TestServer(server)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
