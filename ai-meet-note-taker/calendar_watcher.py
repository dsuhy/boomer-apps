"""Watch Google Calendar for upcoming meetings and trigger the bot."""

import datetime
import logging
import os
import pickle
import time
from dataclasses import dataclass, field
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# If modifying these scopes, delete token.pickle so re-auth is triggered
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
]

TOKEN_PATH = Path("token.pickle")
CREDENTIALS_PATH = Path("credentials.json")


@dataclass
class MeetingInfo:
    """Parsed details of an upcoming Google Meet event."""

    event_id: str
    title: str
    meet_url: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    organizer_email: str
    attendee_emails: list[str] = field(default_factory=list)

    @property
    def minutes_until_start(self) -> float:
        now = datetime.datetime.now(datetime.timezone.utc)
        return (self.start_time - now).total_seconds() / 60


def get_calendar_credentials() -> Credentials:
    """Load or create OAuth2 credentials for Google Calendar API.

    Requires a credentials.json file downloaded from the Google Cloud Console
    (OAuth 2.0 Client ID, Desktop application type).
    """
    creds = None

    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_PATH}. Download your OAuth2 credentials "
                    "from https://console.cloud.google.com/apis/credentials "
                    "(create an OAuth 2.0 Client ID for 'Desktop app'), "
                    "then save the JSON file as credentials.json in this directory."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return creds


def get_upcoming_meetings(
    minutes_ahead: int = 60,
) -> list[MeetingInfo]:
    """Fetch upcoming calendar events that have a Google Meet link.

    Args:
        minutes_ahead: How far ahead to look for meetings (in minutes).

    Returns:
        List of MeetingInfo for events with Meet links starting within the window.
    """
    creds = get_calendar_credentials()
    service = build("calendar", "v3", credentials=creds)

    now = datetime.datetime.now(datetime.timezone.utc)
    time_max = now + datetime.timedelta(minutes=minutes_ahead)

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    meetings = []
    for event in events_result.get("items", []):
        meet_url = _extract_meet_url(event)
        if not meet_url:
            continue

        start = _parse_event_time(event["start"])
        end = _parse_event_time(event["end"])

        attendee_emails = [
            a["email"]
            for a in event.get("attendees", [])
            if not a.get("self", False)
        ]

        organizer = event.get("organizer", {}).get("email", "")

        meetings.append(
            MeetingInfo(
                event_id=event["id"],
                title=event.get("summary", "Untitled Meeting"),
                meet_url=meet_url,
                start_time=start,
                end_time=end,
                organizer_email=organizer,
                attendee_emails=attendee_emails,
            )
        )

    return meetings


def _extract_meet_url(event: dict) -> str | None:
    """Extract the Google Meet URL from a calendar event."""
    # conferenceData.entryPoints is the most reliable source
    for ep in event.get("conferenceData", {}).get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            uri = ep.get("uri", "")
            if "meet.google.com" in uri:
                return uri

    # Fallback: check hangoutLink field
    hangout = event.get("hangoutLink", "")
    if "meet.google.com" in hangout:
        return hangout

    return None


def _parse_event_time(time_entry: dict) -> datetime.datetime:
    """Parse a Google Calendar event start/end time."""
    if "dateTime" in time_entry:
        return datetime.datetime.fromisoformat(time_entry["dateTime"])
    # All-day events only have a 'date' field — treat as midnight
    return datetime.datetime.fromisoformat(
        time_entry["date"] + "T00:00:00+00:00"
    )


class CalendarScheduler:
    """Polls Google Calendar and yields meetings that are about to start."""

    def __init__(
        self,
        poll_interval: int = 60,
        join_minutes_before: int = 1,
        lookahead_minutes: int = 10,
    ):
        self.poll_interval = poll_interval
        self.join_minutes_before = join_minutes_before
        self.lookahead_minutes = lookahead_minutes
        self._handled_events: set[str] = set()

    def watch(self):
        """Generator that yields MeetingInfo objects when it's time to join.

        Polls the calendar every poll_interval seconds and yields meetings
        that are within join_minutes_before of their start time.
        """
        logger.info(
            "Calendar watcher started (poll every %ds, join %dm before start, "
            "lookahead %dm)",
            self.poll_interval,
            self.join_minutes_before,
            self.lookahead_minutes,
        )

        while True:
            try:
                meetings = get_upcoming_meetings(
                    minutes_ahead=self.lookahead_minutes
                )

                for meeting in meetings:
                    if meeting.event_id in self._handled_events:
                        continue

                    if meeting.minutes_until_start <= self.join_minutes_before:
                        logger.info(
                            "Time to join: '%s' (starts in %.1f min) — %s",
                            meeting.title,
                            meeting.minutes_until_start,
                            meeting.meet_url,
                        )
                        self._handled_events.add(meeting.event_id)
                        yield meeting
                    else:
                        logger.debug(
                            "Upcoming: '%s' in %.1f min",
                            meeting.title,
                            meeting.minutes_until_start,
                        )

            except Exception:
                logger.exception("Error polling calendar")

            time.sleep(self.poll_interval)
