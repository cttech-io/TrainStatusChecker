#!/bin/bash

# URL of the train service status page
url="https://www.nationalrail.co.uk/status-and-disruptions/?mode=train-operator-status"

# Train operators to monitor
train_operators=("Stansted Express" "Cambridge")

# Discord Webhook URL
discord_webhook_url="https://discord.com/api/webhooks/1353631844863709255/-LijAhwOfXvYOhGarHDWnfzZTDOb9TWnpeEzigrY3gMFS9V6qjhzN3wmzmL6tdN_pNev"

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
  operator_disruptions=$(echo "$html" | grep "incident: $operator" | sed -n 's/.*\(incident: '"$operator"'[^"]*\)".*/\1/p' | sed 's/incident/INCIDENT/')

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
curl_result=$(curl -s -o /dev/null -w "%{http_code}" -H "Content-Type: application/json" -d "$payload" "$discord_webhook_url")

# Check if the Discord webhook request was successful
if [[ $curl_result -ne 200 && $curl_result -ne 204 ]]; then #Modified line
    echo "Error sending Discord webhook. HTTP Status: $curl_result"
    echo "Payload was: $payload" #added for debugging
else
    echo "Discord webhook sent successfully."
fi
else
  echo "No disruptions found."
fi