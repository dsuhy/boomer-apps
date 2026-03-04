FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    pulseaudio \
    pulseaudio-utils \
    ffmpeg \
    xvfb \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Start virtual display + PulseAudio, then run the bot
ENTRYPOINT ["sh", "-c", "\
    Xvfb :99 -screen 0 1920x1080x24 & \
    export DISPLAY=:99 && \
    pulseaudio -D --exit-idle-time=-1 && \
    pactl load-module module-null-sink sink_name=DummyOutput && \
    pactl set-default-source DummyOutput.monitor && \
    python main.py \"$@\" \
", "--"]
