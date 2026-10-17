"""How Instagram receives a video: a hosted ``video_url`` or a resumable upload.

With ``video_url`` Meta downloads the file from us, which needs a public URL.
A Studio running on localhost has none, so there the bytes are pushed to Meta's
resumable upload host instead (container created with ``upload_type=resumable``,
then ``POST rupload.facebook.com/ig-api-upload/<version>/<container-id>``).
Meta's resumable upload takes video only; images always go out as ``image_url``.

``settings.INSTAGRAM_VIDEO_UPLOAD`` picks the mode:

- ``"url"`` — always ``video_url`` (upstream behaviour).
- ``"resumable"`` — always upload the bytes.
- ``"auto"`` (default) — upload when the media URL points at a host Meta cannot
  reach (localhost, 127.0.0.1, a private IP, a dotless name), else ``video_url``.
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

from .exceptions import PublishError

RUPLOAD_HOST = "rupload.facebook.com"
RUPLOAD_URL = "https://rupload.facebook.com/ig-api-upload/{version}/{container_id}"
UPLOAD_TIMEOUT = 300.0
MODES = ("auto", "url", "resumable")


def video_upload_mode() -> str:
    from django.conf import settings

    mode = str(getattr(settings, "INSTAGRAM_VIDEO_UPLOAD", "auto") or "auto").strip().lower()
    return mode if mode in MODES else "auto"


def is_private_url(url: str) -> bool:
    """True when Meta's servers could not fetch ``url`` from the internet."""
    host = (urlparse(url).hostname or "").lower()
    if not host or host == "localhost" or "." not in host:
        return True
    if host.endswith((".localhost", ".local", ".internal")):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified


def wants_local_media() -> bool:
    """Whether the engine must download media to disk before publishing."""
    from django.conf import settings

    mode = video_upload_mode()
    if mode == "auto":
        return is_private_url(getattr(settings, "APP_URL", ""))
    return mode == "resumable"


def apply_video_source(payload: dict, content, index: int, *, resumable: bool = True) -> str | None:
    """Point a video container at its bytes; return the local file to upload, if any.

    Sets ``video_url`` (URL mode) or ``upload_type=resumable`` on ``payload``.
    Falls back to ``video_url`` when no local file was handed over.
    ``resumable=False`` is for hosts without resumable upload (graph.instagram.com
    answers "The parameter video_url is required"): a URL Meta can't reach then
    fails here with a clear message instead of at Meta.
    """
    url = content.media_urls[index]
    if not resumable:
        if is_private_url(url):
            raise PublishError(
                "Instagram (Direct) accepts video only by a public URL, and this Studio's media URL "
                f"({urlparse(url).hostname}) is not reachable from the internet. Set a public APP_URL "
                "(server or tunnel) or connect the account via Instagram (Facebook Login), which "
                "supports direct upload."
            )
        payload["video_url"] = url
        return None
    mode = video_upload_mode()
    use_resumable = mode == "resumable" or (mode == "auto" and is_private_url(url))
    files = content.media_files or []
    if use_resumable and index < len(files) and files[index]:
        payload["upload_type"] = "resumable"
        return files[index]
    payload["video_url"] = url
    return None


def upload_video(provider, access_token: str, container_id: str, uri: str | None, path: str, version: str) -> None:
    """POST the file's bytes to the container's resumable upload URL."""
    # Use Meta's returned ``uri`` only on Meta's upload host: the token travels
    # in the header, so it must not follow an unexpected URL.
    upload_url = uri if uri and urlparse(uri).hostname == RUPLOAD_HOST else None
    upload_url = upload_url or RUPLOAD_URL.format(version=version, container_id=container_id)
    with open(path, "rb") as fh:
        resp = provider._request(
            "POST",
            upload_url,
            headers={
                "Authorization": f"OAuth {access_token}",
                "offset": "0",
                "file_size": str(os.path.getsize(path)),
            },
            data=fh,
            timeout=UPLOAD_TIMEOUT,
        )
    data = provider._safe_json(resp)
    if data.get("success") is False or "error" in data:
        raise PublishError(
            "Instagram failed to upload the video",
            platform=provider.platform_name,
            raw_response=data,
        )
