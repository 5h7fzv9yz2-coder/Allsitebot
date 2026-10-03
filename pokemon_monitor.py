import requests, json, os, re, sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime

TOKEN = os.environ.get("TELEGRAM_TOKEN","").strip()
CHAT = os.environ.get("TELEGRAM_CHAT","").strip()

IS_MANUAL = "--reset" in sys.argv or os.environ.get("GITHUB_EVENT_NAME")=="workflow_dispatch"
seen = set() if IS_MANUAL else set(json.load(open("seen_products.json")) if os.path.exists("seen_products.json") else [])

# YOUR FILTERS - only these get images + price
KEYWORDS = ["booster", "etb", "elite trainer", "30th", "upc", "bundle", "mini tin"]

def send_tg(text, with_image=False):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT,
                "text": text[:3800],
                "disable_web_page_preview": not with_image,
                "parse_mode": "HTML"
            }, timeout=15)
        print(f"TG {r.status_code} image={with_image}", flush=True)
    except Exception as e:
        print(f"TG fail {e}", flush=True)

def clean_url(u):
    return u.split("?")[0].split("#")[0].rstrip("/")

def get_products(url, base):
    print(f"Fetching {url}...", flush=True)
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"Fail {e}", flush=True); return []

    found=[]
    for card in soup.select(".product-item,.product-card,.grid__item, li")[:100]:
        a = card.find("a", href=True)
        if not a: continue
        title = card.get_text(" ", strip=True)
        if len(title)<20 or "pokemon" not in title.lower(): continue

        raw = urljoin(base, a["href"])
        clean = clean_url(raw)
        if "/products/" not in clean: continue

        # Price
        price="N/A"
        for sel in [".price",".money",".product__price"]:
            el=card.select_one(sel)
            if el:
                m=re.search(r'£\s?\d+(?:\.\d{2})?', el.get_text())
                if m: price=m.group(0).replace(" ",""); break
        if price=="N/A":
            m=re.search(r'£\s?\d+(?:\.\d{2})?', card.get_text())
            if m: price=m.group(0).replace(" ","")

        if clean not in [x["url"] for x in found]:
            found.append({"title": title[:110], "url": clean, "price": price})
        if len(found)>=6: break
    return found

SITES = [
    ("ChaosCards","https://www.chaoscards.co.uk/collections/pokemon-sealed-product","https://www.chaoscards.co.uk"),
    ("MagicMadhouse","https://magicmadhouse.co.uk/collections/pokemon-sealed-products","https://magicmadhouse.co.uk"),
    ("TotalCards","https://www.totalcards.net/collections/pokemon-sealed-products","https://www.totalcards.net"),
]

send_tg(f"🔎 Started {'RESET' if IS_MANUAL else ''} {datetime.now().strftime('%H:%M:%S')}", with_image=False)

all_found=[]
for name,surl,base in SITES:
    prods = get_products(surl, base)
    for p in prods:
        all_found.append((name,p))

# --- THIS IS WHERE THE FILTER + IMAGE LOGIC IS
