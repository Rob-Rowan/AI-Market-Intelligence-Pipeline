"""Notification dispatch via Slack and Gmail."""

from __future__ import annotations

import logging
import os
import smtplib
import socket
from email.message import EmailMessage

from slack_sdk.errors import SlackApiError

from core.google_services import AutomationServices

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_TIMEOUT_SECONDS = 30


class Notifier:
    """Send digest notifications through Slack and Gmail.

    Attributes:
        services: An authenticated :class:`AutomationServices` instance
            that provides a Slack client.
    """

    def __init__(self, services: AutomationServices) -> None:
        """Initialise the notifier.

        Args:
            services: An authenticated :class:`AutomationServices`
                instance exposing the ``.slack_client`` attribute.
        """
        self.services = services

    def send_slack_message(
        self, channel_id: str, message: str
    ) -> None:
        """Post a plain-text message to a Slack channel.

        Args:
            channel_id: The Slack channel ID (e.g. ``"C01234567"``).
            message: The message body to post.
        """
        if self.services.slack_client is None:
            logger.error(
                "Slack client is not initialised; cannot send to %s.",
                channel_id,
            )
            return

        try:
            self.services.slack_client.chat_postMessage(
                channel=channel_id, text=message
            )
        except (SlackApiError, socket.timeout):
            logger.exception(
                "Failed to send Slack message to channel %s.",
                channel_id,
            )
            return
        logger.info("Slack message delivered to channel %s.", channel_id)

    def send_gmail_summary(
        self, target_email: str, subject: str, body: str
    ) -> None:
        """Send a plain-text digest email via Gmail's SMTP over SSL.

        Requires the environment variables ``GMAIL_SENDER`` and
        ``GMAIL_APP_PASSWORD``.

        Args:
            target_email: The recipient email address.
            subject: The email subject line.
            body: The plain-text email body.
        """
        sender_email = os.environ.get("GMAIL_SENDER")
        app_password = os.environ.get("GMAIL_APP_PASSWORD")
        if not sender_email or not app_password:
            logger.error(
                "GMAIL_SENDER and GMAIL_APP_PASSWORD must be set "
                "to send the email digest."
            )
            return

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = target_email
        msg.set_content(body)

        try:
            with smtplib.SMTP_SSL(
                SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS
            ) as server:
                server.login(sender_email, app_password)
                server.send_message(msg)
        except (smtplib.SMTPException, socket.timeout, OSError):
            logger.exception(
                "Failed to send Gmail digest to %s.", target_email
            )
            return
        logger.info("Gmail digest delivered to %s.", target_email)