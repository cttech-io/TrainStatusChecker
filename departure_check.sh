#!/usr/bin/env bash

# --- Configuration ---
# DISCORD_WEBHOOK_URL:  Your Discord Webhook URL
# RTT_REFRESH_TOKEN:    Realtime Trains long-lived token (from api-portal.rtt.io)
# FROM_CRS:             Departure station CRS code (e.g. LST)
# TO_CRS:               Destination station CRS code (e.g. BIS)
# FROM_NAME:            Human-readable departure station name (optional, falls back to CRS)
# TO_NAME:              Human-readable destination name (optional, falls back to CRS)

RTT_BASE="https://data.rtt.io"

# --- Validation ---
for var in DISCORD_WEBHOOK_URL RTT_REFRESH_TOKEN FROM_CRS TO_CRS; do
  if [[ -z "${!var}" ]]; then
    echo "Error: $var is not set."
    exit 1
  fi
done

for cmd in curl jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Error: $cmd is not installed."
    exit 1
  fi
done

FROM_CRS=$(echo "$FROM_CRS" | tr '[:lower:]' '[:upper:]')
TO_CRS=$(echo "$TO_CRS" | tr '[:lower:]' '[:upper:]')
FROM_NAME="${FROM_NAME:-$FROM_CRS}"
TO_NAME="${TO_NAME:-$TO_CRS}"

# --- Exchange refresh token for short-lived access token ---
echo "Obtaining API access token..."
ACCESS_TOKEN=$(curl -sf \
  -H "Authorization: Bearer $RTT_REFRESH_TOKEN" \
  "$RTT_BASE/api/get_access_token" | jq -r '.token')

if [[ -z "$ACCESS_TOKEN" || "$ACCESS_TOKEN" == "null" ]]; then
  echo "Error: Failed to obtain access token. Check RTT_REFRESH_TOKEN."
  exit 1
fi

# --- Fetch departures ---
echo "Fetching departures: $FROM_NAME ($FROM_CRS) → $TO_NAME ($TO_CRS)..."

RESPONSE=$(curl -sf \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$RTT_BASE/gb-nr/location?code=$FROM_CRS&filterTo=$TO_CRS") || {
  echo "Error: Failed to fetch departure data."
  exit 1
}

if [[ -z "$RESPONSE" ]]; then
  echo "Error: Empty response from API."
  exit 1
fi

SERVICE_COUNT=$(echo "$RESPONSE" | jq '.services | length')
if [[ "$SERVICE_COUNT" -eq 0 || "$SERVICE_COUNT" == "null" ]]; then
  echo "No upcoming services found from $FROM_NAME to $TO_NAME."
  exit 0
fi

echo "Found $SERVICE_COUNT service(s). Building notification..."

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
FIELDS=""
COUNT=0

while IFS= read -r service_json && [[ $COUNT -lt 3 ]]; do
  identity=$(echo "$service_json" | jq -r '.scheduleMetadata.identity')
  dep_date=$(echo "$service_json" | jq -r '.scheduleMetadata.departureDate')
  sched_dep=$(echo "$service_json" | jq -r '.temporalData.departure.scheduleAdvertised')
  rt_dep=$(echo "$service_json" | jq -r '.temporalData.departure.realtimeForecast // .temporalData.departure.scheduleAdvertised')
  platform=$(echo "$service_json" | jq -r '.locationMetadata.platform.actual // .locationMetadata.platform.planned // "TBC"')

  # Slice HH:MM from ISO 8601 datetime (e.g. "2026-05-18T20:36:00" → "20:36")
  sched_fmt="${sched_dep:11:5}"
  rt_fmt="${rt_dep:11:5}"

  # Fetch full service to get the arrival time at the destination stop
  DETAIL=$(curl -sf \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    "$RTT_BASE/gb-nr/service?identity=$identity&departureDate=$dep_date") || continue

  arrival=$(echo "$DETAIL" | jq -r --arg crs "$TO_CRS" '
    (.service.locations // [])[] |
    select(.location.shortCodes[]? == $crs) |
    (.temporalData.arrival.realtimeActual
      // .temporalData.arrival.realtimeForecast
      // .temporalData.arrival.scheduleAdvertised) |
    .[11:16]
  ' | head -1)

  if [[ "$rt_fmt" != "$sched_fmt" ]]; then
    dep_label="~~${sched_fmt}~~ → ${rt_fmt}"
  else
    dep_label="$sched_fmt"
  fi

  field=$(jq -n \
    --arg name "Departs $dep_label" \
    --arg value "Platform $platform · Arrives ${arrival:-Unknown}" \
    '{"name": $name, "value": $value, "inline": true}')

  if [[ -n "$FIELDS" ]]; then
    FIELDS="$FIELDS,$field"
  else
    FIELDS="$field"
  fi

  COUNT=$((COUNT + 1))
done < <(echo "$RESPONSE" | jq -c '.services[]')

if [[ $COUNT -eq 0 ]]; then
  echo "Error: Could not retrieve details for any services."
  exit 1
fi

PAYLOAD=$(jq -n \
  --arg title "🚂 $FROM_NAME → $TO_NAME" \
  --arg timestamp "$TIMESTAMP" \
  --argjson fields "[$FIELDS]" \
  '{
    embeds: [{
      title: $title,
      color: 3447003,
      fields: $fields,
      timestamp: $timestamp,
      footer: { text: "National Rail · Realtime Trains" }
    }]
  }')

CURL_RESULT=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "$DISCORD_WEBHOOK_URL")

if [[ $CURL_RESULT -ne 200 && $CURL_RESULT -ne 204 ]]; then
  echo "Error sending Discord notification. HTTP Status: $CURL_RESULT"
  exit 1
fi

echo "Discord notification sent ($COUNT train(s) shown)."
