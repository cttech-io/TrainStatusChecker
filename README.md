# TrainStatusChecker

Two tools for National Rail, both sending results to Discord:

- **Disruption Monitor** — runs every 30 minutes via GitHub Actions and alerts when there is a disruption or cancellation on your commute route
- **Departure Checker** — triggered by Home Assistant when you arrive at a station, showing the next 3 trains to your destination with platform and arrival time

---

## Prerequisites

- Python 3
- `pip install -r requirements.txt` (`requests`)
- A Discord webhook URL

---

## Disruption Monitor (`train_status.py`)

Two checks run on every execution:

1. **RTT API** — detects formally cancelled or delayed (≥5 min) services on the configured routes
2. **National Rail status page** — detects active unplanned incidents for the configured operators, filtered to only those relevant to your route. On each run, the calling points of the next live service are fetched from RTT to build the station list dynamically. An NR alert is included if it either mentions a station on your route, or contains no specific station reference (e.g. a general hot weather advisory). Disruptions affecting stations elsewhere on the same operator are silently skipped.

To avoid notification fatigue, results are diffed against the previous run's state. A notification is only sent when something changes — a new disruption appears, an existing one is updated, or one is cleared. Runs where nothing has changed are silent. State is persisted between runs using the GitHub Actions cache (`state.json`). The cache has a 7-day TTL; if it is evicted, the next run treats all active disruptions as new.

### Configuration

| Variable | Required | Description |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | Yes | Your Discord webhook URL |
| `RTT_REFRESH_TOKEN` | Yes | JWT token from [api-portal.rtt.io](https://api-portal.rtt.io/) |
| `ROUTES` | No | Comma-separated `FROM:TO` CRS pairs to check for delays/cancellations (default: `LST:BIS`) |
| `OPERATOR_CODES` | No | Comma-separated National Rail operator codes to watch for incidents (default: `LE,SX` — Greater Anglia and Stansted Express) |
| `DELAY_THRESHOLD_MINS` | No | Minutes late before a delay is reported (default: `5`) |

### GitHub Actions setup

1. Go to **Settings** > **Secrets and variables** > **Actions**.
2. Under **Secrets**, add `DISCORD_WEBHOOK_URL` and `RTT_REFRESH_TOKEN`.
3. Under **Variables**, optionally add `ROUTES` and `OPERATOR_CODES`.

| Trigger | Behaviour |
|---|---|
| Scheduled (every 30 min) | Notifies only when something has changed since the last run (new, updated, or cleared disruption) |
| Manual (`workflow_dispatch`) | Always notifies — shows full current state regardless of previous run; updates the state cache |

### Run locally

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="your_url"
export RTT_REFRESH_TOKEN="your_jwt"
export ROUTES="LST:BIS"
export OPERATOR_CODES="LE,SX"
python3 train_status.py
```

### Run via cron

```cron
*/30 * * * * DISCORD_WEBHOOK_URL="your_url" RTT_REFRESH_TOKEN="your_jwt" ROUTES="LST:BIS" OPERATOR_CODES="LE,SX" /path/to/.venv/bin/python3 /path/to/train_status.py
```

---

## Departure Checker (`departure_check.py`)

When triggered, queries the [Realtime Trains API](https://api-portal.rtt.io/) for the next 3 departures from a given station to a given destination, and sends a Discord notification showing the departure time, platform, and arrival time for each service. Delayed trains show the original scheduled time with a strikethrough.

### 1. Register for the Realtime Trains API

Sign up at [api-portal.rtt.io](https://api-portal.rtt.io/). Once registered, create a token under your account. On the token detail page, copy the **issued access token** (the long JWT string beginning with `eyJ`) — this is your refresh token.

### 2. Add GitHub secrets

Go to **Settings** > **Secrets and variables** > **Actions** and add:

| Secret | Value |
|---|---|
| `RTT_REFRESH_TOKEN` | The JWT token copied from your api-portal.rtt.io token page |

`DISCORD_WEBHOOK_URL` is shared with the disruption monitor — add it once.

### 3. Run locally

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL="your_url"
export RTT_REFRESH_TOKEN="your_jwt"
export FROM_CRS="LST"
export TO_CRS="BIS"
export FROM_NAME="London Liverpool Street"
export TO_NAME="Bishops Stortford"
python3 departure_check.py
```

### 4. Trigger manually via GitHub Actions

Go to **Actions** > **Departure Check** > **Run workflow** and fill in the station CRS codes. Use this to test before setting up Home Assistant.

Common CRS codes:

| Station | CRS |
|---|---|
| London Liverpool Street | `LST` |
| Bishops Stortford | `BIS` |
| Cambridge | `CBG` |
| Stansted Airport | `SSD` |
| Tottenham Hale | `TOM` |
| Stratford | `SRA` |

A full list is available at [nationalrail.co.uk/stations](https://www.nationalrail.co.uk/stations/).

### 5. Home Assistant integration

This is the main way to trigger the departure checker automatically when you arrive at a station.

#### Create a zone for each station

In Home Assistant, go to **Settings** > **Areas & Zones** > **Zones** and add a zone for each station you commute from. Set the radius to roughly 200m.

#### Create a GitHub Personal Access Token

Go to **GitHub** > **Settings** > **Developer settings** > **Personal access tokens** > **Fine-grained tokens** and create a token scoped to this repository with **Contents: Read and Write** permission (required to trigger `repository_dispatch`).

#### Add a REST command

Add your GitHub PAT to Home Assistant's `secrets.yaml` (never put tokens directly in `configuration.yaml`):

```yaml
# secrets.yaml
github_pat: YOUR_GITHUB_PAT
```

Then add this to `configuration.yaml`:

```yaml
rest_command:
  train_departure_check:
    url: "https://api.github.com/repos/cttech-io/TrainStatusChecker/dispatches"
    method: POST
    headers:
      Authorization: "Bearer !secret github_pat"
      Accept: "application/vnd.github.v3+json"
    payload: >-
      {"event_type":"departure-check","client_payload":{"from_crs":"{{ from_crs }}","to_crs":"{{ to_crs }}","from_name":"{{ from_name }}","to_name":"{{ to_name }}"}}
    content_type: "application/json"
```

#### Create an automation for each station

Add entries like this to your `automations.yaml`:

```yaml
- id: '1749999999999'
  alias: "Trains at Liverpool Street → Bishops Stortford"
  triggers:
  - trigger: zone
    entity_id: device_tracker.your_phone
    zone: zone.london_liverpool_street
    event: enter
  conditions: []
  actions:
  - action: rest_command.train_departure_check
    data:
      from_crs: "LST"
      to_crs: "BIS"
      from_name: "London Liverpool Street"
      to_name: "Bishops Stortford"
  mode: single
```

Duplicate for each station/destination pair. The GitHub Actions job typically starts within 30–60 seconds of the trigger, so the Discord notification arrives shortly after you reach the station.

#### iOS and Android

The Home Assistant companion app for both iOS and Android reports location automatically. Ensure **Background App Refresh** (iOS) or **Background Location** (Android) is enabled, and that the device tracker entity matches `device_tracker.your_phone` in the automation above.
