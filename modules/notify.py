"""Notification dispatch via Slack and Gmail."""

import os
import smtplib
from email.message import EmailMessage

from core.google_services import AutomationServices


class Notifier:
    """Send notifications through Slack and Gmail.

    Attributes:
        services: An authenticated :class:`AutomationServices` instance
            that provides a Slack client.
    """

    def __init__(self, services: AutomationServices) -> None:
        """Initialise the Notifier.

        Args:
            services: An authenticated :class:`AutomationServices`
                instance. The ``.slack_client`` attribute is used for
                Slack messaging.
        """
        self.services = services

    def send_slack_message(
        self, channel_id: str, message: str
    ) -> None:
        """Send a message to a Slack channel.

        Args:
            channel_id: The Slack channel ID (e.g. ``"C01234567"``).
            message: The plain-text message to post.
        """
        try:
            self.services.slack_client.chat_postMessage(
                channel=channel_id, text=message
            )
            print(
                f"Successfully sent Slack message to channel "
                f"{channel_id}"
            )
        except Exception as e:
            print(f"Error sending Slack message: {e}")

    def send_gmail_summary(
        self, target_email: str, subject: str, body: str
    ) -> None:
        """Send an email summary via Gmail's SMTP (SSL).

        Requires the environment variables ``GMAIL_SENDER`` and
        ``GMAIL_APP_PASSWORD`` to be set.

        Args:
            target_email: The recipient email address.
            subject: The email subject line.
            body: The plain-text email body.
        """
        sender_email = os.environ.get("GMAIL_SENDER")
        app_password = os.environ.get("GMAIL_APP_PASSWORD")

        if not sender_email or not app_password:
            print(
                "Error: GMAIL_SENDER and GMAIL_APP_PASSWORD "
                "environment variables must be set."
            )
            return

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = target_email
        msg.set_content(body)

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, app_password)
                server.send_message(msg)
            print(f"Successfully sent email to {target_email}")
        except Exception as e:
            print(f"Error sending email: {e}")