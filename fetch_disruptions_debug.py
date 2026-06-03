import requests
from bs4 import BeautifulSoup
import json
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def fetch(url):
    print(f"\n--- Fetching {url} ---")
    r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
    print(f"Status: {r.status_code}  Content-Type: {r.headers.get('content-type','')}")
    return r

def inspect_nextjs(r):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            print("__NEXT_DATA__ buildId:", data.get("buildId"))
            props = data.get("props", {}).get("pageProps", {})
            print("pageProps keys:", list(props.keys())[:20])
            print("pageProps (first 3000 chars):", json.dumps(props)[:3000])
            return data.get("buildId")
        except Exception as e:
            print("JSON parse error:", e)
    return None

# 1. Try the specific disruption page the user provided
r1 = fetch("https://www.nationalrail.co.uk/service-disruptions/broxbourne-20260603/")
if r1.status_code == 200:
    bid = inspect_nextjs(r1)
    soup = BeautifulSoup(r1.text, "html.parser")
    print("Page title:", soup.title.string if soup.title else "N/A")
    print("Text (first 2000):", soup.get_text()[:2000])
else:
    print("Body:", r1.text[:500])

# 2. Try the status/disruptions page that previously worked
r2 = fetch("https://www.nationalrail.co.uk/status-and-disruptions/?mode=train-operator-status")
if r2.status_code == 200:
    inspect_nextjs(r2)
    soup2 = BeautifulSoup(r2.text, "html.parser")
    for a in soup2.find_all("a", href=True):
        if "disruption" in a["href"]:
            print(f"Link: {a['href']} -> {a.get_text(strip=True)[:60]}")

# 3. Try potential API endpoints
for api_url in [
    "https://www.nationalrail.co.uk/api/disruptions",
    "https://www.nationalrail.co.uk/api/service-disruptions",
    "https://www.nationalrail.co.uk/api/v1/disruptions",
]:
    r = fetch(api_url)
    if r.status_code == 200:
        print("Response:", r.text[:1000])
