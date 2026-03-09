# Wyze Garmin Weight Sync

This repository contains a small Python CLI that syncs missing measurements
from a Wyze scale into Garmin Connect. It is designed to run daily from a
GitHub Actions cron job, while avoiding real Wyze and Garmin usernames and
passwords in GitHub secrets during normal operation.

The sync flow takes inspiration from
[`svanhoutte/wyze_garmin_sync`](https://github.com/svanhoutte/wyze_garmin_sync):
it reads recent Wyze scale records, converts any missing ones into Garmin FIT
weight files, and uploads them to Garmin Connect.

## Tooling

- `mise` manages the project toolchain.
- `uv` manages Python dependencies and the virtual environment.
- `ruff` handles formatting and standard linting.
- `mypy` runs strict type checking.

## Repository Layout

- `src/wyze_garmin_weight_sync/` contains the typed CLI and sync logic.
- `.github/workflows/ci.yml` runs linting and type checks.
- `.github/workflows/sync.yml` runs the daily sync job.
- `.sync-state/state.json` stores the last uploaded measurement id. In GitHub
  Actions, only this non-secret state is cached between runs.

## Local Setup

```bash
mise install
uv sync --all-groups
uv run ruff check .
uv run mypy src
```

## Authentication Model

For normal scheduled GitHub Actions runs, the workflow is built around tokens:

- Garmin uses `GARMIN_TOKEN`, which is a serialized `garth` token bundle.
- Wyze CI only needs `WYZE_REFRESH_TOKEN`.

That means GitHub Actions does not need your real Garmin or Wyze password for
the day-to-day sync.

### Important Caveat

This is "passwordless in GitHub Actions", not "credential-free forever".
Tokens can expire or rotate. If that happens, refresh the secrets by running the
bootstrap commands locally again.

## Bootstrap Tokens Locally

### Garmin

Run this on your machine:

```bash
uv run wyze-garmin-weight-sync bootstrap-garmin
```

The command prompts for your Garmin credentials and prints a value like:

```text
GARMIN_TOKEN=<base64-token>
```

Save the printed token as the GitHub Actions secret `GARMIN_TOKEN`.

### Wyze

You need your Wyze developer API key id and API key from the Wyze developer
portal, plus your normal Wyze login once on your own machine:

```bash
uv run wyze-garmin-weight-sync bootstrap-wyze
```

The command prints JSON that contains:

- `WYZE_ACCESS_TOKEN`
- `WYZE_REFRESH_TOKEN`
- `WYZE_KEY_ID`
- `WYZE_API_KEY`

For GitHub Actions, the only Wyze secret you need to save is
`WYZE_REFRESH_TOKEN`. Keep the other printed values available for local use or
future troubleshooting if needed.

## Running Locally

Once your environment variables are set, run:

```bash
uv run wyze-garmin-weight-sync sync
```

Optional environment variables:

- `WYZE_SCALE_MAC`: required only if your Wyze account has more than one scale.
- `GARMIN_EMAIL` and `GARMIN_PASSWORD`: local fallback if you do not want to use
  a Garmin token.
- `WYZE_EMAIL` and `WYZE_PASSWORD`: local fallback if you do not want to use
  Wyze tokens.

## GitHub Actions Secrets

The workflow expects these secrets:

- `GARMIN_TOKEN`
- `WYZE_REFRESH_TOKEN`

Optional repository variable:

- `WYZE_SCALE_MAC`

## GitHub Actions State

The scheduled job caches `.sync-state/state.json` so the workflow can avoid
re-uploading the same Wyze measurement on every daily run.

The workflow intentionally does not cache refreshed access tokens, because
GitHub cache storage is not the right place for long-lived secrets.

## Commands

```bash
mise run format
mise run lint
mise run typecheck
mise run check
```

## Disclaimer

This repository was one-shotted by an AI agent started with the following prompt:

```
I want to write a Python script that will be runs daily through a Github Actions CRON job and syncs the data measured by my Wyze scale to Garmin connect

if possible, I do not want the Github Actions secrets to include my real Garmin Connect and Wyze credentials (but they may include real access tokens for these services)

make sure the repository uses the following tools:
- mise to manage tools
- uv for Python dependencies
- ruff for codestyle + standard linting rules
- mypy for type checking (make sure the code uses the most specific types possible, eg TypedDict instead of dict)

take inspiration from the Python code of this repository for the logic:
https://github.com/svanhoutte/wyze_garmin_sync
```
