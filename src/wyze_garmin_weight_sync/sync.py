from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from .config import SyncSettings
from .fit_encoder import build_fit_file
from .garmin import configure_garmin, upload_fit_file
from .state import is_new_measurement, load_state, save_state
from .wyze import authenticate_wyze, fetch_latest_measurement

LOGGER = logging.getLogger(__name__)


def run_sync(settings: SyncSettings) -> int:
    settings.validate_for_sync()

    state_path = settings.state_dir / "state.json"
    current_state = load_state(state_path)
    wyze_session = authenticate_wyze(
        access_token=settings.wyze_access_token,
        refresh_token=settings.wyze_refresh_token,
        email=settings.wyze_email,
        password=settings.wyze_password,
        key_id=settings.wyze_key_id,
        api_key=settings.wyze_api_key,
    )
    garmin_auth_source = configure_garmin(
        token=settings.garmin_token,
        email=settings.garmin_email,
        password=settings.garmin_password,
    )
    measurement = fetch_latest_measurement(
        wyze_session.client,
        device_mac=settings.device_mac,
    )

    if not is_new_measurement(current_state, measurement):
        LOGGER.info(
            "No new measurement. Latest Wyze record %s was already uploaded.",
            measurement.measurement_id,
        )
        return 0

    fit_payload = build_fit_file(measurement)
    with _temporary_fit_file(fit_payload) as fit_path:
        upload_fit_file(fit_path)

    save_state(state_path, measurement)
    LOGGER.info(
        (
            "Uploaded measurement %s at %s (%.2f kg) using Wyze %s "
            "and Garmin %s authentication."
        ),
        measurement.measurement_id,
        measurement.measured_at.isoformat(),
        measurement.weight_kg,
        wyze_session.auth_source,
        garmin_auth_source,
    )
    _warn_about_rotated_wyze_tokens(
        configured_access_token=settings.wyze_access_token,
        configured_refresh_token=settings.wyze_refresh_token,
        refreshed_access_token=wyze_session.access_token,
        refreshed_refresh_token=wyze_session.refresh_token,
    )
    return 0


class _temporary_fit_file:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._path: Path | None = None

    def __enter__(self) -> Path:
        with tempfile.NamedTemporaryFile(
            prefix="wyze-scale-",
            suffix=".fit",
            delete=False,
        ) as handle:
            handle.write(self._payload)
            self._path = Path(handle.name)
        return self._path

    def __exit__(self, *_args: object) -> None:
        if self._path is None:
            return
        self._path.unlink(missing_ok=True)


def _warn_about_rotated_wyze_tokens(
    *,
    configured_access_token: str | None,
    configured_refresh_token: str | None,
    refreshed_access_token: str | None,
    refreshed_refresh_token: str | None,
) -> None:
    if not os.getenv("GITHUB_ACTIONS"):
        return

    token_changed = False
    if refreshed_access_token and refreshed_access_token != configured_access_token:
        token_changed = True
    if refreshed_refresh_token and refreshed_refresh_token != configured_refresh_token:
        token_changed = True

    if token_changed:
        print(
            "::warning::Wyze tokens changed during this run. "
            "Update the GitHub Actions secrets if the existing token set stops working."
        )
