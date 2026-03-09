from __future__ import annotations

from getpass import getpass
from pathlib import Path
from typing import Final

import garth

GARMIN_TOKEN_SECRET_NAME: Final[str] = "GARMIN_TOKEN"


def bootstrap_garmin_token(
    *, email: str | None = None, password: str | None = None
) -> str:
    login_email = email or input("Garmin email: ").strip()
    login_password = password or getpass("Garmin password: ")
    garth.login(login_email, login_password)  # type: ignore[no-untyped-call]
    return garth.client.dumps()


def configure_garmin(
    *, token: str | None, email: str | None, password: str | None
) -> str:
    if token:
        garth.client.loads(token)
        return "token"

    if email and password:
        garth.login(email, password)  # type: ignore[no-untyped-call]
        return "password"

    msg = (
        "Garmin authentication is missing. Set GARMIN_TOKEN or provide "
        "GARMIN_EMAIL and GARMIN_PASSWORD."
    )
    raise ValueError(msg)


def upload_fit_file(path: Path) -> None:
    with path.open("rb") as handle:
        garth.upload(handle)
