"""Settings, read once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from unlogged import dotenv

SANDBOX = "https://api-m.sandbox.paypal.com"
LIVE = "https://api-m.paypal.com"


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    base_url: str
    openai_api_key: str | None
    replay: bool
    github_token: str | None = None
    github_repo: str | None = None
    # Writing a cassette must be something someone asked for. It used to be a side effect of
    # any call that reached the network, so a --live verification run, or a judge who set
    # credentials, or a stray script with a stubbed transport would overwrite the committed
    # recordings the money claims rest on — and the next keyless run would report the wrong
    # number with no error, because a matching recording existed. It happened during an audit
    # of this repository: the demo replayed USD 1.00 instead of USD 902.50.
    record: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        dotenv.load()
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
            # Read-only, and optional: a public repository answers unauthenticated, and the
            # recorded thread replays with nothing set at all.
            github_token=os.environ.get("GITHUB_TOKEN") or None,
            github_repo=os.environ.get("GITHUB_REPO") or None,
            record=os.environ.get("UNLOGGED_RECORD", "") not in ("", "0", "false", "False"),
        )

    @property
    def has_github(self) -> bool:
        return bool(self.github_token)

    @property
    def has_paypal(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @property
    def openai_importable(self) -> bool:
        """Whether the SDK is actually installed, not merely configured.

        A key in the environment and an uninstallable module is the one combination that makes
        this service claim a capability it does not have, so the two are checked separately and
        reported separately.
        """
        import importlib.util

        return importlib.util.find_spec("openai") is not None

    @property
    def model_ready(self) -> bool:
        return bool(self.openai_api_key) and self.openai_importable

    def adjudicator_name(self) -> str:
        if self.model_ready:
            return "gpt-6.1-sol"
        if self.openai_api_key and not self.openai_importable:
            return "keyword-baseline (OPENAI_API_KEY set, but the openai package is not installed)"
        return "keyword-baseline"
