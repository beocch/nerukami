"""Instagram trial reels: shown to non-followers first (Meta ``trial_params``)."""

TRIAL_STRATEGIES = ("MANUAL", "SS_PERFORMANCE")
INSTAGRAM_PLATFORMS = ("instagram", "instagram_login")
TRIAL_DESCRIPTION = (
    "Instagram only: publish the Reel as a trial reel (shown to non-followers first). "
    "MANUAL = stays a trial until graduated in the Instagram app; "
    "SS_PERFORMANCE = Instagram graduates it to followers if it performs well."
)


def trial_extra(trial: str | None, social_account) -> dict:
    """``platform_extra`` for a trial request; raises ValueError when it can't apply."""
    if not trial:
        return {}
    if trial not in TRIAL_STRATEGIES:
        raise ValueError(f"instagram_trial must be one of {list(TRIAL_STRATEGIES)}")
    if social_account.platform not in INSTAGRAM_PLATFORMS:
        raise ValueError("instagram_trial applies to Instagram accounts only")
    return {"trial_graduation": trial}
