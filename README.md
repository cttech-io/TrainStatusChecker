# TrainStatusChecker

A Bash script that monitors National Rail train operator status and sends Discord notifications when disruptions are found.

## Features

- Monitors specific train operators for disruptions
- Sends Discord Rich Embeds — red alert on disruption, green all-clear on manual runs
- Configurable via environment variables (no hardcoded secrets)
- Dependency checks for `curl` and `jq`

## Prerequisites

- `curl`
- `jq`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/cttech-io/TrainStatusChecker.git
   cd TrainStatusChecker
   ```

## Configuration

| Variable | Required | Description | Example |
|---|---|---|---|
| `DISCORD_WEBHOOK_URL` | Yes | Your Discord webhook URL | `https://discord.com/api/webhooks/...` |
| `TRAIN_OPERATORS` | No | Comma-separated operators to monitor | `Stansted Express,Cambridge` |

If `TRAIN_OPERATORS` is not set, the script defaults to `Stansted Express,Cambridge`.

## Usage

```bash
export DISCORD_WEBHOOK_URL="your_url"
export TRAIN_OPERATORS="Stansted Express,Cambridge"
bash train_status.sh
```

## GitHub Actions

The workflow runs automatically every 30 minutes and can also be triggered manually from the Actions tab.

| Trigger | Behaviour |
|---|---|
| Scheduled (every 30 min) | Sends a notification only when disruptions are found |
| Manual (`workflow_dispatch`) | Always sends a notification — red alert if disruptions, green all-clear if none |

### Setup

1. Go to **Settings** > **Secrets and variables** > **Actions** in your repository.
2. Under **Secrets**, add `DISCORD_WEBHOOK_URL` with your Discord webhook URL.
3. Under **Variables**, optionally add `TRAIN_OPERATORS` with a comma-separated list of operators. If omitted, the default (`Stansted Express,Cambridge`) is used.

To trigger a manual run, go to **Actions** > **Monitor Train Status** > **Run workflow**.

### Running locally with cron

```cron
*/30 * * * * DISCORD_WEBHOOK_URL="your_url" TRAIN_OPERATORS="Stansted Express,Cambridge" /path/to/train_status.sh
```
