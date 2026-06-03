#!/usr/bin/env python3

import os
import sys
import requests
from datetime import datetime, timezone

RTT_BASE = "https://data.rtt.io"
RTT_URL = "https://www.realtimetrains.co.uk/"

discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
refresh_token = os.environ.get("RTT_REFRESH_TOKEN")
routes_env = os.environ.get("ROUTES", "LST:BIS")
notify_always = os.environ.get("NOTIFY_ALWAYS", "false").lower() == "true"
delay_threshold_mins = int(os.environ.get("DELAY_THRESHOLD_MINS", "5"))

if not discord_webhook:
    print("Error: DISCORD_WEBHOOK_URL is not set.")
    sys.exit(1)
if not refresh_token:
    print("Error: RTT_REFRESH_TOKEN is not set.")
    sys.exit(1)

routes = []
for pair in routes_env.split(","):
    pair = pair.strip()
    if ":" in pair:
        f, t = pair.split(":", 1)
        routes.append((f.strip().upper(), t.strip().upper()))

if not routes:
    print("Error: No valid routes configured in ROUTES.")
    sys.exit(1)


def send_discord(payload):
    r = requests.post(discord_webhook, json=payload, timeout=10)
    if r.status_code not in (200, 204):
        print(f"Error sending Discord notification. HTTP {r.status_code}")
        sys.exit(1)


def parse_time(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


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

disruptions = []

for from_crs, to_crs in routes:
    print(f"Checking {from_crs} → {to_crs}...")
    r = requests.get(
        f"{RTT_BASE}/gb-nr/location",
        params={"code": from_crs, "filterTo": to_crs},
        headers=auth,
        timeout=10,
    )
    if r.status_code != 200:
        print(f"Warning: API error for {from_crs}→{to_crs}: HTTP {r.status_code}")
        continue

    data = r.json()
    services = data.get("services") or []
    print(f"  {len(services)} upcoming service(s)")

    if not services:
        continue

    # Print structure of first service for debugging field names
    import json
    print(f"  [debug] first service: {json.dumps(services[0], indent=2)}")

    for service in services[:5]:
        identity = service.get("scheduleMetadata", {}).get("identity", "?")
        departure = service.get("temporalData", {}).get("departure", {})
        sched_dep = departure.get("scheduleAdvertised", "")
        sched_time = sched_dep[11:16] if len(sched_dep) >= 16 else sched_dep

        is_cancelled = service.get("realtimeCancelled", False)

        delay_mins = 0
        if not is_cancelled:
            rt_dep = departure.get("realtimeForecast") or departure.get("realtimeActual")
            if rt_dep and sched_dep:
                sched_dt = parse_time(sched_dep)
                rt_dt = parse_time(rt_dep)
                if sched_dt and rt_dt:
                    delay_mins = (rt_dt - sched_dt).total_seconds() / 60

        if is_cancelled:
            msg = f"{from_crs}→{to_crs} {sched_time}: Cancelled (service {identity})"
            print(f"  CANCELLED: {msg}")
            disruptions.append(msg)
        elif delay_mins >= delay_threshold_mins:
            msg = f"{from_crs}→{to_crs} {sched_time}: Delayed {int(delay_mins)} min (service {identity})"
            print(f"  DELAYED: {msg}")
            disruptions.append(msg)

timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

if disruptions:
    print("Disruptions found! Sending Discord notification...")
    send_discord({
        "embeds": [{
            "title": "⚠️ Train Service Alert",
            "description": "\n".join(disruptions),
            "url": RTT_URL,
            "color": 15158332,
            "timestamp": timestamp,
            "footer": {"text": "National Rail · Realtime Trains"}
        }]
    })
    print("Discord notification sent successfully.")
elif notify_always:
    print("No disruptions found. Sending all-clear notification...")
    send_discord({
        "embeds": [{
            "title": "✅ No Train Disruptions",
            "description": "All monitored routes are running normally.",
            "url": RTT_URL,
            "color": 3066993,
            "timestamp": timestamp,
            "footer": {"text": "National Rail · Realtime Trains"}
        }]
    })
    print("Discord all-clear notification sent successfully.")
else:
    print("No disruptions found for monitored routes.")
