from __future__ import annotations

import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .config import SyncSettings
from .fit_encoder import build_fit_file
from .garmin import configure_garmin, upload_fit_file
from .models import SyncState
from .state import is_new_measurement, load_state, save_state
from .wyze import authenticate_wyze, fetch_measurements

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
    measurements = fetch_measurements(
        wyze_session.client,
        device_mac=settings.device_mac,
        start_time=_state_measurement_time(current_state),
    )
    new_measurements = [
        measurement
        for measurement in measurements
        if is_new_measurement(current_state, measurement)
    ]

    if not new_measurements:
        latest_measurement = measurements[-1]
        LOGGER.info(
            "No new measurement. Latest Wyze record %s was already uploaded.",
            latest_measurement.measurement_id,
        )
        return 0

    for measurement in new_measurements:
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

    if len(new_measurements) > 1:
        LOGGER.info(
            "Uploaded %s missing Wyze measurements through %s.",
            len(new_measurements),
            new_measurements[-1].measured_at.isoformat(),
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
def _state_measurement_time(settings_state: SyncState | None) -> datetime | None:
    if settings_state is None:
        return None

    measurement_epoch_ms = settings_state["last_measurement_epoch_ms"]
    return datetime.fromtimestamp(measurement_epoch_ms / 1000, tz=UTC)
