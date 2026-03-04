# AI Meet Note Taker

A Grok-powered bot that joins Google Meet meetings, transcribes the audio in real-time, and generates structured meeting notes using xAI's Grok models.

## How It Works

1. **Joins the meeting** — Uses Selenium browser automation to open a headless Chrome instance and join the Google Meet call as a guest
2. **Captures audio** — Records system audio via PulseAudio (or microphone in local mode) and transcribes it in chunks using Google's Speech Recognition API
3. **Generates notes** — Sends the full transcript to Grok (via the xAI SDK) which produces structured meeting notes with summaries, action items, decisions, and open questions

## Prerequisites

- Python 3.10+
- Google Chrome / Chromium
- PulseAudio (for system audio capture on Linux)
- An xAI API key ([get one here](https://console.x.ai))

### System Dependencies (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y chromium-browser pulseaudio pulseaudio-utils ffmpeg portaudio19-dev
```

## Setup

```bash
cd ai-meet-note-taker

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure your API key
cp .env.example .env
# Edit .env and add your XAI_API_KEY
```

## Usage

### Join a meeting and take notes

```bash
python main.py "https://meet.google.com/abc-defg-hij"
```

The bot will join the meeting, transcribe audio in real-time, and when you press `Ctrl+C` (or the meeting ends), it generates structured notes using Grok.

### Options

```
python main.py --help

positional arguments:
  meeting_url           Google Meet URL to join

options:
  --name NAME           Display name shown in the meeting (default: 'AI Note Taker')
  --output FILE, -o     Output file for the meeting notes
  --model MODEL         Grok model to use (default: grok-3)
  --mic-mode            Use microphone instead of system audio capture
  --transcript-only     Save raw transcript without generating notes
  --from-transcript F   Generate notes from an existing transcript file
  --chunk-duration N    Seconds per audio chunk (default: 30)
  --admit-timeout N     Seconds to wait for host admission (default: 300)
```

### Generate notes from an existing transcript

```bash
python main.py --from-transcript meeting_transcript.txt "https://meet.google.com/unused"
```

### Local testing with microphone

```bash
python main.py --mic-mode "https://meet.google.com/abc-defg-hij"
```

## Docker

For a fully self-contained headless setup:

```bash
docker build -t meet-note-taker .
docker run --rm -e XAI_API_KEY=your_key meet-note-taker "https://meet.google.com/abc-defg-hij"
```

## Output

The bot produces two files:

- `transcript_<timestamp>.txt` — Raw timestamped transcript
- `meeting_notes_<timestamp>.md` — Structured notes with:
  - Meeting summary
  - Key discussion points
  - Action items (with owners and deadlines)
  - Decisions made
  - Open questions

## Architecture

```
main.py            — CLI entry point, orchestrates the session
meet_bot.py        — Selenium-based Google Meet joiner
audio_capture.py   — PulseAudio / microphone audio capture + transcription
note_taker.py      — Grok-powered summarization via xAI SDK
```

## Limitations

- Google Meet's DOM changes frequently — selectors in `meet_bot.py` may need updating
- The bot joins as a visible participant (not invisible)
- System audio capture requires PulseAudio on Linux
- Google may show CAPTCHAs for automated joins from the same IP
- Meeting host must admit the bot if the meeting has a waiting room
