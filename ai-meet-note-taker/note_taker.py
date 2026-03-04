"""Grok-powered meeting note taker using the xAI SDK."""

import logging
import os

from xai_sdk import Client
from xai_sdk.chat import system, user

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert meeting note-taker. You will receive a raw transcript of a \
meeting. Your job is to produce clear, well-organized meeting notes.

Your notes MUST include:
1. **Meeting Summary** — A 2-3 sentence high-level overview of what was discussed.
2. **Key Discussion Points** — Bullet points covering each major topic discussed, \
with relevant details and context.
3. **Action Items** — A numbered list of tasks, decisions, or follow-ups mentioned \
in the meeting. For each item, include who is responsible (if mentioned) and any \
deadlines.
4. **Decisions Made** — Any explicit decisions or agreements reached during the meeting.
5. **Open Questions** — Anything left unresolved or needing follow-up.

Guidelines:
- Be concise but thorough. Don't omit important details.
- Use professional language and clean formatting.
- If the transcript is noisy or unclear in places, do your best to infer meaning \
and note any uncertain sections with [unclear].
- Attribute statements to speakers when possible (if names are mentioned).
"""


class GrokNoteTaker:
    """Uses Grok via the xAI SDK to turn raw transcripts into structured notes."""

    def __init__(self, model: str = "grok-3"):
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError(
                "XAI_API_KEY environment variable is required. "
                "Get one at https://console.x.ai"
            )
        self.client = Client(api_key=api_key)
        self.model = model

    def summarize(self, transcript: str) -> str:
        """Generate structured meeting notes from a transcript."""
        if not transcript.strip():
            return "No transcript content to summarize."

        logger.info(
            "Sending transcript to Grok (%d characters, model=%s)",
            len(transcript),
            self.model,
        )

        chat = self.client.chat.create(model=self.model)
        chat.append(system(SYSTEM_PROMPT))
        chat.append(
            user(
                f"Here is the raw meeting transcript:\n\n"
                f"---\n{transcript}\n---\n\n"
                f"Please produce structured meeting notes."
            )
        )

        response = chat.sample()
        notes = response.content
        logger.info("Generated meeting notes (%d characters)", len(notes))
        return notes

    def summarize_streaming(self, transcript: str) -> str:
        """Generate notes with streaming output (prints as it goes)."""
        if not transcript.strip():
            return "No transcript content to summarize."

        chat = self.client.chat.create(model=self.model)
        chat.append(system(SYSTEM_PROMPT))
        chat.append(
            user(
                f"Here is the raw meeting transcript:\n\n"
                f"---\n{transcript}\n---\n\n"
                f"Please produce structured meeting notes."
            )
        )

        full_text = ""
        print("\n--- Meeting Notes (streaming) ---\n")
        for response, chunk in chat.stream():
            print(chunk.content, end="", flush=True)
            full_text += chunk.content
        print("\n\n--- End of Notes ---\n")

        return full_text

    def ask_about_meeting(self, transcript: str, question: str) -> str:
        """Ask a follow-up question about the meeting."""
        chat = self.client.chat.create(model=self.model)
        chat.append(
            system(
                "You are a helpful assistant that answers questions about a meeting "
                "based on its transcript. Be specific and reference what was said."
            )
        )
        chat.append(
            user(
                f"Meeting transcript:\n\n---\n{transcript}\n---\n\n"
                f"Question: {question}"
            )
        )

        response = chat.sample()
        return response.content
