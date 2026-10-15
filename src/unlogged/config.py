"""Settings, read once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

SANDBOX = "https://api-m.sandbox.paypal.com"
LIVE = "https://api-m.paypal.com"


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    base_url: str
    openai_api_key: str | None
    replay: bool

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ.get("PAYPAL_ENV", "sandbox").lower()
        if env not in ("sandbox", "live"):
            raise ValueError(f"PAYPAL_ENV must be sandbox or live, got {env!r}")
        return cls(
            client_id=os.environ.get("PAYPAL_CLIENT_ID", ""),
            client_secret=os.environ.get("PAYPAL_CLIENT_SECRET", ""),
            base_url=SANDBOX if env == "sandbox" else LIVE,
            openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
            # Replay is the default so the project runs for anyone with no credentials.
            replay=os.environ.get("UNLOGGED_REPLAY", "1") not in ("0", "false", "False", ""),
        )

    @property
    def has_paypal(self) -> bool:
        return bool(self.client_id and self.client_secret)
