import requests
from bs4 import BeautifulSoup
import json
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def get_next_data(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    print(f"{url} -> {r.status_code}")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if m:
        return json.loads(m.group(1)).get("props", {}).get("pageProps", {})
    return {}

# Status page - print just the 'data' field
props = get_next_data("https://www.nationalrail.co.uk/status-and-disruptions/?mode=train-operator-status")
print("pageProps keys:", list(props.keys()))
data = props.get("data")
print("pageProps.data (full):")
print(json.dumps(data, indent=2)[:8000])

# Also try nreservices backend
print("\n--- nreservices API ---")
for path in ["/service-disruptions", "/disruptions", "/v1/disruptions", "/v2/disruptions"]:
    r = requests.get(f"https://nreservices.nationalrail.co.uk{path}", headers=HEADERS, timeout=10)
    print(f"{path} -> {r.status_code}")
    if r.status_code == 200:
        print(r.text[:500])
