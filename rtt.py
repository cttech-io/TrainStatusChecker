import sys
import requests

RTT_BASE = "https://data.rtt.io"


def get_auth_headers(refresh_token):
    """Exchange an RTT refresh token for a short-lived access token and return auth headers."""
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

    return {"Authorization": f"Bearer {access_token}"}
