"""Instagram video delivery: resumable upload (localhost Studio) vs hosted video_url."""

from unittest.mock import MagicMock

import pytest

from providers.exceptions import PublishError
from providers.instagram import InstagramProvider
from providers.instagram_login import InstagramLoginProvider
from providers.types import PostType, PublishContent

LOCAL_URL = "http://localhost:8000/media/org/v.mp4"
PUBLIC_URL = "https://cdn.example.com/media/v.mp4"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload/v25.0/c1"


def _resp(data):
    resp = MagicMock()
    resp.json.return_value = data
    return resp


def _publish(provider, content, create=None, upload=None):
    """Run publish_post against a scripted Graph API; return the _request mock."""
    responses = {
        "create": create or {"id": "c1", "uri": RUPLOAD},
        "upload": upload or {"success": True, "message": "Upload successful."},
    }

    def fake_request(method, url, **kwargs):
        if url.endswith("/media"):
            return _resp(responses["create"])
        if "rupload" in url or url.startswith("https://evil"):
            return _resp(responses["upload"])
        if url.endswith("/media_publish"):
            return _resp({"id": "m1"})
        return _resp({"status_code": "FINISHED"})  # container status poll

    provider._request = MagicMock(side_effect=fake_request)
    provider.publish_post("tok", content)
    return provider._request


def _calls(request_mock, predicate):
    return [c for c in request_mock.call_args_list if predicate(c.args[1])]


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "v.mp4"
    path.write_bytes(b"\x00" * 1234)
    return str(path)


def _reel(video_path, url=LOCAL_URL, extra=None):
    return PublishContent(
        text="hi",
        media_urls=[url],
        media_types=["video"],
        media_files=[video_path],
        post_type=PostType.REEL,
        extra={"ig_user_id": "1784", **(extra or {})},
    )


@pytest.mark.parametrize(
    ("provider_cls", "create_url"),
    [
        (InstagramProvider, "https://graph.facebook.com/v25.0/1784/media"),
    ],
)
def test_resumable_reel_uploads_bytes_and_keeps_trial_params(settings, video, provider_cls, create_url):
    settings.INSTAGRAM_VIDEO_UPLOAD = "resumable"
    req = _publish(provider_cls(), _reel(video, extra={"trial_graduation": "MANUAL"}))

    create = _calls(req, lambda url: url.endswith("/media"))
    assert [c.args[1] for c in create] == [create_url]
    payload = create[0].kwargs["json"]
    assert payload["media_type"] == "REELS"
    assert payload["upload_type"] == "resumable"
    assert "video_url" not in payload
    assert payload["trial_params"] == {"graduation_strategy": "MANUAL"}

    (upload,) = _calls(req, lambda url: "rupload" in url)
    assert upload.args == ("POST", RUPLOAD)
    assert upload.kwargs["headers"] == {"Authorization": "OAuth tok", "offset": "0", "file_size": "1234"}
    assert upload.kwargs["data"].name == video
    assert "access_token" not in upload.kwargs  # no Bearer header next to OAuth


def test_upload_url_falls_back_when_meta_returns_no_uri(settings, video):
    settings.INSTAGRAM_VIDEO_UPLOAD = "resumable"
    req = _publish(InstagramProvider(), _reel(video), create={"id": "c1"})
    assert _calls(req, lambda url: "rupload" in url)[0].args[1] == RUPLOAD


def test_upload_ignores_a_uri_off_metas_upload_host(settings, video):
    settings.INSTAGRAM_VIDEO_UPLOAD = "resumable"
    req = _publish(InstagramProvider(), _reel(video), create={"id": "c1", "uri": "https://evil.example/x"})
    assert not _calls(req, lambda url: url.startswith("https://evil"))
    assert _calls(req, lambda url: "rupload" in url)[0].args[1] == RUPLOAD


def test_failed_upload_raises(settings, video):
    settings.INSTAGRAM_VIDEO_UPLOAD = "resumable"
    with pytest.raises(PublishError):
        _publish(InstagramProvider(), _reel(video), upload={"success": False, "debug_info": {}})


def test_auto_mode_uploads_local_media_and_links_public_media(settings, video):
    settings.INSTAGRAM_VIDEO_UPLOAD = "auto"
    req = _publish(InstagramProvider(), _reel(video, url=LOCAL_URL))
    assert _calls(req, lambda url: url.endswith("/media"))[0].kwargs["json"]["upload_type"] == "resumable"

    req = _publish(InstagramProvider(), _reel(video, url=PUBLIC_URL, extra={"trial_graduation": "MANUAL"}))
    payload = _calls(req, lambda url: url.endswith("/media"))[0].kwargs["json"]
    assert payload["video_url"] == PUBLIC_URL
    assert "upload_type" not in payload
    assert payload["trial_params"] == {"graduation_strategy": "MANUAL"}
    assert not _calls(req, lambda url: "rupload" in url)


def test_url_mode_always_sends_video_url(settings, video):
    settings.INSTAGRAM_VIDEO_UPLOAD = "url"
    req = _publish(InstagramProvider(), _reel(video, url=LOCAL_URL))
    assert _calls(req, lambda url: url.endswith("/media"))[0].kwargs["json"]["video_url"] == LOCAL_URL
    assert not _calls(req, lambda url: "rupload" in url)


def test_resumable_without_local_file_falls_back_to_video_url(settings):
    settings.INSTAGRAM_VIDEO_UPLOAD = "resumable"
    content = _reel(None)
    content.media_files = []
    req = _publish(InstagramProvider(), content)
    assert _calls(req, lambda url: url.endswith("/media"))[0].kwargs["json"]["video_url"] == LOCAL_URL


def test_carousel_uploads_video_children_and_links_images(settings, video):
    settings.INSTAGRAM_VIDEO_UPLOAD = "auto"
    content = PublishContent(
        text="hi",
        media_urls=["http://127.0.0.1:8000/media/a.jpg", LOCAL_URL],
        media_types=["image", "video"],
        media_files=["unused.jpg", video],
        post_type=PostType.CAROUSEL,
        extra={"ig_user_id": "1784"},
    )
    req = _publish(InstagramProvider(), content)
    image_child, video_child, carousel = (c.kwargs["json"] for c in _calls(req, lambda url: url.endswith("/media")))
    assert image_child == {"is_carousel_item": True, "image_url": "http://127.0.0.1:8000/media/a.jpg"}
    assert video_child == {"is_carousel_item": True, "media_type": "VIDEO", "upload_type": "resumable"}
    assert carousel["media_type"] == "CAROUSEL"
    assert len(_calls(req, lambda url: "rupload" in url)) == 1


@pytest.mark.parametrize(
    ("mode", "app_url", "expected"),
    [
        ("auto", "http://localhost:8000", True),
        ("auto", "http://127.0.0.1:8000", True),
        ("auto", "http://192.168.1.5:8000", True),
        ("auto", "https://studio.example.com", False),
        ("url", "http://localhost:8000", False),
        ("resumable", "https://studio.example.com", True),
    ],
)
def test_engine_downloads_media_only_when_uploading(settings, mode, app_url, expected):
    settings.INSTAGRAM_VIDEO_UPLOAD = mode
    settings.APP_URL = app_url
    assert InstagramProvider().needs_local_media is expected
    assert InstagramLoginProvider().needs_local_media is False


# graph.instagram.com has no resumable upload: Meta answers "The parameter
# video_url is required" to upload_type=resumable (checked live 2026-10-17).
@pytest.mark.parametrize("mode", ["auto", "resumable", "url"])
def test_instagram_login_always_sends_video_url(settings, video, mode):
    settings.INSTAGRAM_VIDEO_UPLOAD = mode
    req = _publish(InstagramLoginProvider(), _reel(video, url=PUBLIC_URL, extra={"trial_graduation": "MANUAL"}))
    payload = _calls(req, lambda url: url.endswith("/media"))[0].kwargs["json"]
    assert payload["video_url"] == PUBLIC_URL
    assert "upload_type" not in payload
    assert payload["trial_params"] == {"graduation_strategy": "MANUAL"}
    assert not _calls(req, lambda url: "rupload" in url)


def test_instagram_login_private_video_url_fails_with_clear_error(settings, video):
    settings.INSTAGRAM_VIDEO_UPLOAD = "auto"
    with pytest.raises(PublishError, match="public URL"):
        _publish(InstagramLoginProvider(), _reel(video, url=LOCAL_URL))
