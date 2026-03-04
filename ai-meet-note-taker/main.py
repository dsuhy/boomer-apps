#!/usr/bin/env python3
"""AI Meeting Note Taker — joins Google Meet calls, transcribes audio,
and generates structured notes using Grok (xAI).

Modes:
  1. Manual:  python main.py <meet-url>
  2. Watch:   python main.py --watch   (polls Google Calendar, auto-joins)
  3. Offline: python main.py --from-transcript <file> <meet-url>
"""

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from audio_capture import AudioTranscriber, MicrophoneTranscriber
from meet_bot import MeetBot
from note_taker import GrokNoteTaker

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-powered Google Meet note taker using Grok",
    )
    parser.add_argument(
        "meeting_url",
        nargs="?",
        default=None,
        help="Google Meet URL to join (e.g. https://meet.google.com/abc-defg-hij)",
    )
    parser.add_argument(
        "--name",
        default="AI Note Taker",
        help="Display name shown in the meeting (default: 'AI Note Taker')",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file for the meeting notes (default: meeting_notes_<timestamp>.md)",
    )
    parser.add_argument(
        "--model",
        default="grok-3",
        help="Grok model to use for summarization (default: grok-3)",
    )
    parser.add_argument(
        "--mic-mode",
        action="store_true",
        help="Use microphone input instead of system audio capture "
             "(useful for local testing)",
    )
    parser.add_argument(
        "--transcript-only",
        action="store_true",
        help="Only save the raw transcript without generating notes",
    )
    parser.add_argument(
        "--from-transcript",
        type=str,
        default=None,
        help="Skip meeting join and generate notes from an existing transcript file",
    )
    parser.add_argument(
        "--chunk-duration",
        type=int,
        default=30,
        help="Duration in seconds of each audio chunk for transcription (default: 30)",
    )
    parser.add_argument(
        "--admit-timeout",
        type=int,
        default=300,
        help="Seconds to wait for host to admit the bot (default: 300)",
    )

    # Calendar watch mode
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch Google Calendar and automatically join upcoming meetings",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=60,
        help="Seconds between calendar polls in watch mode (default: 60)",
    )
    parser.add_argument(
        "--join-before",
        type=int,
        default=1,
        help="Minutes before meeting start to join (default: 1)",
    )
    parser.add_argument(
        "--lookahead",
        type=int,
        default=10,
        help="Minutes ahead to look for upcoming meetings (default: 10)",
    )

    # Email options
    parser.add_argument(
        "--email",
        action="store_true",
        help="Email meeting notes to all attendees after the meeting",
    )
    parser.add_argument(
        "--email-to",
        nargs="+",
        default=None,
        help="Override attendee list — send notes to these email addresses instead",
    )
    parser.add_argument(
        "--include-transcript",
        action="store_true",
        help="Include the raw transcript in the email (appended below notes)",
    )

    return parser.parse_args()


def generate_notes_from_file(transcript_path: str, model: str, output: str | None) -> None:
    """Generate notes from an existing transcript file."""
    path = Path(transcript_path)
    if not path.exists():
        logger.error("Transcript file not found: %s", transcript_path)
        sys.exit(1)

    transcript = path.read_text()
    logger.info("Loaded transcript from %s (%d characters)", path, len(transcript))

    note_taker = GrokNoteTaker(model=model)
    notes = note_taker.summarize_streaming(transcript)

    output_path = output or f"meeting_notes_{int(time.time())}.md"
    Path(output_path).write_text(notes)
    logger.info("Notes saved to %s", output_path)


def run_live_session(
    meeting_url: str,
    args: argparse.Namespace,
    attendee_emails: list[str] | None = None,
    meeting_title: str = "Meeting",
) -> None:
    """Join a meeting, transcribe, and generate notes.

    Args:
        meeting_url: The Google Meet URL.
        args: Parsed CLI arguments.
        attendee_emails: Emails from the calendar event (for --watch mode).
        meeting_title: Title from the calendar event.
    """
    if "meet.google.com" not in meeting_url:
        logger.error("URL doesn't look like a Google Meet link: %s", meeting_url)
        return

    # Set up the transcriber
    if args.mic_mode:
        transcriber = MicrophoneTranscriber(chunk_duration=args.chunk_duration)
    else:
        transcriber = AudioTranscriber(chunk_duration=args.chunk_duration)

    bot = MeetBot(meeting_url=meeting_url, display_name=args.name)

    stop_requested = False

    def signal_handler(sig, frame):
        nonlocal stop_requested
        if stop_requested:
            logger.info("Force quitting...")
            sys.exit(1)
        stop_requested = True
        logger.info("\nStopping... press Ctrl+C again to force quit")

    signal.signal(signal.SIGINT, signal_handler)

    try:
        bot.join()

        if not bot.wait_for_admission(timeout=args.admit_timeout):
            logger.warning(
                "Was not admitted to the meeting within %ds. "
                "Proceeding anyway (may be in waiting room).",
                args.admit_timeout,
            )

        transcriber.start()
        logger.info("Recording and transcribing... Press Ctrl+C to stop.")

        while not stop_requested:
            if not bot.is_in_meeting():
                time.sleep(5)
                if not bot.is_in_meeting():
                    logger.info("Meeting appears to have ended")
                    break
            time.sleep(3)

    finally:
        transcriber.stop()
        transcript = transcriber.get_full_transcript()
        bot.leave()

        if not transcript.strip():
            logger.warning("No transcript was captured. Nothing to summarize.")
            return

        # Save raw transcript
        transcript_path = f"transcript_{int(time.time())}.txt"
        Path(transcript_path).write_text(transcript)
        logger.info("Raw transcript saved to %s", transcript_path)

        if args.transcript_only:
            logger.info("Transcript-only mode — skipping note generation.")
            return

        # Generate notes with Grok
        logger.info("Generating meeting notes with Grok...")
        note_taker = GrokNoteTaker(model=args.model)
        notes = note_taker.summarize_streaming(transcript)

        output_path = args.output or f"meeting_notes_{int(time.time())}.md"
        Path(output_path).write_text(notes)
        logger.info("Meeting notes saved to %s", output_path)

        # Email notes to attendees
        if args.email or args.email_to:
            _send_notes_email(
                args=args,
                notes=notes,
                transcript=transcript if args.include_transcript else None,
                meeting_title=meeting_title,
                attendee_emails=attendee_emails,
            )


def _send_notes_email(
    args: argparse.Namespace,
    notes: str,
    transcript: str | None,
    meeting_title: str,
    attendee_emails: list[str] | None,
) -> None:
    """Send the meeting notes via email."""
    from email_sender import EmailSender

    recipients = args.email_to or attendee_emails or []
    if not recipients:
        logger.warning(
            "No email recipients — use --email-to or run in --watch mode "
            "to auto-detect attendees from the calendar event"
        )
        return

    try:
        sender = EmailSender()
        sender.send_notes(
            recipients=recipients,
            meeting_title=meeting_title,
            notes=notes,
            transcript=transcript,
        )
    except Exception:
        logger.exception("Failed to email notes (notes are still saved locally)")


def run_watch_mode(args: argparse.Namespace) -> None:
    """Watch Google Calendar and auto-join meetings as they start."""
    from calendar_watcher import CalendarScheduler

    logger.info("Starting calendar watch mode")
    logger.info(
        "Will poll every %ds, join %dm before start, look %dm ahead",
        args.poll_interval,
        args.join_before,
        args.lookahead,
    )

    scheduler = CalendarScheduler(
        poll_interval=args.poll_interval,
        join_minutes_before=args.join_before,
        lookahead_minutes=args.lookahead,
    )

    for meeting in scheduler.watch():
        logger.info(
            "Auto-joining: '%s' at %s (%d attendees)",
            meeting.title,
            meeting.meet_url,
            len(meeting.attendee_emails),
        )

        # Include organizer in the email list
        all_emails = list(set(
            meeting.attendee_emails + [meeting.organizer_email]
        ))

        run_live_session(
            meeting_url=meeting.meet_url,
            args=args,
            attendee_emails=all_emails,
            meeting_title=meeting.title,
        )

        logger.info("Finished processing '%s' — resuming calendar watch", meeting.title)


def main() -> None:
    args = parse_args()

    # Check for API key early (unless transcript-only mode)
    if not args.transcript_only and not os.getenv("XAI_API_KEY"):
        logger.error(
            "XAI_API_KEY environment variable is required. "
            "Get your API key at https://console.x.ai"
        )
        sys.exit(1)

    if args.from_transcript:
        generate_notes_from_file(args.from_transcript, args.model, args.output)
    elif args.watch:
        run_watch_mode(args)
    else:
        if not args.meeting_url:
            logger.error(
                "Provide a meeting URL or use --watch mode. "
                "Run with --help for usage."
            )
            sys.exit(1)
        run_live_session(
            meeting_url=args.meeting_url,
            args=args,
            meeting_title="Meeting",
        )


if __name__ == "__main__":
    main()
