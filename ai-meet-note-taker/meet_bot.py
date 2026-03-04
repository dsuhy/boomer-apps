"""Google Meet bot that joins meetings via Selenium browser automation."""

import time
import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class MeetBot:
    """Joins a Google Meet call using browser automation and captures audio."""

    def __init__(self, meeting_url: str, display_name: str = "AI Note Taker"):
        self.meeting_url = meeting_url
        self.display_name = display_name
        self.driver = None

    def _create_driver(self) -> webdriver.Chrome:
        """Create a headless Chrome driver configured for Meet."""
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")

        # Auto-allow microphone/camera permissions (we'll mute them)
        opts.add_argument("--use-fake-ui-for-media-stream")
        opts.add_argument("--use-fake-device-for-media-stream")

        # Enable audio capture from the browser tab
        opts.add_argument("--autoplay-policy=no-user-gesture-required")
        opts.add_argument("--enable-audio-output")

        # Route browser audio to a virtual sink for capture
        opts.add_argument(
            "--alsa-output-device=pulse"
        )

        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=opts)

    def join(self) -> None:
        """Navigate to the Meet URL and join the call."""
        logger.info("Launching browser and navigating to %s", self.meeting_url)
        self.driver = self._create_driver()
        self.driver.get(self.meeting_url)

        # Wait for the page to load
        time.sleep(5)

        # Try to dismiss any "sign in" or "use without account" prompts
        self._dismiss_sign_in_prompt()

        # Set display name if the field is available (guest join)
        self._set_display_name()

        # Turn off microphone and camera before joining
        self._mute_mic_and_camera()

        # Click the "Join now" / "Ask to join" button
        self._click_join_button()

        logger.info("Successfully requested to join the meeting")

    def _dismiss_sign_in_prompt(self) -> None:
        """Try to click 'Continue without signing in' if prompted."""
        try:
            # Google Meet sometimes shows a sign-in interstitial
            continue_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//*[contains(text(), 'Continue without')]")
                )
            )
            continue_btn.click()
            time.sleep(2)
        except Exception:
            logger.debug("No sign-in prompt found, continuing")

    def _set_display_name(self) -> None:
        """Enter a display name in the guest name field."""
        try:
            name_input = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[aria-label='Your name']")
                )
            )
            name_input.clear()
            name_input.send_keys(self.display_name)
            logger.info("Set display name to '%s'", self.display_name)
        except Exception:
            logger.debug("No name input found (may already be signed in)")

    def _mute_mic_and_camera(self) -> None:
        """Toggle off microphone and camera if they're on."""
        # Mic toggle
        try:
            mic_btn = self.driver.find_element(
                By.CSS_SELECTOR,
                "[data-is-muted='false'][aria-label*='microphone'],"
                "[aria-label*='Turn off microphone']",
            )
            mic_btn.click()
            logger.info("Muted microphone")
        except Exception:
            logger.debug("Microphone already muted or button not found")

        # Camera toggle
        try:
            cam_btn = self.driver.find_element(
                By.CSS_SELECTOR,
                "[data-is-muted='false'][aria-label*='camera'],"
                "[aria-label*='Turn off camera']",
            )
            cam_btn.click()
            logger.info("Turned off camera")
        except Exception:
            logger.debug("Camera already off or button not found")

    def _click_join_button(self) -> None:
        """Click 'Join now' or 'Ask to join'."""
        join_selectors = [
            "//*[contains(text(), 'Join now')]",
            "//*[contains(text(), 'Ask to join')]",
            "//button[contains(@data-idom-class, 'join')]",
            "//span[contains(text(), 'Join')]/ancestor::button",
        ]

        for xpath in join_selectors:
            try:
                btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                btn.click()
                logger.info("Clicked join button: %s", xpath)
                return
            except Exception:
                continue

        logger.warning("Could not find a join button — you may need to join manually")

    def is_in_meeting(self) -> bool:
        """Check whether we're currently in the meeting."""
        if not self.driver:
            return False
        try:
            # If the "Leave call" button exists, we're in the meeting
            self.driver.find_element(
                By.CSS_SELECTOR,
                "[aria-label='Leave call'],"
                "[aria-label='Leave meeting']",
            )
            return True
        except Exception:
            return False

    def wait_for_admission(self, timeout: int = 300) -> bool:
        """Wait until the host admits us into the meeting."""
        logger.info("Waiting up to %ds for host to admit us...", timeout)
        start = time.time()
        while time.time() - start < timeout:
            if self.is_in_meeting():
                logger.info("Admitted to meeting!")
                return True
            time.sleep(3)
        logger.warning("Timed out waiting for admission")
        return False

    def leave(self) -> None:
        """Leave the meeting and close the browser."""
        if self.driver:
            try:
                leave_btn = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "[aria-label='Leave call'],"
                    "[aria-label='Leave meeting']",
                )
                leave_btn.click()
                time.sleep(1)
            except Exception:
                pass
            self.driver.quit()
            self.driver = None
            logger.info("Left the meeting")
