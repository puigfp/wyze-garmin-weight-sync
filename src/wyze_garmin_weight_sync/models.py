from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import NotRequired, TypedDict

POUNDS_TO_KILOGRAMS = 0.45359237


@dataclass(frozen=True, slots=True)
class WyzeMeasurement:
    measurement_id: str
    measured_at: datetime
    weight_kg: float
    percent_fat: float | None
    percent_hydration: float | None
    visceral_fat_mass: float | None
    visceral_fat_rating: int | None
    bone_mass_kg: float | None
    muscle_mass_kg: float | None
    basal_met: float | None
    active_met: int | None
    physique_rating: int
    metabolic_age: int | None
    bmi: float | None

    @property
    def measured_at_epoch_ms(self) -> int:
        return int(self.measured_at.timestamp() * 1000)


class WyzeLoginResponse(TypedDict):
    access_token: str
    refresh_token: str
    user_id: str


class WyzeRefreshPayload(TypedDict):
    access_token: str
    refresh_token: str


class WyzeRefreshResponse(TypedDict):
    data: WyzeRefreshPayload


class SyncState(TypedDict):
    last_measurement_id: str
    last_measurement_epoch_ms: int
    last_uploaded_at: str
    last_uploaded_weight_kg: float
    last_uploaded_source: NotRequired[str]


@dataclass(frozen=True, slots=True)
class GarminUploadResult:
    source: str
    measurement: WyzeMeasurement


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
