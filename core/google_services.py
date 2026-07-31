"""Google Cloud service authentication and client initialization."""

import os

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource
import gspread
from gspread.client import Client
from slack_sdk import WebClient


class AutomationServices:
    """Authorised clients for Google Workspace and Slack services.

    Initialises and manages connections to Google Sheets, Drive, Docs,
    Gmail, and Slack using a service account credentials file and
    environment variables.

    Attributes:
        credentials_path: Path to the Google service account JSON file.
        env_path: Path to the .env file containing secret tokens.
        gspread_client: Authenticated gspread :class:`Client` instance.
        drive_service: Google Drive API v3 :class:`Resource` instance.
        docs_service: Google Docs API v1 :class:`Resource` instance.
        gmail_service: Google Gmail API v1 :class:`Resource` instance.
        slack_client: Slack :class:`WebClient` instance (or None).
    """

    def __init__(
        self,
        credentials_path: str = "credentials.json",
        env_path: str = ".env",
    ) -> None:
        """Initialise AutomationServices and authenticate all clients.

        Args:
            credentials_path: Relative path to the Google service
                account credentials JSON file. Defaults to
                ``"credentials.json"``.
            env_path: Relative path to the ``.env`` file containing
                ``SLACK_BOT_TOKEN`` et al. Defaults to ``".env"``.
        """
        self.credentials_path = credentials_path
        self.env_path = env_path
        self.gspread_client: Client | None = None
        self.drive_service: Resource | None = None
        self.docs_service: Resource | None = None
        self.gmail_service: Resource | None = None
        self.slack_client: WebClient | None = None

        self._load_env()
        self._authenticate()

    def _load_env(self) -> None:
        """Load environment variables from the ``.env`` file."""
        try:
            load_dotenv(dotenv_path=self.env_path)
            print("Successfully loaded .env file.")
        except Exception as e:
            print(f"Error loading .env file: {e}")

    def _authenticate(self) -> None:
        """Authenticate and initialise all Google and Slack service clients.

        Raises:
            Exception: Propagates any authentication or API
                initialisation failure.
        """
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/gmail.send",
            ]

            creds = Credentials.from_service_account_file(
                self.credentials_path, scopes=scopes
            )

            # Initialise gspread
            self.gspread_client = gspread.authorize(creds)
            print("Successfully initialised gspread client.")

            # Initialise Google Drive API
            self.drive_service = build("drive", "v3", credentials=creds)
            print("Successfully initialised Google Drive API client.")

            # Initialise Google Docs API
            self.docs_service = build("docs", "v1", credentials=creds)
            print("Successfully initialised Google Docs API client.")

            # Initialise Google Gmail API
            self.gmail_service = build("gmail", "v1", credentials=creds)
            print("Successfully initialised Google Gmail API client.")

        except Exception as e:
            print(
                f"An error occurred during Google services authentication: {e}"
            )

        try:
            # Initialise Slack SDK
            slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
            if slack_bot_token:
                self.slack_client = WebClient(token=slack_bot_token)
                print("Successfully initialised Slack client.")
            else:
                print(
                    "SLACK_BOT_TOKEN not found in .env file. "
                    "Slack client not initialised."
                )
        except Exception as e:
            print(
                f"An error occurred during Slack client initialisation: {e}"
            )


if __name__ == "__main__":
    if not os.path.exists("credentials.json"):
        with open("credentials.json", "w") as f:
            f.write("{}")
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write("SLACK_BOT_TOKEN=your_slack_bot_token")

    services = AutomationServices()