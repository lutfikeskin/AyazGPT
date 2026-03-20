import httpx
import json
from datetime import datetime

today = datetime.now().strftime('%d.%m.%Y')
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.kap.org.tr/tr",
    "Content-Type": "application/json"
}
payload = {
    "fromDate": today,
    "toDate": today,
    "disclosureTypes": None,
    "memberTypes": ["DDK", "IGS"],
    "mkkMemberOid": None
}

try:
    with httpx.Client(timeout=30.0) as client:
        r = client.post("https://www.kap.org.tr/tr/api/disclosure/list/main", headers=headers, json=payload)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            with open("/tmp/kap_api_response.json", "w", encoding="utf-8") as f:
                json.dump(r.json(), f, ensure_ascii=False, indent=2)
            print("Response saved to /tmp/kap_api_response.json")
        else:
            print(f"Error: {r.text[:500]}")
except Exception as e:
    print(f"Exception: {e}")
