from dataclasses import dataclass

from app.core.config import settings

SUPPORTED_BROWSERS = {"chromium", "firefox", "webkit"}
SUPPORTED_WAIT_UNTIL = {"commit", "domcontentloaded", "load", "networkidle"}


@dataclass(frozen=True)
class BrowserConfig:
    browser_name: str
    headless: bool
    navigation_timeout_ms: int
    action_timeout_ms: int
    viewport_width: int
    viewport_height: int
    retries: int
    wait_until: str


def get_browser_config() -> BrowserConfig:
    browser_name = settings.browser_name.lower().strip()
    if browser_name not in SUPPORTED_BROWSERS:
        raise ValueError(f"Unsupported browser '{settings.browser_name}'")

    wait_until = settings.browser_wait_until.lower().strip()
    if wait_until not in SUPPORTED_WAIT_UNTIL:
        raise ValueError(f"Unsupported wait strategy '{settings.browser_wait_until}'")

    return BrowserConfig(
        browser_name=browser_name,
        headless=settings.browser_headless,
        navigation_timeout_ms=settings.browser_navigation_timeout_ms,
        action_timeout_ms=settings.browser_action_timeout_ms,
        viewport_width=settings.browser_viewport_width,
        viewport_height=settings.browser_viewport_height,
        retries=max(settings.browser_retries, 0),
        wait_until=wait_until,
    )
