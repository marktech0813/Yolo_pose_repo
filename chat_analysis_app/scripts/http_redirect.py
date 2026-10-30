#!/usr/bin/env python3
"""Redirect HTTP :8000 → HTTPS :8443 so old http:// bookmarks keep working."""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HTTPS_PORT = 8443
LISTEN_PORT = 8000


class RedirectHandler(BaseHTTPRequestHandler):
    def _redirect(self) -> None:
        host = (self.headers.get("Host") or "127.0.0.1").split(":")[0]
        location = f"https://{host}:{HTTPS_PORT}{self.path}"
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        body = f"Redirecting to {location}\n".encode()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._redirect()

    def do_HEAD(self) -> None:  # noqa: N802
        self._redirect()

    def do_POST(self) -> None:  # noqa: N802
        self._redirect()

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), RedirectHandler)
    print(f"HTTP redirect listening on 0.0.0.0:{LISTEN_PORT} → https://*:{HTTPS_PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
