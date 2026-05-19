#!/usr/bin/env python3

import os
import re
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

URL = "https://www.nationalrail.co.uk/status-and-disruptions/?mode=train-operator-status"

discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
train_operators = os.environ.get("TRAIN_OPERATORS", "Stansted Express,Cambridge")
notify_always = os.environ.get("NOTIFY_ALWAYS", "false").lower() == "true"

if not discord_webhook:
    print("Error: DISCORD_WEBHOOK_URL is not set.")
    sys.exit(1)

operators = [op.strip() for op in train_operators.split(",")]


def send_discord(payload):
    r = requests.post(discord_webhook, json=payload, timeout=10)
    if r.status_code not in (200, 204):
        print(f"Error sending Discord notification. HTTP {r.status_code}")
        sys.exit(1)


print("Fetching webpage content...")
try:
    response = requests.get(URL, timeout=15)
    response.raise_for_status()
except requests.RequestException as e:
    print(f"Error fetching webpage: {e}")
    sys.exit(1)

if not response.text:
    print("Error: Empty response from National Rail.")
    sys.exit(1)

soup = BeautifulSoup(response.text, "html.parser")
disruptions = []

for operator in operators:
    print(f"Checking status for: {operator}")
    matches = soup.find_all(string=re.compile(f"incident: {re.escape(operator)}", re.IGNORECASE))
    for match in matches:
        text = re.sub(r"incident:", "INCIDENT:", match.strip(), flags=re.IGNORECASE)
        disruptions.append(text)

timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

if disruptions:
    print("Disruptions found! Sending Discord notification...")
    send_discord({
        "embeds": [{
            "title": "⚠️ Train Service Alert",
            "description": "\n".join(disruptions),
            "url": URL,
            "color": 15158332,
            "timestamp": timestamp,
            "footer": {"text": "National Rail Status Monitor"}
        }]
    })
    print("Discord notification sent successfully.")
elif notify_always:
    print("No disruptions found. Sending all-clear notification...")
    send_discord({
        "embeds": [{
            "title": "✅ No Train Disruptions",
            "description": "All monitored operators are running normally.",
            "url": URL,
            "color": 3066993,
            "timestamp": timestamp,
            "footer": {"text": "National Rail Status Monitor"}
        }]
    })
    print("Discord all-clear notification sent successfully.")
else:
    print("No disruptions found for monitored operators.")
