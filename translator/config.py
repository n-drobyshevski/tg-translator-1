"""
Centralized configuration with environment validation.
"""

import os
from typing import Dict, Optional, Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional


class Config:
    """Holds all configuration values loaded from environment variables."""

    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_API_ID: int
    TELEGRAM_API_HASH: str
    ANTHROPIC_API_KEY: str
    CHANNELS: Dict[str, int]
    SOURCE_TEST_ID: int
    LOG_LEVEL: str

    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        """Reload configuration from environment variables."""
        self.TELEGRAM_BOT_TOKEN = self._require("TELEGRAM_BOT_TOKEN")
        self.TELEGRAM_API_ID = int(self._require("TELEGRAM_API_ID"))
        self.TELEGRAM_API_HASH = self._require("TELEGRAM_API_HASH")
        self.ANTHROPIC_API_KEY = self._require("ANTHROPIC_API_KEY")
        self.SOURCE_TEST_ID = int(self._require("SOURCE_TEST_ID"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

        self.CHANNELS = {
            "christianvision": int(self._require("CHRISTIANVISION_CHANNEL")),
            "shaltnotkill": int(self._require("SHALTNOTKILL_CHANNEL")),
            "test": self.SOURCE_TEST_ID,
        }

    def _require(self, var: str) -> str:
        val = os.getenv(var)
        if not val:
            raise RuntimeError(
                f"Missing required environment variable: {var}\n"
                f"Please set it in your environment or .env file."
            )
        return val

    def get_channel_id(self, name: str) -> Optional[int]:
        """Get channel ID by logical name."""
        return self.CHANNELS.get(name)

    def validate(self) -> None:
        """Validate that all required config values are present."""
        required_vars = [
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_API_ID",
            "TELEGRAM_API_HASH",
            "ANTHROPIC_API_KEY",
            "CHRISTIANVISION_CHANNEL",
            "SHALTNOTKILL_CHANNEL",
            "SOURCE_TEST_ID",
        ]
        missing = [v for v in required_vars if not os.getenv(v)]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

    def as_dict(self) -> Dict[str, Any]:
        """Return config as a dict (for debugging/testing)."""
        return {
            "TELEGRAM_BOT_TOKEN": self.TELEGRAM_BOT_TOKEN,
            "TELEGRAM_API_ID": self.TELEGRAM_API_ID,
            "TELEGRAM_API_HASH": self.TELEGRAM_API_HASH,
            "ANTHROPIC_API_KEY": self.ANTHROPIC_API_KEY,
            "CHANNELS": self.CHANNELS,
            "SOURCE_TEST_ID": self.SOURCE_TEST_ID,
            "LOG_LEVEL": self.LOG_LEVEL,
        }


CONFIG = Config()
