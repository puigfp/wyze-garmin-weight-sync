from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from getpass import getpass
from typing import Final, cast

from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError

from .models import (
    POUNDS_TO_KILOGRAMS,
    WyzeLoginResponse,
    WyzeMeasurement,
    WyzeRefreshResponse,
    ensure_utc,
)

WYZE_ACCESS_TOKEN_SECRET_NAME: Final[str] = "WYZE_ACCESS_TOKEN"
WYZE_REFRESH_TOKEN_SECRET_NAME: Final[str] = "WYZE_REFRESH_TOKEN"
WYZE_KEY_ID_SECRET_NAME: Final[str] = "WYZE_KEY_ID"
WYZE_API_KEY_SECRET_NAME: Final[str] = "WYZE_API_KEY"


@dataclass(frozen=True, slots=True)
class WyzeSession:
    client: Client
    auth_source: str
    access_token: str | None
    refresh_token: str | None


def bootstrap_wyze_tokens(
    *,
    email: str | None = None,
    password: str | None = None,
    key_id: str | None = None,
    api_key: str | None = None,
) -> tuple[str, str, str, str]:
    login_email = email or input("Wyze email: ").strip()
    login_password = password or getpass("Wyze password: ")
    login_key_id = key_id or input("Wyze API key ID: ").strip()
    login_api_key = api_key or getpass("Wyze API key: ")

    response = cast(
        WyzeLoginResponse,
        Client().login(
            email=login_email,
            password=login_password,
            key_id=login_key_id,
            api_key=login_api_key,
        ),
    )
    return (
        response["access_token"],
        response["refresh_token"],
        login_key_id,
        login_api_key,
    )


def authenticate_wyze(
    *,
    access_token: str | None,
    refresh_token: str | None,
    email: str | None,
    password: str | None,
    key_id: str | None,
    api_key: str | None,
) -> WyzeSession:
    if access_token:
        client = Client(token=access_token, refresh_token=refresh_token)
        if _is_session_valid(client):
            return WyzeSession(
                client=client,
                auth_source="access_token",
                access_token=access_token,
                refresh_token=refresh_token,
            )

    if refresh_token:
        client = Client(refresh_token=refresh_token)
        refresh_response = cast(WyzeRefreshResponse, client.refresh_token())
        refreshed = refresh_response["data"]
        if _is_session_valid(client):
            return WyzeSession(
                client=client,
                auth_source="refresh_token",
                access_token=refreshed["access_token"],
                refresh_token=refreshed["refresh_token"],
            )

    if email and password and key_id and api_key:
        client = Client()
        login_response = cast(
            WyzeLoginResponse,
            client.login(
                email=email,
                password=password,
                key_id=key_id,
                api_key=api_key,
            ),
        )
        return WyzeSession(
            client=client,
            auth_source="password",
            access_token=login_response["access_token"],
            refresh_token=login_response["refresh_token"],
        )

    msg = (
        "Wyze authentication is missing or invalid. Set WYZE_ACCESS_TOKEN or "
        "WYZE_REFRESH_TOKEN, or provide WYZE_EMAIL, WYZE_PASSWORD, "
        "WYZE_KEY_ID, and WYZE_API_KEY."
    )
    raise ValueError(msg)


def fetch_latest_measurement(
    client: Client, *, device_mac: str | None = None
) -> WyzeMeasurement:
    scale_mac = device_mac or _select_scale_mac(client.devices_list())
    scale = client.scales.info(device_mac=scale_mac)
    if scale is None:
        raise RuntimeError(f"Wyze scale {scale_mac} was not found")

    latest_records = getattr(scale, "latest_records", None)
    if not latest_records:
        raise RuntimeError(f"Wyze scale {scale_mac} has no recent measurements")

    record = latest_records[0]
    return _measurement_from_record(record)


def _is_session_valid(client: Client) -> bool:
    try:
        client.devices_list()
    except WyzeApiError:
        return False
    return True


def _select_scale_mac(devices: Sequence[object]) -> str:
    scale_macs = [
        _require_str_attr(device, "mac")
        for device in devices
        if _string_attr(device, "type") == "WyzeScale"
    ]
    if len(scale_macs) == 1:
        return scale_macs[0]
    if not scale_macs:
        raise RuntimeError("No Wyze scale devices were found on this account")
    msg = (
        "Multiple Wyze scales were found. Set WYZE_SCALE_MAC to the device "
        f"you want to sync: {', '.join(scale_macs)}"
    )
    raise RuntimeError(msg)


def _measurement_from_record(record: object) -> WyzeMeasurement:
    measure_ts = _require_int_attr(record, "measure_ts")
    basal_met = _optional_float_attr(record, "bmr")
    visceral_fat_value = _optional_float_attr(record, "body_vfr")
    visceral_fat_rating = (
        int(round(visceral_fat_value)) if visceral_fat_value is not None else None
    )
    active_met = int(round(basal_met * 1.25)) if basal_met is not None else None
    measured_at = ensure_utc(datetime.fromtimestamp(measure_ts / 1000))

    return WyzeMeasurement(
        measurement_id=_measurement_id(record, measure_ts),
        measured_at=measured_at,
        weight_kg=_require_float_attr(record, "weight") * POUNDS_TO_KILOGRAMS,
        percent_fat=_optional_float_attr(record, "body_fat"),
        percent_hydration=_optional_float_attr(record, "body_water"),
        visceral_fat_mass=visceral_fat_value,
        visceral_fat_rating=visceral_fat_rating,
        bone_mass_kg=_optional_float_attr(record, "bone_mineral"),
        muscle_mass_kg=_optional_float_attr(record, "muscle"),
        basal_met=basal_met,
        active_met=active_met,
        physique_rating=_optional_int_attr(record, "body_type") or 5,
        metabolic_age=_optional_int_attr(record, "metabolic_age"),
        bmi=_optional_float_attr(record, "bmi"),
    )


def _measurement_id(record: object, measure_ts: int) -> str:
    record_id = _string_attr(record, "id")
    if record_id:
        return record_id
    return str(measure_ts)


def _string_attr(value: object, name: str) -> str | None:
    attr = getattr(value, name, None)
    if attr is None:
        return None
    if not isinstance(attr, str):
        return str(attr)
    stripped = attr.strip()
    return stripped or None


def _require_str_attr(value: object, name: str) -> str:
    result = _string_attr(value, name)
    if result is None:
        raise TypeError(f"{name} is missing or empty")
    return result


def _require_int_attr(value: object, name: str) -> int:
    attr = getattr(value, name, None)
    if isinstance(attr, bool):
        raise TypeError(f"{name} must be an integer")
    if isinstance(attr, int):
        return attr
    if isinstance(attr, float):
        return int(attr)
    if isinstance(attr, str) and attr.strip():
        return int(attr)
    raise TypeError(f"{name} is missing")


def _optional_int_attr(value: object, name: str) -> int | None:
    attr = getattr(value, name, None)
    if attr is None:
        return None
    if isinstance(attr, bool):
        raise TypeError(f"{name} must be an integer")
    if isinstance(attr, int):
        return attr
    if isinstance(attr, float):
        return int(attr)
    if isinstance(attr, str) and attr.strip():
        return int(attr)
    return None


def _require_float_attr(value: object, name: str) -> float:
    result = _optional_float_attr(value, name)
    if result is None:
        raise TypeError(f"{name} is missing")
    return result


def _optional_float_attr(value: object, name: str) -> float | None:
    attr = getattr(value, name, None)
    if attr is None:
        return None
    if isinstance(attr, bool):
        raise TypeError(f"{name} must be numeric")
    if isinstance(attr, (int, float)):
        return float(attr)
    if isinstance(attr, str) and attr.strip():
        return float(attr)
    return None
