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
  echo "Warning: TRAIN_OPERATORS environment variable is not set. Using defaults: Stansted Express, Cambridge"
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
HTML=$(curl -s "$URL")

if [[ $? -ne 0 ]]; then
  echo "Error fetching webpage: $URL"
  exit 1
fi

DISRUPTIONS=""

for operator in "${OPERATORS[@]}"; do
  # Trim whitespace
  operator=$(echo "$operator" | xargs)
  
  echo "Checking status for: $operator"
  # Extract disruptions from the HTML
  OPERATOR_DISRUPTIONS=$(echo "$HTML" | grep -i "incident: $operator" | sed -n 's/.*\(incident: '"$operator"'[^"]*\)".*/\1/p' | sed 's/incident/INCIDENT/')

  if [[ -n "$OPERATOR_DISRUPTIONS" ]]; then
    if [[ -n "$DISRUPTIONS" ]]; then
      DISRUPTIONS="$DISRUPTIONS\n$OPERATOR_DISRUPTIONS"
    else
      DISRUPTIONS="$OPERATOR_DISRUPTIONS"
    fi
  fi
done

if [[ -n "$DISRUPTIONS" ]]; then
  echo "Disruptions found! Sending Discord Embed..."
  
  # Get current timestamp in ISO8601 format
  TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  
  # Format the payload for Discord using an Embed
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
fi
