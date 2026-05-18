# TrainStatusChecker

Two tools for National Rail, both sending results to Discord:

- **Disruption Monitor** — runs every 30 minutes via GitHub Actions and alerts when a monitored operator has a disruption
- **Departure Checker** — triggered by Home Assistant when you arrive at a station, showing the next 3 trains to your destination with platform and arrival time

---

## Prerequisites

- `curl`
- `jq`
- A Discord webhook URL

---

## Disruption Monitor (`train_status.sh`)

Polls [National Rail](https://www.nationalrail.co.uk/status-and-disruptions/) for disruptions on specified operators.

### Configuration

| Variable | Required | Description |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | Yes | Your Discord webhook URL |
| `TRAIN_OPERATORS` | No | Comma-separated operators to monitor (default: `Stansted Express,Cambridge`) |

### GitHub Actions setup

1. Go to **Settings** > **Secrets and variables** > **Actions**.
2. Under **Secrets**, add `DISCORD_WEBHOOK_URL`.
3. Under **Variables**, optionally add `TRAIN_OPERATORS`.

| Trigger | Behaviour |
|---|---|
| Scheduled (every 30 min) | Notifies only when disruptions are found |
| Manual (`workflow_dispatch`) | Always notifies — red alert if disruptions, green all-clear if none |

### Run locally

```bash
export DISCORD_WEBHOOK_URL="your_url"
export TRAIN_OPERATORS="Stansted Express,Cambridge"
bash train_status.sh
```

### Run via cron

```cron
*/30 * * * * DISCORD_WEBHOOK_URL="your_url" TRAIN_OPERATORS="Stansted Express,Cambridge" /path/to/train_status.sh
```

---

## Departure Checker (`departure_check.sh`)

When triggered, queries the [Realtime Trains API](https://api.rtt.io/) for the next 3 departures from a given station to a given destination, and sends a Discord notification showing the departure time, platform, and arrival time for each service. Delayed trains show the original scheduled time with a strikethrough.

### 1. Register for the Realtime Trains API

Sign up at [api-portal.rtt.io](https://api-portal.rtt.io/). Once registered, create a token under your account. On the token detail page, copy the **issued access token** (the long JWT string beginning with `eyJ`) — this is your refresh token.

### 2. Add GitHub secrets

Go to **Settings** > **Secrets and variables** > **Actions** and add:

| Secret | Value |
|---|---|
| `RTT_REFRESH_TOKEN` | The JWT token copied from your api-portal.rtt.io token page |

`DISCORD_WEBHOOK_URL` is shared with the disruption monitor — add it once.

### 3. Trigger manually

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

### 4. Home Assistant integration

This is the main way to trigger the departure checker automatically when you arrive at a station.

#### Create a zone for each station

In Home Assistant, go to **Settings** > **Areas & Zones** > **Zones** and add a zone for each station you commute from. Set the radius to roughly 200m.

#### Create a GitHub Personal Access Token

Go to **GitHub** > **Settings** > **Developer settings** > **Personal access tokens** > **Fine-grained tokens** and create a token scoped to this repository with **Contents: Read and Write** permission (required to trigger `repository_dispatch`).

Store it in Home Assistant as a secret (`github_pat`) or in an `input_text` helper.

#### Add a REST command

Add this to your `configuration.yaml`:

```yaml
rest_command:
  train_departure_check:
    url: "https://api.github.com/repos/cttech-io/TrainStatusChecker/dispatches"
    method: POST
    headers:
      Authorization: "Bearer YOUR_GITHUB_PAT"
      Accept: "application/vnd.github.v3+json"
    payload: >-
      {"event_type":"departure-check","client_payload":{"from_crs":"{{ from_crs }}","to_crs":"{{ to_crs }}","from_name":"{{ from_name }}","to_name":"{{ to_name }}"}}
    content_type: "application/json"
```

#### Create an automation for each station

```yaml
alias: "Trains at Liverpool Street → Bishops Stortford"
trigger:
  - platform: zone
    entity_id: device_tracker.your_phone
    zone: zone.london_liverpool_street
    event: enter
action:
  - service: rest_command.train_departure_check
    data:
      from_crs: "LST"
      to_crs: "BIS"
      from_name: "London Liverpool Street"
      to_name: "Bishops Stortford"
```

Duplicate this automation for each station/destination pair you need. The GitHub Actions job typically starts within 30–60 seconds of the trigger, so the Discord notification will arrive shortly after you reach the station.

#### iOS and Android

The Home Assistant companion app for both iOS and Android reports location to HA automatically. Ensure **Background App Refresh** (iOS) or **Background Location** (Android) is enabled for the app, and that the device tracker entity matches `device_tracker.your_phone` in the automation above.
