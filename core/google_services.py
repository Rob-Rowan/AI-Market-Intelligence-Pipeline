"""Google Cloud service authentication and client initialisation."""

from __future__ import annotations

import logging
import os
import socket

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from gspread.client import Client
from slack_sdk import WebClient

logger = logging.getLogger(__name__)

_GOOGLE_AUTH_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.send",
]


class AutomationServices:
    """Authorised clients for Google Workspace and Slack services.

    Builds all Google API clients from a service-account credentials
    file and optionally a Slack ``WebClient`` from the ``SLACK_BOT_TOKEN``
    environment variable.

    Attributes:
        credentials_path: Path to the Google service account JSON file.
        env_path: Path to the ``.env`` file containing secret tokens.
        gspread_client: Authenticated gspread :class:`Client` instance.
        drive_service: Google Drive API v3 :class:`Resource` instance.
        docs_service: Google Docs API v1 :class:`Resource` instance.
        gmail_service: Google Gmail API v1 :class:`Resource` instance.
        slack_client: Slack :class:`WebClient` instance or ``None``.
    """

    def __init__(
        self,
        credentials_path: str = "credentials.json",
        env_path: str = ".env",
    ) -> None:
        """Load environment variables and authenticate all services.

        Args:
            credentials_path: Path to the Google service account
                credentials JSON file.
            env_path: Path to the ``.env`` file containing secret tokens.

        Raises:
            RuntimeError: If Google service authentication fails.
        """
        self.credentials_path = credentials_path
        self.env_path = env_path
        self.gspread_client: Client | None = None
        self.drive_service: Resource | None = None
        self.docs_service: Resource | None = None
        self.gmail_service: Resource | None = None
        self.slack_client: WebClient | None = None

        self._load_env()
        self._authenticate_google()
        self._authenticate_slack()

    def _load_env(self) -> None:
        """Load environment variables from the ``.env`` file, if present."""
        load_dotenv(dotenv_path=self.env_path)
        logger.info("Loaded environment variables from %s.", self.env_path)

    def _authenticate_google(self) -> None:
        """Build the gspread, Drive, Docs, and Gmail API clients.

        Raises:
            RuntimeError: If any Google client fails to initialise.
        """
        try:
            creds = Credentials.from_service_account_file(
                self.credentials_path, scopes=_GOOGLE_AUTH_SCOPES
            )
            self.gspread_client = gspread.authorize(creds)
            self.drive_service = build("drive", "v3", credentials=creds)
            self.docs_service = build("docs", "v1", credentials=creds)
            self.gmail_service = build("gmail", "v1", credentials=creds)
        except (socket.timeout, HttpError) as exc:
            logger.error(
                "Transient network failure while authenticating Google "
                "services: %s",
                exc,
            )
            raise
        except Exception as exc:
            logger.exception(
                "Google service authentication failed; verify %s "
                "exists and is shared with the target sheet/docs.",
                self.credentials_path,
            )
            raise RuntimeError(
                f"Google service authentication failed: {exc}"
            ) from exc

        logger.info(
            "Initialised gspread, Drive, Docs, and Gmail clients."
        )

    def _authenticate_slack(self) -> None:
        """Initialise the Slack client if ``SLACK_BOT_TOKEN`` is set."""
        slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        if not slack_bot_token:
            logger.warning(
                "SLACK_BOT_TOKEN not set; Slack notifications disabled."
            )
            return
        try:
            self.slack_client = WebClient(token=slack_bot_token)
        except Exception as exc:
            logger.error("Failed to initialise Slack client: %s", exc)
            return
        logger.info("Initialised Slack client.")