"""Composer "Trial reel" control → platform_extra["trial_graduation"] → Meta trial_params."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.urls import reverse

from apps.composer.models import PlatformPost
from apps.media_library.models import MediaAsset
from apps.publisher.engine import PublishEngine
from apps.social_accounts.models import SocialAccount
from providers.instagram_login import InstagramLoginProvider
from providers.types import AuthType, PostType, PublishResult

from .test_account_scope import AccountScopeTestsBase


class InstagramTrialComposerTests(AccountScopeTestsBase):
    def setUp(self):
        super().setUp()
        self.instagram = SocialAccount.objects.create(
            workspace=self.workspace,
            platform="instagram_login",
            account_platform_id="ig-1",
            account_name="IG Account",
            connection_status=SocialAccount.ConnectionStatus.CONNECTED,
        )
        self.ig_pp = PlatformPost.objects.create(
            post=self.post,
            social_account=self.instagram,
            status=PlatformPost.Status.DRAFT,
        )
        self._attach(MediaAsset.MediaType.VIDEO, "reel.mp4", post=self.post)

    def _instagram_payload(self, trial=None, panel=True):
        acc = str(self.instagram.id)
        fields = {}
        if panel:
            fields[f"instagram_panel_{acc}"] = "1"
        if trial is not None:
            fields[f"instagram_trial_{acc}"] = trial
        return self._payload(selected_accounts=acc, account_scope=acc, **fields)

    def _save(self, **kwargs):
        response = self.client.post(self.save_url, data=self._instagram_payload(**kwargs))
        self.assertIn(response.status_code, (200, 204, 302))
        self.ig_pp.refresh_from_db()
        return self.ig_pp.platform_extra

    def test_trial_choice_saved_into_platform_extra(self):
        self.assertEqual(self._save(trial="SS_PERFORMANCE")["trial_graduation"], "SS_PERFORMANCE")
        self.assertEqual(self._save(trial="MANUAL")["trial_graduation"], "MANUAL")

    def test_off_clears_choice_and_keeps_other_extras(self):
        self.ig_pp.platform_extra = {"trial_graduation": "MANUAL", "other": 1}
        self.ig_pp.save(update_fields=["platform_extra"])
        self.assertEqual(self._save(trial=""), {"other": 1})

    def test_invalid_strategy_is_not_stored(self):
        self.assertNotIn("trial_graduation", self._save(trial="SOMETIMES"))

    def test_save_without_panel_leaves_choice_untouched(self):
        self.ig_pp.platform_extra = {"trial_graduation": "MANUAL"}
        self.ig_pp.save(update_fields=["platform_extra"])
        self.assertEqual(self._save(panel=False), {"trial_graduation": "MANUAL"})

    def test_facebook_login_instagram_account_is_supported(self):
        self.instagram.platform = "instagram"
        self.instagram.save(update_fields=["platform"])
        self.assertEqual(self._save(trial="MANUAL")["trial_graduation"], "MANUAL")

    def test_edit_page_renders_control_and_saved_value(self):
        self.ig_pp.platform_extra = {"trial_graduation": "SS_PERFORMANCE"}
        self.ig_pp.save(update_fields=["platform_extra"])
        edit_url = reverse(
            "composer:compose_edit",
            kwargs={"workspace_id": self.workspace.id, "post_id": self.post.id},
        )
        response = self.client.get(edit_url)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("'instagram_trial_' + accId", body)
        self.assertIn("Reels only; shown to non-followers first", body)
        # platformExtras is fed from this JSON blob; the select reads it to preselect.
        self.assertIn('"trial_graduation": "SS_PERFORMANCE"', body)

    @patch("apps.publisher.engine.download_to_path")
    @patch("apps.publisher.engine.get_provider")
    @patch("apps.publisher.engine._resolve_publish_credentials", return_value={})
    def test_saved_choice_reaches_meta_payload(self, _creds, get_provider, _download):
        self._save(trial="MANUAL")

        provider = MagicMock()
        provider.auth_type = AuthType.OAUTH2
        provider.supported_post_types = [PostType.REEL, PostType.VIDEO, PostType.IMAGE]
        provider.needs_local_media = False
        provider.publish_is_async = False
        provider.publish_post.return_value = PublishResult(platform_post_id="p1", url=None, extra={})
        get_provider.return_value = provider
        self.instagram.oauth_access_token = "tok"
        self.instagram.save()

        pp = PlatformPost.objects.select_related("social_account", "post").get(id=self.ig_pp.id)
        PublishEngine()._dispatch_to_provider(pp)
        _token, content = provider.publish_post.call_args.args
        self.assertEqual(content.extra["trial_graduation"], "MANUAL")

        real = InstagramLoginProvider()
        real._create_container = MagicMock(return_value="c1")
        real._wait_for_container = MagicMock()
        real._publish_container = MagicMock(return_value=SimpleNamespace(platform_post_id="m1"))
        real.publish_post("tok", content)
        payload = real._create_container.call_args.args[-1]
        self.assertEqual(payload["media_type"], "REELS")
        self.assertEqual(payload["trial_params"], {"graduation_strategy": "MANUAL"})
