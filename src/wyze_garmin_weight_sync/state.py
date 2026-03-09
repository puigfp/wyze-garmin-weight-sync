from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .models import SyncState, WyzeMeasurement


def load_state(state_path: Path) -> SyncState | None:
    if not state_path.exists():
        return None

    raw = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a JSON object in {state_path}")

    required_keys = {
        "last_measurement_id",
        "last_measurement_epoch_ms",
        "last_uploaded_at",
        "last_uploaded_weight_kg",
    }
    if not required_keys.issubset(raw):
        raise ValueError(f"State file {state_path} is missing required keys")

    return {
        "last_measurement_id": str(raw["last_measurement_id"]),
        "last_measurement_epoch_ms": int(raw["last_measurement_epoch_ms"]),
        "last_uploaded_at": str(raw["last_uploaded_at"]),
        "last_uploaded_weight_kg": float(raw["last_uploaded_weight_kg"]),
        "last_uploaded_source": str(raw["last_uploaded_source"])
        if "last_uploaded_source" in raw
        else "wyze",
    }


def save_state(
    state_path: Path, measurement: WyzeMeasurement, *, source: str = "wyze"
) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload: SyncState = {
        "last_measurement_id": measurement.measurement_id,
        "last_measurement_epoch_ms": measurement.measured_at_epoch_ms,
        "last_uploaded_at": datetime.now(UTC).isoformat(),
        "last_uploaded_weight_kg": measurement.weight_kg,
        "last_uploaded_source": source,
    }
    state_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def is_new_measurement(state: SyncState | None, measurement: WyzeMeasurement) -> bool:
    if state is None:
        return True

    if measurement.measured_at_epoch_ms > state["last_measurement_epoch_ms"]:
        return True
    if measurement.measured_at_epoch_ms < state["last_measurement_epoch_ms"]:
        return False
    return state["last_measurement_id"] != measurement.measurement_id
