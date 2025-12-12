Below is the **exact change-set** to switch your current “Alpaca-first” project to **Saxo OpenAPI (SIM / paper-like)**, while keeping your **modular structure** intact (config / data / strategies / execution). Your current docs explicitly assume Alpaca keys + Alpaca base URL  and a config module built around `APCA_*` variables , so we’ll replace those assumptions.

---

## 1) What changes conceptually (Alpaca → Saxo)

### Authentication model

* **Alpaca:** long-lived `APCA_API_KEY_ID` + `APCA_API_SECRET_KEY` in `.env` 
* **Saxo SIM quick start:** **one-day / 24h token** from the Developer Portal (SIM-only) ([developer.saxobank.com][1])
* **Saxo production-grade:** OAuth app credentials (**AppKey/AppSecret**) + OAuth flow (Code / PKCE / etc.) ([developer.saxobank.com][2])

### Instruments

* **Alpaca:** symbols like `AAPL`, `BTC/USD` (per your config epic) 
* **Saxo:** you trade by **UIC + AssetType**, discovered via `ref/v1/instruments` ([Saxo Bank Developer Portal][3])

### Order placement

* Saxo places orders via `POST /trade/v2/orders` ([Saxo Bank Developer Portal][4])
* You can “paper-check” an order using `POST /trade/v2/orders/precheck` (useful for safe testing) ([Saxo Bank Support][5])

---

## 2) Update your dependencies (requirements.txt)

Your Story 001-003 installs `alpaca-trade-api` . Replace it.

**Remove**

* `alpaca-trade-api`

**Add**

* `requests` (simple + stable)
* optionally later: `websockets` (if you use streaming)

Example `requirements.txt` (minimal):

```txt
pandas
schedule
python-dotenv
requests
```

(Keep `python-dotenv` because your security pattern is correct and reusable .)

---

## 3) Replace your .env contract (APCA_* → SAXO_*)

Your docs currently require:

* `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `APCA_API_BASE_URL`  and assume `https://paper-api.alpaca.markets` 

### New `.env` (Saxo SIM with 24h token)

```env
# Saxo OpenAPI (SIM)
SAXO_ENV=SIM
SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
SAXO_AUTH_BASE=https://sim.logonvalidation.net
SAXO_ACCESS_TOKEN=your_24h_token_here

# Optional (only if/when you move to a real OAuth app)
SAXO_APP_KEY=
SAXO_APP_SECRET=
SAXO_REDIRECT_URI=http://localhost/mytestapp
```

Why these URLs:

* SIM REST base: `https://gateway.saxobank.com/sim/openapi` ([developer.saxobank.com][1])
* SIM auth base: `https://sim.logonvalidation.net` ([developer.saxobank.com][1])
* One-day tokens from the portal are **SIM-only** ([developer.saxobank.com][1])

---

## 4) Update `verify_env.py` (keep the pattern, change the variables)

Your current verifier checks the Alpaca vars . Replace `required_vars` with:

```python
required_vars = [
    "SAXO_ENV",
    "SAXO_REST_BASE",
    "SAXO_ACCESS_TOKEN",
]
```

(Keep the masking logic exactly as-is; it’s a good practice pattern .)

---

## 5) Replace `test_connection.py` (Alpaca clock/account → Saxo accounts/me)

Your current Story 001-006 explicitly tests Alpaca endpoints and uses `alpaca_trade_api` . For Saxo SIM, your “hello world” should replicate what your Saxo tutorial page is doing: **GET `/port/v1/accounts/me`** with a Bearer token.

Create/replace `test_connection.py` with:

```python
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import requests

def test_connection():
    print("=" * 50)
    print("Saxo OpenAPI Connection Test (SIM)")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    load_dotenv()

    base = os.getenv("SAXO_REST_BASE")
    token = os.getenv("SAXO_ACCESS_TOKEN")

    if not base or not token:
        print("✗ Missing environment variables.")
        print("  Ensure SAXO_REST_BASE and SAXO_ACCESS_TOKEN are set.")
        return False

    if "/sim/" not in base:
        print("⚠ WARNING: SAXO_REST_BASE does not look like SIM.")

    headers = {"Authorization": f"Bearer {token}"}

    # 1) clients/me (often useful to confirm identity / clientkey)
    r1 = requests.get(f"{base}/port/v1/clients/me", headers=headers, timeout=30)
    if r1.status_code != 200:
        print(f"✗ /port/v1/clients/me failed: {r1.status_code} {r1.text}")
        return False
    print("✓ /port/v1/clients/me OK")

    # 2) accounts/me (this matches the tutorial step in your screenshot)
    r2 = requests.get(f"{base}/port/v1/accounts/me", headers=headers, timeout=30)
    if r2.status_code != 200:
        print(f"✗ /port/v1/accounts/me failed: {r2.status_code} {r2.text}")
        return False

    data = r2.json()
    accounts = data.get("Data", []) if isinstance(data, dict) else []
    print(f"✓ /port/v1/accounts/me OK (accounts returned: {len(accounts)})")

    print("\n✓ ALL TESTS PASSED - Saxo API Connection Successful!")
    return True

if __name__ == "__main__":
    ok = test_connection()
    sys.exit(0 if ok else 1)
```

---

## 6) Implement a minimal Saxo REST client (drop-in replacement for Alpaca SDK)

Add: `data/saxo_client.py` (new file)

```python
import os
from dotenv import load_dotenv
import requests

class SaxoClient:
    def __init__(self):
        load_dotenv()
        self.base = os.getenv("SAXO_REST_BASE")
        self.token = os.getenv("SAXO_ACCESS_TOKEN")
        if not self.base or not self.token:
            raise RuntimeError("Missing SAXO_REST_BASE or SAXO_ACCESS_TOKEN")

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path, params=None):
        r = requests.get(f"{self.base}{path}", headers=self.headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def post(self, path, json_body=None, params=None):
        r = requests.post(f"{self.base}{path}", headers=self.headers, params=params, json=json_body, timeout=30)
        r.raise_for_status()
        return r.json()
```

This keeps your modular architecture from Story 001-005 intact .

---

## 7) Update `data/market_data.py` (symbols → UIC discovery + pricing)

### A) Instrument lookup (watchlist bootstrap)

Use `ref/v1/instruments` to map “AAPL” etc to UIC ([Saxo Bank Developer Portal][3]).

Example function:

```python
from .saxo_client import SaxoClient

def find_instrument_uic(keyword: str, asset_types="Stock"):
    c = SaxoClient()
    return c.get("/ref/v1/instruments", params={"Keywords": keyword, "AssetTypes": asset_types})
```

Note: Apple’s UIC example is commonly `Identifier: 211` for NASDAQ listing when searching by ISIN ([Saxo Bank Support][6]), but you should still query and confirm your accessible listing(s) in SIM.

### B) Pricing

Once you have `(Uic, AssetType)`, your next step is to pull prices using Saxo trade pricing endpoints (you can validate supported order types via instrument details) ([Saxo Bank Support][7]). Keep this simple first: store last-known mid/quote from the pricing response.

---

## 8) Update `execution/trade_executor.py` (order endpoint change)

Replace Alpaca order placement logic with Saxo `POST /trade/v2/orders` ([Saxo Bank Developer Portal][4]).

**Key differences:**

* You must include **AccountKey** (you’ll get it from `/port/v1/accounts/me`).
* You must specify **Uic** and **AssetType**.
* Use `/precheck` first to simulate outcomes and costs ([Saxo Bank Support][5]).

Example precheck + place:

```python
from .saxo_client import SaxoClient

def precheck_order(uic: int, asset_type: str, buy_sell: str, amount: float):
    c = SaxoClient()
    body = {
        "Uic": uic,
        "AssetType": asset_type,
        "BuySell": buy_sell,
        "Amount": amount,
        "OrderType": "Market",
        "FieldGroups": ["Costs"],
        "ManualOrder": True,
    }
    return c.post("/trade/v2/orders/precheck", json_body=body)

def place_order(account_key: str, uic: int, asset_type: str, buy_sell: str, amount: float):
    c = SaxoClient()
    body = {
        "AccountKey": account_key,
        "Uic": uic,
        "AssetType": asset_type,
        "BuySell": buy_sell,
        "Amount": amount,
        "OrderType": "Market",
        "ManualOrder": False,
    }
    return c.post("/trade/v2/orders", json_body=body)
```

---

## 9) Update your watchlist format (Epic 002 change)

Your Epic 002 currently defines watchlist as Alpaca symbols like `["AAPL", ... , "BTC/USD"]` . Replace it with **instrument descriptors**:

```python
WATCHLIST = [
  {"name": "AAPL", "asset_type": "Stock", "uic": 211},
  {"name": "BTCUSD", "asset_type": "FxSpot", "uic": 21700189},
  {"name": "ETHUSD", "asset_type": "FxSpot", "uic": 21750301},
]
```

Crypto note: Saxo has announced/implemented an AssetType transition for crypto FX pairs (FxSpot → FxCrypto) and lists impacted UICs (including BTCUSD / ETHUSD) ([developer.saxobank.com][8]). Code defensively: accept both asset types when parsing, and validate via instrument details.

---

## 10) How to get a “key” on Saxo (what you can do today)

### Fastest (SIM only): 24h token

* Use the Developer Portal’s **one-day token** feature; it is explicitly for **SIM** ([developer.saxobank.com][1])
* Put it into `SAXO_ACCESS_TOKEN`.

### Real OAuth AppKey/AppSecret (needed for Live and for robust automation)

* Saxo apps are “created for you” and then you receive **AppKey, AppSecret, AuthenticationUrl, OpenApiBaseUrl** ([developer.saxobank.com][2])
* Then implement OAuth (Authorization Code / PKCE recommended for native/desktop) ([developer.saxobank.com][9])

---

## 11) Switzerland: can you do this?

If you can log into the Saxo Developer Portal and obtain the **SIM one-day token**, you can call the SIM APIs from Switzerland (it’s just HTTPS). The key constraint is not your location but **whether your user/token/app is authorized** for the environment you are calling. The Developer Portal one-day token is **SIM-only** ([developer.saxobank.com][1]).

---

If you want, paste (redact) the JSON you get back from `/port/v1/accounts/me` and I’ll tell you exactly where to extract and persist `AccountKey` (and the minimal fields you should store in `config/config.py`).

[1]: https://developer.saxobank.com/openapi/learn/environments?utm_source=chatgpt.com "Saxo Bank Developer Portal"
[2]: https://developer.saxobank.com/openapi/learn/oauth-authorization-code-grant?utm_source=chatgpt.com "Saxo Bank Developer Portal"
[3]: https://www.developer.saxo/openapi/referencedocs/ref/v1/instruments?utm_source=chatgpt.com "Saxo Bank Developer Portal"
[4]: https://www.developer.saxo/openapi/referencedocs/trade/v2/orders?utm_source=chatgpt.com "Saxo Bank Developer Portal"
[5]: https://openapi.help.saxo/hc/en-us/articles/4418459141265-How-do-I-retrieve-trade-costs-for-orders?utm_source=chatgpt.com "How do I retrieve trade costs for orders? – Saxo Bank Support"
[6]: https://openapi.help.saxo/hc/en-us/articles/4416972708625-Can-I-retrieve-ISINs-through-the-OpenAPI?utm_source=chatgpt.com "Can I retrieve ISINs through the OpenAPI? – Saxo Bank Support"
[7]: https://openapi.help.saxo/hc/en-us/articles/4417056540689-How-can-I-find-the-supported-order-types-and-durations-for-an-instrument?utm_source=chatgpt.com "How can I find the supported order types and durations for an instrument? – Saxo Bank Support"
[8]: https://developer.saxobank.com/openapi/releasenotes/completed-planned-changes?utm_source=chatgpt.com "Saxo Bank Developer Portal"
[9]: https://developer.saxobank.com/openapi/learn/oauth-authorization-code-grant-pkce?utm_source=chatgpt.com "Saxo Bank Developer Portal"
