# AI Meet Note Taker

A Grok-powered bot that joins Google Meet meetings, transcribes the audio in real-time, generates structured meeting notes using xAI's Grok models, and emails the notes to all attendees.

## How It Works

1. **Watches your calendar** — Polls Google Calendar for upcoming meetings with Meet links (or accepts a manual URL)
2. **Joins the meeting** — Uses Selenium browser automation to open a headless Chrome instance and join the Google Meet call as a guest. Overlapping meetings are handled concurrently — each meeting runs in its own thread with a separate browser instance
3. **Captures audio** — Records system audio via PulseAudio (or microphone in local mode) and transcribes it in chunks using Google's Speech Recognition API
4. **Generates notes** — Sends the full transcript to Grok (via the xAI SDK) which produces structured meeting notes with summaries, action items, decisions, and open questions
5. **Emails attendees** — Sends the formatted notes (and optionally the raw transcript) to all meeting attendees via SMTP

## Prerequisites

- Python 3.10+
- Google Chrome / Chromium
- PulseAudio (for system audio capture on Linux)
- An xAI API key ([get one here](https://console.x.ai))
- Google Cloud OAuth2 credentials (for calendar watch mode)
- SMTP credentials (for emailing notes — Gmail App Passwords work well)

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

# Configure your keys
cp .env.example .env
# Edit .env and add your XAI_API_KEY, SMTP credentials, etc.
```

### Google Calendar Setup (for `--watch` mode)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **Google Calendar API**
3. Create an **OAuth 2.0 Client ID** (Desktop application type)
4. Download the JSON file and save it as `credentials.json` in this directory
5. On first run, a browser window will open for you to authorize access — the token is saved to `token.pickle` for future runs

### Email Setup (for `--email` mode)

For Gmail, create an [App Password](https://myaccount.google.com/apppasswords) and set these in `.env`:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
```

## Usage

### 1. Watch Calendar & Auto-Join (recommended)

```bash
python main.py --watch --email
```

The bot will:
- Poll your Google Calendar every 60 seconds
- Automatically join meetings 1 minute before they start
- Transcribe the entire meeting
- Generate notes with Grok
- Email the notes to all attendees listed on the calendar event

### 2. Join a specific meeting manually

```bash
python main.py "https://meet.google.com/abc-defg-hij"
```

### 3. Join and email notes to specific people

```bash
python main.py "https://meet.google.com/abc-defg-hij" \
  --email-to alice@company.com bob@company.com \
  --include-transcript
```

### 4. Generate notes from an existing transcript

```bash
python main.py --from-transcript meeting_transcript.txt
```

### All Options

```
python main.py --help

positional arguments:
  meeting_url               Google Meet URL (not needed with --watch or --from-transcript)

Core options:
  --name NAME               Display name in the meeting (default: 'AI Note Taker')
  --output FILE, -o         Output file for notes (default: meeting_notes_<timestamp>.md)
  --model MODEL             Grok model to use (default: grok-3)
  --mic-mode                Use microphone instead of system audio
  --transcript-only         Save raw transcript only, skip note generation
  --from-transcript FILE    Generate notes from an existing transcript file
  --chunk-duration N        Seconds per audio chunk (default: 30)
  --admit-timeout N         Seconds to wait for host admission (default: 300)

Calendar watch mode:
  --watch                   Watch Google Calendar and auto-join meetings
  --poll-interval N         Seconds between calendar polls (default: 60)
  --join-before N           Minutes before meeting start to join (default: 1)
  --lookahead N             Minutes ahead to scan for meetings (default: 10)

Email options:
  --email                   Email notes to all calendar attendees
  --email-to ADDR [ADDR...] Override recipients (space-separated emails)
  --include-transcript      Include raw transcript in the email body
```

## Docker

```bash
docker build -t meet-note-taker .

# Manual mode
docker run --rm -e XAI_API_KEY=your_key \
  meet-note-taker "https://meet.google.com/abc-defg-hij"

# Watch mode (mount credentials for calendar access)
docker run --rm \
  -e XAI_API_KEY=your_key \
  -e SMTP_USER=you@gmail.com \
  -e SMTP_PASSWORD=your_app_password \
  -v $(pwd)/credentials.json:/app/credentials.json \
  -v $(pwd)/token.pickle:/app/token.pickle \
  meet-note-taker --watch --email
```

## Output

The bot produces two files per meeting:

- `transcript_<timestamp>.txt` — Raw timestamped transcript
- `meeting_notes_<timestamp>.md` — Structured notes with:
  - Meeting summary
  - Key discussion points
  - Action items (with owners and deadlines)
  - Decisions made
  - Open questions

When `--email` is enabled, these notes are also sent as a formatted HTML email to all attendees.

## Architecture

```
main.py              — CLI entry point, orchestrates all modes
meet_bot.py          — Selenium-based Google Meet joiner
audio_capture.py     — PulseAudio / microphone audio capture + transcription
note_taker.py        — Grok-powered summarization via xAI SDK
calendar_watcher.py  — Google Calendar polling and meeting detection
email_sender.py      — SMTP email delivery with HTML formatting
```

## Limitations

- Google Meet's DOM changes frequently — selectors in `meet_bot.py` may need updating
- The bot joins as a visible participant (not invisible)
- System audio capture requires PulseAudio on Linux
- Google may show CAPTCHAs for automated joins from the same IP
- Meeting host must admit the bot if the meeting has a waiting room
- Calendar watch mode runs meetings concurrently — ensure your system has enough resources for multiple Chrome instances if you have back-to-back or overlapping meetings
