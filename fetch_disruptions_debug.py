import requests
from bs4 import BeautifulSoup
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Try the disruptions listing page
url = "https://www.nationalrail.co.uk/service-disruptions/"
print(f"Fetching {url} ...")
r = requests.get(url, headers=HEADERS, timeout=15)
print(f"Status: {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type')}")

if r.status_code == 200:
    soup = BeautifulSoup(r.text, "html.parser")

    # Print page title
    print(f"Title: {soup.title.string if soup.title else 'N/A'}")

    # Look for JSON-LD structured data
    for script in soup.find_all("script", type="application/ld+json"):
        print("JSON-LD:", script.string[:500])

    # Look for any __NEXT_DATA__ or similar
    for script in soup.find_all("script"):
        if script.string and "__NEXT_DATA__" in (script.string or ""):
            print("Next.js data found:", script.string[:2000])
            break
        if script.string and "disruption" in (script.string or "").lower():
            print("Disruption script:", script.string[:500])

    # Look for disruption links matching the pattern
    for a in soup.find_all("a", href=True):
        if "service-disruptions" in a["href"] or "disruption" in a["href"]:
            print(f"Disruption link: {a['href']} -> {a.get_text(strip=True)[:80]}")

    # Print first 3000 chars of body text
    print("\n--- PAGE TEXT (first 3000 chars) ---")
    print(soup.get_text()[:3000])
else:
    print("Response body:", r.text[:500])
