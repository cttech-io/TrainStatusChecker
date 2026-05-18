#!/usr/bin/env bash

# --- Configuration ---
# Set these environment variables in your shell or .env file
# DISCORD_WEBHOOK_URL: Your Discord Webhook URL
# TRAIN_OPERATORS: Comma-separated list of operators (e.g., "Stansted Express,Cambridge")

URL="https://www.nationalrail.co.uk/status-and-disruptions/?mode=train-operator-status"

# --- Validation ---
if [[ -z "$DISCORD_WEBHOOK_URL" ]]; then
  echo "Error: DISCORD_WEBHOOK_URL environment variable is not set."
  exit 1
fi

if [[ -z "$TRAIN_OPERATORS" ]]; then
  echo "Warning: TRAIN_OPERATORS environment variable is not set. Using defaults: Stansted Express,Cambridge"
  TRAIN_OPERATORS="Stansted Express,Cambridge"
fi

# Check for dependencies
for cmd in curl jq; do
  if ! command -v "$cmd" &> /dev/null; then
    echo "Error: $cmd is not installed."
    exit 1
  fi
done

# Convert comma-separated operators into an array
IFS=',' read -ra OPERATORS <<< "$TRAIN_OPERATORS"

# --- Execution ---
echo "Fetching webpage content..."
HTML=$(curl -sf "$URL") || { echo "Error fetching webpage: $URL"; exit 1; }

if [[ -z "$HTML" ]]; then
  echo "Error: Empty response from $URL"
  exit 1
fi

DISRUPTIONS=""

for operator in "${OPERATORS[@]}"; do
  # Trim leading/trailing whitespace
  operator=$(printf '%s' "$operator" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

  echo "Checking status for: $operator"

  # grep -iF uses fixed-string matching so operator name is never treated as a regex.
  # sed then extracts from "incident: ..." up to the closing quote without embedding
  # the operator in the regex, avoiding issues with special characters in names.
  OPERATOR_DISRUPTIONS=$(printf '%s\n' "$HTML" | grep -iF "incident: $operator" | sed -n 's/.*\(incident: [^"]*\)".*/\1/p' | sed 's/incident/INCIDENT/')

  if [[ -n "$OPERATOR_DISRUPTIONS" ]]; then
    if [[ -n "$DISRUPTIONS" ]]; then
      DISRUPTIONS="${DISRUPTIONS}"$'\n'"${OPERATOR_DISRUPTIONS}"
    else
      DISRUPTIONS="$OPERATOR_DISRUPTIONS"
    fi
  fi
done

if [[ -n "$DISRUPTIONS" ]]; then
  echo "Disruptions found! Sending Discord Embed..."

  TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # Color 15158332 is a shade of red
  PAYLOAD=$(jq -n \
    --arg content "$DISRUPTIONS" \
    --arg title "⚠️ Train Service Alert" \
    --arg timestamp "$TIMESTAMP" \
    --arg url "$URL" \
    '{
      embeds: [{
        title: $title,
        description: $content,
        url: $url,
        color: 15158332,
        timestamp: $timestamp,
        footer: {
          text: "National Rail Status Monitor"
        }
      }]
    }')

  CURL_RESULT=$(curl -s -o /dev/null -w "%{http_code}" -H "Content-Type: application/json" -d "$PAYLOAD" "$DISCORD_WEBHOOK_URL")

  if [[ $CURL_RESULT -ne 200 && $CURL_RESULT -ne 204 ]]; then
    echo "Error sending Discord webhook. HTTP Status: $CURL_RESULT"
    exit 1
  else
    echo "Discord notification sent successfully."
  fi
else
  echo "No disruptions found for monitored operators."
  if [[ "$NOTIFY_ALWAYS" == "true" ]]; then
    echo "Manual run: sending all-clear notification..."
    TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    PAYLOAD=$(jq -n \
      --arg title "✅ No Train Disruptions" \
      --arg desc "All monitored operators are running normally." \
      --arg timestamp "$TIMESTAMP" \
      --arg url "$URL" \
      '{
        embeds: [{
          title: $title,
          description: $desc,
          url: $url,
          color: 3066993,
          timestamp: $timestamp,
          footer: {
            text: "National Rail Status Monitor"
          }
        }]
      }')
    CURL_RESULT=$(curl -s -o /dev/null -w "%{http_code}" -H "Content-Type: application/json" -d "$PAYLOAD" "$DISCORD_WEBHOOK_URL")
    if [[ $CURL_RESULT -ne 200 && $CURL_RESULT -ne 204 ]]; then
      echo "Error sending Discord webhook. HTTP Status: $CURL_RESULT"
      exit 1
    else
      echo "Discord all-clear notification sent successfully."
    fi
  fi
fi
