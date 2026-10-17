"""httpx transport that sends requests through the ``curl`` binary.

Some networks (e.g. DPI filters in Russia) stall the TLS handshake Python's
OpenSSL makes to Meta's hosts while the OS TLS stack curl uses on Windows
(Schannel) gets through. ``HTTP_TRANSPORT=curl`` routes provider calls through
curl instead. Headers and bodies go through temp files, never the command
line, so tokens don't show up in the process list.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx
from django.conf import settings


def provider_transport() -> httpx.BaseTransport | None:
    """The transport ``BaseProvider._request`` should use (None = httpx default)."""
    if getattr(settings, "HTTP_TRANSPORT", "httpx") == "curl":
        return CurlTransport()
    return None


class CurlTransport(httpx.BaseTransport):
    def __init__(self, curl: str | None = None):
        self.curl = curl or shutil.which("curl") or "curl"

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        timeout = request.extensions.get("timeout", {}).get("read") or 60
        with tempfile.TemporaryDirectory() as tmp:
            hdr_in, hdr_out, body_in, body_out = (os.path.join(tmp, n) for n in ("hi", "ho", "bi", "bo"))
            with open(hdr_in, "w", encoding="utf-8") as f:
                for name, value in request.headers.items():
                    # curl handles the transfer itself; a forwarded encoding header
                    # would hand httpx a body it then tries to decode twice.
                    if name.lower() not in ("accept-encoding", "content-length", "transfer-encoding", "host"):
                        f.write(f"{name}: {value}\n")
            args = [
                self.curl,
                "-sS",
                "-X",
                request.method,
                str(request.url),
                "-H",
                f"@{hdr_in}",
                "-D",
                hdr_out,
                "-o",
                body_out,
                "--max-time",
                str(int(timeout) + 30),
                "--http1.1",
            ]
            with open(body_in, "wb") as f:
                for chunk in request.stream:
                    f.write(chunk)
            if os.path.getsize(body_in) or request.method in ("POST", "PUT", "PATCH"):
                args += ["--data-binary", f"@{body_in}"]
            proc = subprocess.run(args, capture_output=True)
            if proc.returncode != 0:
                raise httpx.ConnectError(proc.stderr.decode(errors="replace").strip() or "curl failed", request=request)
            with open(hdr_out, "rb") as f:
                # Last header block wins: proxies and 100-continue add earlier ones.
                block = f.read().decode("latin-1").strip().split("\r\n\r\n")[-1].split("\r\n")
            content = Path(body_out).read_bytes() if os.path.exists(body_out) else b""
        status = int(block[0].split()[1])
        headers = [tuple(h.split(":", 1)) for h in block[1:] if ":" in h]
        headers = [
            (k.strip(), v.strip())
            for k, v in headers
            if k.strip().lower() not in ("content-encoding", "transfer-encoding")
        ]
        return httpx.Response(status, headers=headers, content=content, request=request)
