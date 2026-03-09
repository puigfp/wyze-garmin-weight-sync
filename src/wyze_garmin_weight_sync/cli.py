from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .config import SyncSettings
from .garmin import GARMIN_TOKEN_SECRET_NAME, bootstrap_garmin_token
from .sync import run_sync
from .wyze import (
    WYZE_ACCESS_TOKEN_SECRET_NAME,
    WYZE_API_KEY_SECRET_NAME,
    WYZE_KEY_ID_SECRET_NAME,
    WYZE_REFRESH_TOKEN_SECRET_NAME,
    bootstrap_wyze_tokens,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wyze-garmin-weight-sync",
        description="Sync the latest Wyze scale measurement to Garmin Connect.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser(
        "sync",
        help="Upload the latest Wyze scale measurement to Garmin Connect.",
    )
    sync_parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path(".sync-state"),
        help="Directory that stores the last uploaded measurement state.",
    )

    garmin_parser = subparsers.add_parser(
        "bootstrap-garmin",
        help="Create a Garmin token suitable for the GARMIN_TOKEN secret.",
    )
    garmin_parser.add_argument("--email", help="Garmin email address.")
    garmin_parser.add_argument(
        "--password",
        help="Garmin password. If omitted, the command prompts for it.",
    )

    wyze_parser = subparsers.add_parser(
        "bootstrap-wyze",
        help="Create Wyze access and refresh tokens from account credentials.",
    )
    wyze_parser.add_argument("--email", help="Wyze email address.")
    wyze_parser.add_argument(
        "--password",
        help="Wyze password. If omitted, the command prompts for it.",
    )
    wyze_parser.add_argument(
        "--key-id",
        help="Wyze developer API key ID. If omitted, the command prompts for it.",
    )
    wyze_parser.add_argument(
        "--api-key",
        help="Wyze developer API key. If omitted, the command prompts for it.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    if args.command == "sync":
        settings = SyncSettings.from_env(args.state_dir)
        return run_sync(settings)

    if args.command == "bootstrap-garmin":
        token = bootstrap_garmin_token(email=args.email, password=args.password)
        print(f"{GARMIN_TOKEN_SECRET_NAME}={token}")
        return 0

    if args.command == "bootstrap-wyze":
        access_token, refresh_token, key_id, api_key = bootstrap_wyze_tokens(
            email=args.email,
            password=args.password,
            key_id=args.key_id,
            api_key=args.api_key,
        )
        payload = {
            WYZE_ACCESS_TOKEN_SECRET_NAME: access_token,
            WYZE_REFRESH_TOKEN_SECRET_NAME: refresh_token,
            WYZE_KEY_ID_SECRET_NAME: key_id,
            WYZE_API_KEY_SECRET_NAME: api_key,
        }
        print(json.dumps(payload, indent=2))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
