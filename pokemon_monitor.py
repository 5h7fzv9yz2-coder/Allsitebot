import requests, os, re, json, sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN = os.environ.get("TELEGRAM_TOKEN","").strip()
CHAT = os.environ.get("TELEGRAM_CHAT","").strip()
IS_MANUAL = "--reset" in sys.argv or os.environ.get("GITHUB_EVENT_NAME")=="workflow_dispatch"

KEYWORDS = ["booster","etb","elite trainer","30th","upc","bundle","mini tin"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def send_tg(text, with_image=False):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT, "text": text[:3800], "disable_web_page_preview": not with_image, "parse_mode": "HTML"},
            timeout=15
        )
    except Exception as ex:
        print(f"TG fail {ex}", flush=True)

def clean(u): return u.split("?")[0].split("#")[0].rstrip("/")

def scrape_one(site):
    name, url, base = site
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f"{name} HTTP {r.status_code} len={len(r.text)}", flush=True)
        if r.status_code!= 200:
            return name, []
        soup = BeautifulSoup(r.text, "lxml")
        found = []
        # broader selector
        for card in soup.select("[class*=product], li")[:200]:
            a = card.find("a", href=True)
            if not a: continue
            title = card.get_text(" ", strip=True)
            if len(title) < 20 or "pokemon" not in title.lower(): continue
            raw = urljoin(base, a["href"])
            curl = clean(raw)
            if "/products/" not in curl and "/product/" not in curl: continue
            m = re.search(r'£\s?\d+(?:\.\d{2})?', card.get_text())
            price = m.group(0).replace(" ","") if m else "N/A"
            if curl not in [x["url"] for x in found]:
                found.append({"title": title[:120], "url": curl, "price": price})
            if len(found) >= 8: break
        return name, found
    except Exception as e:
        print(f"{name} fail {e}", flush=True)
        return name, []

# 8 REAL WORKING SITES ONLY
SITES = [
    ("TotalCards","https://www.totalcards.net/collections/pokemon-sealed-products","https://www.totalcards.net"),
    ("TotalCards Boxes","https://www.totalcards.net/collections/pokemon-booster-boxes","https://www.totalcards.net"),
    ("365Games","https://www.365games.co.uk/search?q=pokemon+sealed","https://www.365games.co.uk"),
    ("ShopTo","https://www.shopto.net/en/search/?s=Pokemon+booster+box","https://www.shopto.net"),
    ("ChaosCards","https://www.chaoscards.co.uk/collections/pokemon-sealed-product","https://www.chaoscards.co.uk"),
    ("MagicMadhouse","https://magicmadhouse.co.uk/collections/sealed-pokemon-cards","https://magicmadhouse.co.uk"),
    ("TitanCards","https://www.titancards.co.uk/collections/pokemon-sealed-products","https://www.titancards.co.uk"),
    ("GatheringGames","https://gatheringgames.uk/collections/pokemon","https://gatheringgames.uk"),
]

is_first_run = IS_MANUAL or not os.path.exists("seen_products.json")
seen = set() if is_first_run else set(json.load(open("seen_products.json")) if os.path.exists("seen_products.json") else [])

send_tg(f"Scanning 8 real sites {'FIRST RUN' if is_first_run else ''} {datetime.now().strftime('%H:%M')}")

all_results=[]
with ThreadPoolExecutor(max_workers=5) as ex:
    futures={ex.submit(scrape_one,s): s for s in SITES}
    for f in as_completed(futures):
        name, prods = f.result()
        for p in prods:
            low=p["title"].lower()
            # FIRST RUN = looser filter, show all with price
            if is_first_run:
                if p["price"]=="N/A": continue
            else:
                if not any(k in low for k in KEYWORDS): continue
                if p["price"]=="N/A": continue
            if "simplified chinese" in low: continue
            all_results.append((name,p))

to_send = all_results if is_first_run else [x for x in all_results if x[1]["url"] not in seen]
print(f"FIRST={is_first_run} TO_SEND={len(to_send)}", flush=True)

for name,p in to_send[:25]:
    msg=f"<b>{name}</b>\n{p['title']}\n\nRetail: <b>{p['price']}</b>\n{p['url']}"
    send_tg(msg, with_image=True)
    seen.add(p["url"])

open("seen_products.json","w").write(json.dumps(sorted(list(seen)), indent=2))
send_tg(f"Done First={is_first_run} Sent:{len(to_send)}", with_image=False)
