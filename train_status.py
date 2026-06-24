#!/usr/bin/env python3

import json
import os
import re
import sys
import requests
from datetime import datetime, timezone

from rtt import RTT_BASE, get_auth_headers

RTT_URL = "https://www.realtimetrains.co.uk/"
NR_STATUS_URL = "https://www.nationalrail.co.uk/status-and-disruptions/?mode=train-operator-status"
NR_DISRUPTIONS_URL = "https://www.nationalrail.co.uk/status-and-disruptions"
STATE_FILE = "state.json"

NR_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
refresh_token = os.environ.get("RTT_REFRESH_TOKEN")
routes_env = os.environ.get("ROUTES", "LST:BIS")
notify_always = os.environ.get("NOTIFY_ALWAYS", "false").lower() == "true"
delay_threshold_mins = int(os.environ.get("DELAY_THRESHOLD_MINS", "5"))
operator_codes_env = os.environ.get("OPERATOR_CODES", "LE,SX")

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

watched_operators = {c.strip().upper() for c in operator_codes_env.split(",") if c.strip()}


def send_discord(embed):
    r = requests.post(discord_webhook, json={"embeds": [embed]}, timeout=10)
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


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"nr": {}, "rtt": {}}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def get_route_stations(from_crs, to_crs, auth):
    """Return the union of station names across the next few services between from_crs and to_crs.
    Using multiple services ensures all intermediate stops are captured regardless of service pattern."""
    r = requests.get(
        f"{RTT_BASE}/gb-nr/location",
        params={"code": from_crs, "filterTo": to_crs},
        headers=auth,
        timeout=10,
    )
    if r.status_code != 200:
        print(f"  Warning: Could not fetch services for {from_crs}→{to_crs}")
        return []

    services = r.json().get("services") or []
    if not services:
        print(f"  Warning: No services found for {from_crs}→{to_crs}, skipping route station lookup")
        return []

    all_stations = set()
    for service in services[:3]:
        identity = service["scheduleMetadata"]["identity"]
        dep_date = service["scheduleMetadata"]["departureDate"]

        detail = requests.get(
            f"{RTT_BASE}/gb-nr/service",
            params={"identity": identity, "departureDate": dep_date},
            headers=auth,
            timeout=10,
        )
        if detail.status_code != 200:
            continue

        locations = detail.json().get("service", {}).get("locations") or []
        in_route = False
        for loc in locations:
            short_codes = loc.get("location", {}).get("shortCodes") or []
            name = loc.get("location", {}).get("description", "")

            if from_crs in short_codes:
                in_route = True

            if in_route and name:
                all_stations.add(name)

            if to_crs in short_codes:
                break

    return list(all_stations)


def get_nr_disruptions(route_station_names):
    """Return active disruptions as {slug: {summary, label}}, filtered to the commute route."""
    print("Checking National Rail disruptions page...")
    try:
        r = requests.get(NR_STATUS_URL, headers=NR_HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"Warning: National Rail status page returned HTTP {r.status_code}")
            return {}
    except requests.RequestException as e:
        print(f"Warning: Failed to fetch National Rail status: {e}")
        return {}

    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if not m:
        print("Warning: Could not find __NEXT_DATA__ on National Rail status page")
        return {}

    try:
        page_props = json.loads(m.group(1)).get("props", {}).get("pageProps", {})
    except json.JSONDecodeError:
        print("Warning: Failed to parse National Rail __NEXT_DATA__ JSON")
        return {}

    disruptions = page_props.get("data", {}).get("disruptionsData", {}).get("disruptions", [])
    print(f"  {len(disruptions)} total disruption(s) listed on National Rail")

    route_stations_lower = {name.lower() for name in route_station_names}
    result = {}

    for d in disruptions:
        if d.get("incidentCleared"):
            continue
        operators = d.get("operatorsAffectedCollection", [])
        affected_codes = {op.get("code", "").upper() for op in operators}
        if not affected_codes.intersection(watched_operators):
            continue

        try:
            summary = d["summary"]["json"]["content"][0]["content"][0]["value"]
        except (KeyError, IndexError, TypeError):
            summary = f"Disruption reported near {d.get('name', 'unknown location')}"

        if route_station_names:
            summary_lower = summary.lower()
            route_station_mentioned = any(station in summary_lower for station in route_stations_lower)
            if not route_station_mentioned and "between" in summary_lower:
                print(f"  Skipping (specific non-route stations): {summary[:80]}")
                continue

        matched_names = ", ".join(
            op["name"] for op in operators if op.get("code", "").upper() in watched_operators
        )
        slug = d.get("slug") or summary[:60]
        print(f"  Active ({matched_names}): {summary}")
        result[slug] = {"summary": summary, "label": matched_names}

    return result


auth = get_auth_headers(refresh_token)

# --- Load previous state ---
prev_state = load_state()
prev_nr = prev_state.get("nr", {})
prev_rtt = prev_state.get("rtt", {})

# --- Build route station list from live timetable ---
all_route_stations = set()
for from_crs, to_crs in routes:
    print(f"Fetching route stations for {from_crs} → {to_crs}...")
    stations = get_route_stations(from_crs, to_crs, auth)
    if stations:
        print(f"  Stations: {', '.join(stations)}")
        all_route_stations.update(stations)

# --- Check RTT for cancelled/delayed trains ---
current_rtt = {}
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

    services = r.json().get("services") or []
    print(f"  {len(services)} upcoming service(s)")

    for service in services[:5]:
        identity = service.get("scheduleMetadata", {}).get("identity", "?")
        departure = service.get("temporalData", {}).get("departure", {})
        sched_dep = departure.get("scheduleAdvertised", "")
        sched_time = sched_dep[11:16] if len(sched_dep) >= 16 else sched_dep

        is_cancelled = departure.get("isCancelled", False)

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
            current_rtt[identity] = msg
        elif delay_mins >= delay_threshold_mins:
            msg = f"{from_crs}→{to_crs} {sched_time}: Delayed {int(delay_mins)} min (service {identity})"
            print(f"  DELAYED: {msg}")
            current_rtt[identity] = msg

# --- Check National Rail disruption alerts ---
current_nr = get_nr_disruptions(list(all_route_stations))

# --- Diff against previous state ---
nr_new     = {s: d for s, d in current_nr.items() if s not in prev_nr}
nr_changed = {s: d for s, d in current_nr.items() if s in prev_nr and prev_nr[s]["summary"] != d["summary"]}
nr_cleared = {s: d for s, d in prev_nr.items() if s not in current_nr}
rtt_new    = {i: m for i, m in current_rtt.items() if i not in prev_rtt or prev_rtt[i] != m}

# --- Save updated state ---
save_state({"nr": current_nr, "rtt": current_rtt})

timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

if notify_always:
    # Manual run: show full current state regardless of previous state
    sent = False
    if current_rtt:
        send_discord({
            "title": "⚠️ Train Service Disruptions",
            "description": "\n".join(current_rtt.values()),
            "url": RTT_URL,
            "color": 15158332,
            "timestamp": timestamp,
            "footer": {"text": "National Rail · Realtime Trains"},
        })
        sent = True
    if current_nr:
        send_discord({
            "title": "⚠️ National Rail Disruption Alert",
            "description": "\n".join(f"**{d['label']}**: {d['summary']}" for d in current_nr.values()),
            "url": NR_DISRUPTIONS_URL,
            "color": 15105570,
            "timestamp": timestamp,
            "footer": {"text": "National Rail"},
        })
        sent = True
    if not sent:
        send_discord({
            "title": "✅ No Train Disruptions",
            "description": "All monitored routes and operators are running normally.",
            "url": RTT_URL,
            "color": 3066993,
            "timestamp": timestamp,
            "footer": {"text": "National Rail · Realtime Trains"},
        })
    print("Discord notification sent successfully.")

elif nr_new or nr_changed or nr_cleared or rtt_new:
    # Scheduled run: only notify on changes
    if rtt_new:
        send_discord({
            "title": "⚠️ Train Service Disruptions",
            "description": "\n".join(rtt_new.values()),
            "url": RTT_URL,
            "color": 15158332,
            "timestamp": timestamp,
            "footer": {"text": "National Rail · Realtime Trains"},
        })

    nr_alert_msgs = (
        [f"**{d['label']}**: {d['summary']}" for d in nr_new.values()] +
        [f"**{d['label']}** *(updated)*: {d['summary']}" for d in nr_changed.values()]
    )
    if nr_alert_msgs:
        send_discord({
            "title": "⚠️ National Rail Disruption Alert",
            "description": "\n".join(nr_alert_msgs),
            "url": NR_DISRUPTIONS_URL,
            "color": 15105570,
            "timestamp": timestamp,
            "footer": {"text": "National Rail"},
        })

    if nr_cleared:
        cleared_msgs = [f"**{d['label']}**: {d['summary']}" for d in nr_cleared.values()]
        send_discord({
            "title": "✅ Disruption Cleared",
            "description": "\n".join(cleared_msgs),
            "url": NR_DISRUPTIONS_URL,
            "color": 3066993,
            "timestamp": timestamp,
            "footer": {"text": "National Rail"},
        })

    print("Changes detected. Discord notification(s) sent successfully.")

else:
    print("No changes since last run. Skipping notification.")
