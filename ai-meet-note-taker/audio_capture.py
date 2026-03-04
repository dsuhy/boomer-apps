"""Capture audio from browser/system and transcribe it to text."""

import io
import logging
import subprocess
import threading
import time
import wave

import speech_recognition as sr

logger = logging.getLogger(__name__)

# Duration in seconds for each audio chunk sent to the recognizer
CHUNK_DURATION = 30
SAMPLE_RATE = 16000
CHANNELS = 1


class AudioTranscriber:
    """Records system/browser audio and transcribes it in chunks using
    Google's free Speech Recognition API."""

    def __init__(self, chunk_duration: int = CHUNK_DURATION):
        self.chunk_duration = chunk_duration
        self.recognizer = sr.Recognizer()
        self._running = False
        self._thread = None
        self.transcript_segments: list[dict] = []

    def start(self) -> None:
        """Begin capturing and transcribing audio in the background."""
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Audio transcription started")

    def stop(self) -> None:
        """Stop the capture loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Audio transcription stopped")

    def get_full_transcript(self) -> str:
        """Return the full transcript assembled so far."""
        return "\n".join(seg["text"] for seg in self.transcript_segments)

    def _capture_loop(self) -> None:
        """Continuously record chunks and transcribe them."""
        while self._running:
            try:
                audio_data = self._record_chunk()
                if audio_data:
                    text = self._transcribe(audio_data)
                    if text:
                        segment = {
                            "timestamp": time.strftime("%H:%M:%S"),
                            "text": text,
                        }
                        self.transcript_segments.append(segment)
                        logger.info("[%s] %s", segment["timestamp"], text)
            except Exception:
                logger.exception("Error in audio capture loop")
                time.sleep(2)

    def _record_chunk(self) -> sr.AudioData | None:
        """Record a chunk of audio from the system's default PulseAudio
        monitor source using parec, then wrap it as an AudioData object."""
        try:
            proc = subprocess.run(
                [
                    "parec",
                    "--rate", str(SAMPLE_RATE),
                    "--channels", str(CHANNELS),
                    "--format", "s16le",
                    "--device", _get_monitor_source(),
                    "--raw",
                ],
                capture_output=True,
                timeout=self.chunk_duration + 2,
            )
            raw = proc.stdout
        except FileNotFoundError:
            logger.error(
                "parec not found — install PulseAudio utilities "
                "(apt install pulseaudio-utils)"
            )
            self._running = False
            return None
        except subprocess.TimeoutExpired:
            # TimeoutExpired still gives us partial output
            return None

        if not raw or len(raw) < SAMPLE_RATE * 2:
            return None

        return sr.AudioData(raw, SAMPLE_RATE, 2)

    def _transcribe(self, audio: sr.AudioData) -> str | None:
        """Transcribe an AudioData chunk using Google free speech API."""
        try:
            text = self.recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            logger.debug("Could not understand audio chunk")
            return None
        except sr.RequestError as exc:
            logger.error("Speech recognition API error: %s", exc)
            return None


class MicrophoneTranscriber:
    """Fallback transcriber that records from the default microphone.
    Useful for local testing without PulseAudio monitor setup."""

    def __init__(self, chunk_duration: int = CHUNK_DURATION):
        self.chunk_duration = chunk_duration
        self.recognizer = sr.Recognizer()
        self._running = False
        self._thread = None
        self.transcript_segments: list[dict] = []

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Microphone transcription started (fallback mode)")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    def get_full_transcript(self) -> str:
        return "\n".join(seg["text"] for seg in self.transcript_segments)

    def _capture_loop(self) -> None:
        while self._running:
            try:
                with sr.Microphone(sample_rate=SAMPLE_RATE) as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    audio = self.recognizer.listen(
                        source, timeout=self.chunk_duration, phrase_time_limit=self.chunk_duration
                    )
                    text = self._transcribe(audio)
                    if text:
                        segment = {
                            "timestamp": time.strftime("%H:%M:%S"),
                            "text": text,
                        }
                        self.transcript_segments.append(segment)
                        logger.info("[%s] %s", segment["timestamp"], text)
            except sr.WaitTimeoutError:
                continue
            except Exception:
                logger.exception("Error in microphone capture loop")
                time.sleep(2)

    def _transcribe(self, audio: sr.AudioData) -> str | None:
        try:
            return self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return None
        except sr.RequestError as exc:
            logger.error("Speech recognition API error: %s", exc)
            return None


def _get_monitor_source() -> str:
    """Detect the PulseAudio monitor source for capturing system audio."""
    try:
        result = subprocess.run(
            ["pactl", "list", "short", "sources"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if ".monitor" in line:
                return line.split()[1]
    except Exception:
        pass
    # Fallback default
    return "auto_null.monitor"
