#!/usr/bin/env python3
"""AI Meeting Note Taker — joins a Google Meet call, transcribes audio,
and generates structured notes using Grok (xAI)."""

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


def run_live_session(args: argparse.Namespace) -> None:
    """Join a meeting, transcribe, and generate notes."""
    # Validate meeting URL
    if "meet.google.com" not in args.meeting_url:
        logger.error("URL doesn't look like a Google Meet link: %s", args.meeting_url)
        sys.exit(1)

    # Set up the transcriber
    if args.mic_mode:
        transcriber = MicrophoneTranscriber(chunk_duration=args.chunk_duration)
    else:
        transcriber = AudioTranscriber(chunk_duration=args.chunk_duration)

    # Set up the Meet bot
    bot = MeetBot(meeting_url=args.meeting_url, display_name=args.name)

    # Handle Ctrl+C gracefully
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
        # Join the meeting
        bot.join()

        # Wait for admission
        if not bot.wait_for_admission(timeout=args.admit_timeout):
            logger.warning(
                "Was not admitted to the meeting within %ds. "
                "Proceeding anyway (may be in waiting room).",
                args.admit_timeout,
            )

        # Start transcription
        transcriber.start()
        logger.info("Recording and transcribing... Press Ctrl+C to stop.")

        # Keep running until user stops or meeting ends
        while not stop_requested:
            if not bot.is_in_meeting():
                # Check a few times before deciding the meeting ended
                time.sleep(5)
                if not bot.is_in_meeting():
                    logger.info("Meeting appears to have ended")
                    break
            time.sleep(3)

    finally:
        # Stop transcription
        transcriber.stop()
        transcript = transcriber.get_full_transcript()

        # Leave the meeting
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
    else:
        run_live_session(args)


if __name__ == "__main__":
    main()
