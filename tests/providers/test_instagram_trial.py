"""Trial reels: ``trial_graduation`` in platform_extra reaches Meta as ``trial_params``."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apps.composer.trial import trial_extra
from providers.instagram import InstagramProvider
from providers.instagram_login import InstagramLoginProvider
from providers.types import PostType, PublishContent


def _container_payload(provider, content):
    provider._create_container = MagicMock(return_value="c1")
    provider._wait_for_container = MagicMock()
    provider._publish_container = MagicMock(return_value=SimpleNamespace(platform_post_id="m1"))
    provider.publish_post("tok", content)
    return provider._create_container.call_args.args[-1]


def _reel(extra):
    return PublishContent(
        text="hi", media_urls=["https://x/v.mp4"], media_types=["video"], post_type=PostType.REEL, extra=extra
    )


@pytest.mark.parametrize("strategy", ["MANUAL", "SS_PERFORMANCE"])
def test_instagram_login_reel_carries_trial_params(strategy):
    payload = _container_payload(InstagramLoginProvider(), _reel({"trial_graduation": strategy}))
    assert payload["media_type"] == "REELS"
    assert payload["trial_params"] == {"graduation_strategy": strategy}


def test_instagram_login_reel_without_trial_has_no_trial_params():
    payload = _container_payload(InstagramLoginProvider(), _reel({}))
    assert "trial_params" not in payload


def test_facebook_login_instagram_reel_carries_trial_params():
    provider = InstagramProvider()
    content = _reel({"trial_graduation": "MANUAL", "ig_user_id": "1784"})
    provider._create_container = MagicMock(return_value="c1")
    provider._wait_for_container = MagicMock()
    provider._publish_container = MagicMock(return_value=SimpleNamespace(platform_post_id="m1"))
    provider.publish_post("tok", content)
    payload = provider._create_container.call_args.args[-1]
    assert payload["trial_params"] == {"graduation_strategy": "MANUAL"}


def test_trial_extra_validates_strategy_and_platform():
    ig = SimpleNamespace(platform="instagram_login")
    assert trial_extra(None, ig) == {}
    assert trial_extra("MANUAL", ig) == {"trial_graduation": "MANUAL"}
    with pytest.raises(ValueError):
        trial_extra("SOMETIMES", ig)
    with pytest.raises(ValueError):
        trial_extra("MANUAL", SimpleNamespace(platform="tiktok"))
