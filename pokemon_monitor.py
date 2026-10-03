import requests, json, os, re, sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime

TOKEN = os.environ.get("TELEGRAM_TOKEN","").strip()
CHAT = os.environ.get("TELEGRAM_CHAT","").strip()
print(f"Token set: {bool(TOKEN)} Chat set: {bool(CHAT)}", flush=True)

IS_MANUAL = "--reset" in sys.argv or os.environ.get("GITHUB_EVENT_NAME")=="workflow_dispatch"
seen = set()

KEYWORDS = ["booster","etb","bundle","tin","box"]

def send_tg(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id":CHAT,"text":text[:3800],"disable_web_page_preview":False}, timeout=15)
        print(f"TG {r.status_code}", flush=True)
    except Exception as e:
        print(f"TG fail {e}", flush=True)

def clean_url(u):
    u = u.split("?")[0].split("#")[0]
    return u.rstrip("/")

def get_products(url, base):
    print(f"Fetching {url}...", flush=True)
    headers = {"User-Agent":"Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"HTTP {r.status_code} len={len(r.text)}", flush=True)
        if r.status_code!=200 or len(r.text)<2000:
            return []
        soup = BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"Fetch fail {e}", flush=True)
        return []

    found=[]
    for a in soup.find_all("a", href=True)[:300]:
        title = a.get_text(" ", strip=True)
        if not (15 < len(title) < 150): continue
        if "pokemon" not in title.lower(): continue
        if not any(k in title.lower() for k in KEYWORDS): continue
        if "jigsaw" in title.lower() or "puzzle" in title.lower(): continue

        raw = urljoin(base, a["href"])
        clean = clean_url(raw)
        if "/products/" not in clean and "/product/" not in clean: continue
        if clean in [x["url"] for x in found]: continue

        # price
        price="N/A"
        parent = a.parent
        for _ in range(4):
            if not parent: break
            txt = parent.get_text(" ", strip=True)[:500]
            m = re.search(r'£\d+(?:\.\d{2})?', txt)
            if m: price=m.group(0); break
            parent = parent.parent

        found.append({"title":title[:100], "url":clean, "price":price})
        if len(found)>=5: break

    print(f"Found {len(found)}", flush=True)
    return found

SITES = [
    ("ChaosCards","https://www.chaoscards.co.uk/collections/pokemon-sealed-product","https://www.chaoscards.co.uk"),
    ("MagicMadhouse","https://magicmadhouse.co.uk/collections/pokemon-sealed-products","https://magicmadhouse.co.uk"),
    ("TotalCards","https://www.totalcards.net/collections/pokemon-sealed-products","https://www.totalcards.net"),
]

send_tg(f"🔎 Monitor started MANUAL RESET\n⏰ {datetime.now().strftime('%H:%M:%S')}")

for name,surl,base in SITES:
    prods = get_products(surl, base)
    for p in prods:
        msg = f"🔥 {name}\n{p['title']}\n💷 {p['price']}\n🔗 {p['url']}"
        print(msg, flush=True)
        send_tg(msg)

send_tg(f"✅ Done {datetime.now().strftime('%H:%M:%S')}")
