"""HTTP_TRANSPORT=curl: provider calls go through the curl binary."""

import os
from pathlib import Path

import httpx

from providers import curl_transport
from providers.curl_transport import CurlTransport, provider_transport


def _fake_curl(monkeypatch, status_line="HTTP/1.1 200 OK", body=b'{"ok": true}'):
    seen = {}

    def run(args, capture_output):
        seen["args"] = args
        seen["headers"] = Path(args[args.index("-H") + 1][1:]).read_text(encoding="utf-8")
        if "--data-binary" in args:
            seen["body"] = Path(args[args.index("--data-binary") + 1][1:]).read_bytes()
        with open(args[args.index("-D") + 1], "wb") as f:
            f.write(
                b"HTTP/1.1 200 Connection established\r\n\r\n"
                + status_line.encode()
                + b"\r\nContent-Type: application/json\r\n\r\n"
            )
        with open(args[args.index("-o") + 1], "wb") as f:
            f.write(body)
        return type("P", (), {"returncode": 0, "stderr": b""})()

    monkeypatch.setattr(curl_transport.subprocess, "run", run)
    return seen


def test_post_sends_headers_and_body_through_files(monkeypatch):
    seen = _fake_curl(monkeypatch)
    with httpx.Client(transport=CurlTransport(curl="curl")) as c:
        r = c.post("https://graph.instagram.com/me", json={"a": 1}, headers={"Authorization": "Bearer tok"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert "authorization: Bearer tok" in seen["headers"].lower().replace("bearer", "Bearer")
    assert "tok" not in " ".join(seen["args"])  # token never on the command line
    assert seen["body"] in (b'{"a":1}', b'{"a": 1}')


def test_status_comes_from_last_header_block(monkeypatch):
    _fake_curl(monkeypatch, status_line="HTTP/1.1 400 Bad Request", body=b"{}")
    with httpx.Client(transport=CurlTransport(curl="curl")) as c:
        assert c.get("https://graph.instagram.com/me").status_code == 400


def test_curl_failure_is_connect_error(monkeypatch):
    monkeypatch.setattr(
        curl_transport.subprocess, "run", lambda *a, **k: type("P", (), {"returncode": 35, "stderr": b"ssl"})()
    )
    with httpx.Client(transport=CurlTransport(curl="curl")) as c:
        try:
            c.get("https://graph.instagram.com/me")
        except httpx.ConnectError as e:
            assert "ssl" in str(e)
        else:
            raise AssertionError("expected ConnectError")


def test_setting_selects_transport(settings):
    settings.HTTP_TRANSPORT = "httpx"
    assert provider_transport() is None
    settings.HTTP_TRANSPORT = "curl"
    assert isinstance(provider_transport(), CurlTransport)


def test_temp_files_are_removed(monkeypatch):
    seen = _fake_curl(monkeypatch)
    with httpx.Client(transport=CurlTransport(curl="curl")) as c:
        c.get("https://graph.instagram.com/me")
    assert not os.path.exists(seen["args"][seen["args"].index("-D") + 1])
