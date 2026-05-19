#!/usr/bin/env python3

import os
import sys
import requests
from datetime import datetime, timezone

RTT_BASE = "https://data.rtt.io"

discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
refresh_token = os.environ.get("RTT_REFRESH_TOKEN")
from_crs = os.environ.get("FROM_CRS", "").upper()
to_crs = os.environ.get("TO_CRS", "").upper()
from_name = os.environ.get("FROM_NAME") or from_crs
to_name = os.environ.get("TO_NAME") or to_crs

for name, val in [
    ("DISCORD_WEBHOOK_URL", discord_webhook),
    ("RTT_REFRESH_TOKEN", refresh_token),
    ("FROM_CRS", from_crs),
    ("TO_CRS", to_crs),
]:
    if not val:
        print(f"Error: {name} is not set.")
        sys.exit(1)

# --- Get short-lived access token ---
print("Obtaining API access token...")
r = requests.get(
    f"{RTT_BASE}/api/get_access_token",
    headers={"Authorization": f"Bearer {refresh_token}"},
    timeout=10,
)
if r.status_code != 200:
    print(f"Error: Failed to obtain access token. HTTP {r.status_code}")
    sys.exit(1)

access_token = r.json().get("token")
if not access_token:
    print("Error: Invalid or expired refresh token.")
    sys.exit(1)

auth = {"Authorization": f"Bearer {access_token}"}

# --- Fetch departures ---
print(f"Fetching departures: {from_name} ({from_crs}) → {to_name} ({to_crs})...")
r = requests.get(
    f"{RTT_BASE}/gb-nr/location",
    params={"code": from_crs, "filterTo": to_crs},
    headers=auth,
    timeout=10,
)
if r.status_code != 200:
    print(f"Error: Failed to fetch departure data. HTTP {r.status_code}")
    sys.exit(1)

services = r.json().get("services") or []
if not services:
    print(f"No upcoming services found from {from_name} to {to_name}.")
    sys.exit(0)

print(f"Found {len(services)} service(s). Building notification...")

fields = []
for service in services[:3]:
    identity = service["scheduleMetadata"]["identity"]
    dep_date = service["scheduleMetadata"]["departureDate"]

    departure = service["temporalData"]["departure"]
    sched_dep = departure["scheduleAdvertised"]
    rt_dep = departure.get("realtimeForecast") or sched_dep

    platform_data = service.get("locationMetadata", {}).get("platform") or {}
    platform = platform_data.get("actual") or platform_data.get("planned") or "TBC"

    sched_fmt = sched_dep[11:16]
    rt_fmt = rt_dep[11:16]

    # Fetch full service to get arrival time at the destination stop
    detail = requests.get(
        f"{RTT_BASE}/gb-nr/service",
        params={"identity": identity, "departureDate": dep_date},
        headers=auth,
        timeout=10,
    )
    if detail.status_code != 200:
        continue

    arrival = None
    locations = detail.json().get("service", {}).get("locations") or []
    for loc in locations:
        if to_crs in (loc.get("location", {}).get("shortCodes") or []):
            arr = loc.get("temporalData", {}).get("arrival") or {}
            arr_time = arr.get("realtimeActual") or arr.get("realtimeForecast") or arr.get("scheduleAdvertised")
            if arr_time:
                arrival = arr_time[11:16]
            break

    dep_label = f"~~{sched_fmt}~~ → {rt_fmt}" if rt_fmt != sched_fmt else sched_fmt
    fields.append({
        "name": f"Departs {dep_label}",
        "value": f"Platform {platform} · Arrives {arrival or 'Unknown'}",
        "inline": True,
    })

if not fields:
    print("Error: Could not retrieve details for any services.")
    sys.exit(1)

timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
payload = {
    "embeds": [{
        "title": f"🚂 {from_name} → {to_name}",
        "color": 3447003,
        "fields": fields,
        "timestamp": timestamp,
        "footer": {"text": "National Rail · Realtime Trains"},
    }]
}

r = requests.post(discord_webhook, json=payload, timeout=10)
if r.status_code not in (200, 204):
    print(f"Error sending Discord notification. HTTP {r.status_code}")
    sys.exit(1)

print(f"Discord notification sent ({len(fields)} train(s) shown).")
