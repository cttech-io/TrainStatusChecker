# TrainStatusChecker

A simple Bash script to monitor National Rail train operator status and send notifications to Discord when disruptions are found.

## Features
- Monitors specific train operators for disruptions.
- Sends professional **Discord Rich Embeds** (colored sidebars, timestamps, and links).
- Configurable via environment variables (no hardcoded secrets).
- Dependency checks for `curl` and `jq`.

## Prerequisites
- `curl`
- `jq` (for JSON processing)

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/cttech-io/TrainStatusChecker.git
   cd TrainStatusChecker
   ```
2. Make the script executable:
   ```bash
   chmod +x train_status.sh
   ```

## Configuration
The script uses environment variables for configuration. You can export them in your shell or add them to your crontab.

| Variable | Description | Example |
|----------|-------------|---------|
| `DISCORD_WEBHOOK_URL` | Your Discord Webhook URL | `https://discord.com/api/webhooks/...` |
| `TRAIN_OPERATORS` | Comma-separated list of operators to monitor | `Stansted Express,Cambridge` |

## Usage
Run the script manually:
```bash
export DISCORD_WEBHOOK_URL="your_url"
export TRAIN_OPERATORS="Stansted Express,Cambridge"
./train_status.sh
```

### Automation (Cron)
To run the script every 30 minutes, add the following to your `crontab -e`:
```cron
*/30 * * * * DISCORD_WEBHOOK_URL="your_url" TRAIN_OPERATORS="Stansted Express,Cambridge" /path/to/train_status.sh
```

## Security Note
**Never** commit your `DISCORD_WEBHOOK_URL` to public repositories. If you have previously committed a webhook URL, delete it in Discord and create a new one.
