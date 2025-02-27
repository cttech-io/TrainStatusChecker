#!/bin/bash

# URL of the train service status page
url="https://www.nationalrail.co.uk/status-and-disruptions/?mode=train-operator-status"

# Train operators to monitor
train_operators=("Stansted Express" "Cambridge" "Avanti West Coast")

# Discord Webhook URL
discord_webhook_url="https://discord.com/api/webhooks/1319241840800829531/dDPRC9epL3AkTSN8-yqraWtqwTw83Dnz85x165rNpDRcERHMJB-CSzuMpFNEJommxdmE"

# Fetch the webpage content
html=$(curl -s "$url")

# Check if the request was successful
if [[ $? -ne 0 ]]; then
  echo "Error fetching webpage: $url"
  exit 1
fi

disruptions=""

# Loop through train operators and extract disruptions
for operator in "${train_operators[@]}"; do
  operator_disruptions=$(echo "$html" | grep "incident: $operator" | sed -n 's/.*\(incident: '"$operator"'[^"]*\)".*/\1/p' | sed 's/incident/INCIDENT/') # Added sed command
  if [[ -n "$operator_disruptions" ]]; then
    if [[ -n "$disruptions" ]]; then
      disruptions="$disruptions\n$operator_disruptions"
    else
      disruptions="$operator_disruptions"
    fi
  fi
done

# Check if any disruptions were found
if [[ -n "$disruptions" ]]; then
  # Format the payload for Discord
  payload=$(jq -n --arg content "$disruptions" '{content: $content}')

  # Send the payload to the Discord webhook
  curl -H "Content-Type: application/json" -d "$payload" "$discord_webhook_url"

  # Check if the Discord webhook request was successful
  if [[ $? -ne 0 ]]; then
    echo "Error sending Discord webhook."
  fi

else
  echo "No disruptions found."
fi