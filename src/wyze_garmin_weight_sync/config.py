from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True, slots=True)
class SyncSettings:
    state_dir: Path
    device_mac: str | None
    wyze_access_token: str | None
    wyze_refresh_token: str | None
    wyze_email: str | None
    wyze_password: str | None
    wyze_key_id: str | None
    wyze_api_key: str | None
    garmin_token: str | None
    garmin_email: str | None
    garmin_password: str | None

    @classmethod
    def from_env(cls, state_dir: Path) -> SyncSettings:
        return cls(
            state_dir=state_dir,
            device_mac=_env("WYZE_SCALE_MAC"),
            wyze_access_token=_env("WYZE_ACCESS_TOKEN"),
            wyze_refresh_token=_env("WYZE_REFRESH_TOKEN"),
            wyze_email=_env("WYZE_EMAIL"),
            wyze_password=_env("WYZE_PASSWORD"),
            wyze_key_id=_env("WYZE_KEY_ID"),
            wyze_api_key=_env("WYZE_API_KEY"),
            garmin_token=_env("GARMIN_TOKEN"),
            garmin_email=_env("GARMIN_EMAIL"),
            garmin_password=_env("GARMIN_PASSWORD"),
        )

    def validate_for_sync(self) -> None:
        if not self.garmin_token and not (self.garmin_email and self.garmin_password):
            msg = (
                "Garmin authentication is missing. Set GARMIN_TOKEN or "
                "GARMIN_EMAIL and GARMIN_PASSWORD."
            )
            raise ValueError(msg)

        has_wyze_token = self.wyze_access_token or self.wyze_refresh_token
        has_wyze_credentials = (
            self.wyze_email
            and self.wyze_password
            and self.wyze_key_id
            and self.wyze_api_key
        )
        if not has_wyze_token and not has_wyze_credentials:
            msg = (
                "Wyze authentication is missing. Set WYZE_ACCESS_TOKEN or "
                "WYZE_REFRESH_TOKEN, or provide WYZE_EMAIL, WYZE_PASSWORD, "
                "WYZE_KEY_ID, and WYZE_API_KEY."
            )
            raise ValueError(msg)
