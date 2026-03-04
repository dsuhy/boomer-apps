"""Send meeting notes to attendees via email."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends meeting notes to attendees via SMTP."""

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        from_address: str | None = None,
    ):
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER", "")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD", "")
        self.from_address = from_address or os.getenv(
            "EMAIL_FROM", self.smtp_user
        )

        if not self.smtp_user or not self.smtp_password:
            raise ValueError(
                "SMTP credentials required. Set SMTP_USER and SMTP_PASSWORD "
                "environment variables (or SMTP_HOST/SMTP_PORT to use a "
                "non-Gmail server). For Gmail, use an App Password: "
                "https://myaccount.google.com/apppasswords"
            )

    def send_notes(
        self,
        recipients: list[str],
        meeting_title: str,
        notes: str,
        transcript: str | None = None,
    ) -> None:
        """Email the meeting notes to all recipients.

        Args:
            recipients: List of email addresses to send to.
            meeting_title: The meeting title (used in the subject line).
            notes: The formatted meeting notes (markdown).
            transcript: Optional raw transcript to attach.
        """
        if not recipients:
            logger.warning("No recipients provided — skipping email")
            return

        subject = f"Meeting Notes: {meeting_title}"

        # Build the email body — plain text version of the notes
        # plus an HTML version for clients that support it
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_address
        msg["To"] = ", ".join(recipients)

        # Plain text part
        plain_body = (
            f"Meeting Notes: {meeting_title}\n"
            f"{'=' * 40}\n\n"
            f"{notes}"
        )
        if transcript:
            plain_body += (
                f"\n\n{'=' * 40}\n"
                f"Raw Transcript\n"
                f"{'=' * 40}\n\n"
                f"{transcript}"
            )
        msg.attach(MIMEText(plain_body, "plain"))

        # HTML part — wrap markdown notes in a basic template
        html_body = _markdown_to_html(notes, meeting_title, transcript)
        msg.attach(MIMEText(html_body, "html"))

        try:
            logger.info(
                "Sending notes to %d recipients via %s:%d",
                len(recipients),
                self.smtp_host,
                self.smtp_port,
            )
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_address, recipients, msg.as_string())

            logger.info("Meeting notes emailed to: %s", ", ".join(recipients))
        except Exception:
            logger.exception("Failed to send email")
            raise


def _markdown_to_html(
    notes: str, title: str, transcript: str | None
) -> str:
    """Convert markdown notes to a simple HTML email.

    Does basic markdown-to-HTML conversion for bold, headers, and lists
    without requiring an external library.
    """
    import re

    # Escape HTML
    html_notes = notes.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Convert markdown headers
    html_notes = re.sub(
        r"^#{1,3}\s+(.+)$", r"<h3>\1</h3>", html_notes, flags=re.MULTILINE
    )

    # Convert bold
    html_notes = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_notes)

    # Convert bullet points
    html_notes = re.sub(
        r"^[-*]\s+(.+)$", r"<li>\1</li>", html_notes, flags=re.MULTILINE
    )

    # Convert numbered lists
    html_notes = re.sub(
        r"^\d+\.\s+(.+)$", r"<li>\1</li>", html_notes, flags=re.MULTILINE
    )

    # Wrap consecutive <li> in <ul>
    html_notes = re.sub(
        r"((?:<li>.*?</li>\n?)+)",
        r"<ul>\1</ul>",
        html_notes,
    )

    # Convert newlines to <br> for remaining plain text
    html_notes = html_notes.replace("\n", "<br>\n")

    transcript_section = ""
    if transcript:
        escaped_transcript = (
            transcript.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>\n")
        )
        transcript_section = f"""
        <hr>
        <h3>Raw Transcript</h3>
        <div style="background: #f5f5f5; padding: 16px; border-radius: 8px;
                    font-size: 13px; color: #555; white-space: pre-wrap;">
            {escaped_transcript}
        </div>
        """

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
             Roboto, sans-serif; max-width: 700px; margin: 0 auto;
             padding: 20px; color: #333;">
    <h2 style="border-bottom: 2px solid #4285f4; padding-bottom: 8px;">
        Meeting Notes: {title}
    </h2>
    <div style="line-height: 1.6;">
        {html_notes}
    </div>
    {transcript_section}
    <hr>
    <p style="font-size: 12px; color: #999;">
        Generated by AI Meet Note Taker (powered by Grok)
    </p>
</body>
</html>
"""
