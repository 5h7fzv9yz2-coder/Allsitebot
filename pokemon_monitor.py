import requests, json, os, re, sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime

TOKEN = os.environ.get("TELEGRAM_TOKEN","").strip()
CHAT = os.environ.get("TELEGRAM_CHAT","").strip()

FILE = "last_products.json"
SEEN_FILE = "seen_products.json"

# === CLEAR ON MANUAL RUN ===
# If you run from GitHub Actions "Run workflow" button, it sets GITHUB_EVENT_NAME=workflow_dispatch
# We auto-clear for that. Or run locally with: python pokemon_monitor.py --reset
is_manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" or "--reset" in sys.argv or "--manual" in sys.argv
if is_manual:
    for f in [FILE, SEEN_FILE]:
        if os.path.exists(f):
            os.remove(f)
            print(f"Cleared {f} for manual run")
    seen = set()
    is_first = True
else:
    def load_json(fn, default):
        if not os.path.exists(fn): return default
        try: return json.load(open(fn,encoding="utf-8"))
        except: return default
    seen = set(load_json(SEEN_FILE, []))
    is_first = len(seen)==0

KEYWORDS = ["booster","etb","elite trainer","bundle","30th","pokeball","mini tin","collection","box","tin"]

def send_tg(text):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id":CHAT,"text":text[:3800],"disable_web_page_preview":False}, timeout=15)
        if not r.ok: print(f"Telegram error {r.status_code}: {r.text[:400]}")
    except Exception as e: print(f"TG error: {e}")

def clean_url(dirty):
    # Strip everything after?, ;, #
    dirty = dirty.split(";")[0].split("?")[0].split("#")[0]
    # Amazon clean to /dp/ASIN
    m = re.search(r'/dp/([A-Z0-9]{10})', dirty, re.I)
    if m: return f"https://www.amazon.co.uk/dp/{m.group(1)}"
    m = re.search(r'/gp/product/([A-Z0-9]{10})', dirty, re.I)
    if m: return f"https://www.amazon.co.uk/dp/{m.group(1)}"
    # Shopify /products/handle clean
    parsed = urlparse(dirty)
    # Remove double slashes, trailing slash
    path = re.sub(r'/+', '/', parsed.path).rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"

def get_price_from_block(block):
    # Search for £ price in text
    text = block.get_text(" ", strip=True)[:1000]
    m = re.search(r'£\s?\d{1,4}(?:\.\d{2})?', text)
    if m: return m.group(0).replace(" ", "")
    # Try data attributes
    for el in block.find_all(attrs={"data-price": True}):
        if "£" in el["data-price"]: return el["data-price"]
    return "N/A"

def get_products(url, base):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-GB,en;q=0.9",
    }
    try:
        r = requests.get(url, headers=headers, timeout=30)
        print(f"HTTP {r.status_code}: {url}")
        if r.status_code in (403,429) or len(r.text)<1500:
            proxy = f"https://api.allorigins.win/raw?url={requests.utils.quote(url, safe='')}"
            r = requests.get(proxy, headers=headers, timeout=25)
            print(f"Proxy {r.status_code}: {url}")
        soup = BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"Fail {url}: {e}"); return []

    found, seen_urls = [], set()
    for a in soup.find_all("a", href=True, limit=900):
        title = a.get_text(" ", strip=True)
        if not (12 < len(title) < 160): continue
        low = title.lower()
        if "pokemon" not in low: continue
        if not any(k in low for k in KEYWORDS): continue
        if any(x in low for x in ["cookie","privacy","wishlist","jigsaw","puzzle","plush"]): continue

        raw = urljoin(base, a["href"])
        clean = clean_url(raw)
        if clean in seen_urls or len(clean)<25: continue
        if "/search" in clean or "/blogs" in clean or "/collections/all" in clean: continue
        # Must look like a product
        if "/products/" not in clean and "/product/" not in clean and "/dp/" not in clean and "/p/" not in clean:
            # Allow but only if title is strong match
            if "booster" not in low and "etb" not in low and "bundle" not in low: continue

        # PRICE - look 6 parents up
        price = "N/A"
        p = a
        for _ in range(6):
            if not p or not getattr(p,'parent',None): break
            p = p.parent
            try:
                pr = get_price_from_block(p)
                if pr!= "N/A": price = pr; break
            except: break

        found.append({"title": title, "url": clean, "price": price})
        seen_urls.add(clean)
        if len(found)>=6: break
    return found

SITES = [
    ("ChaosCards","https://www.chaoscards.co.uk/search/pok","https://www.chaoscards.co.uk"),
    ("MagicMadhouse","https://magicmadhouse.co.uk/search?q=pokemon","https://magicmadhouse.co.uk"),
    ("TotalCards","https://www.totalcards.net/search?type=product&q=pokemon","https://www.totalcards.net"),
    ("TrollTrader","https://www.trolltradercards.com/search?q=pokemon","https://www.trolltradercards.com"),
    ("ShopTo","https://www.shopto.net/en/search/?s=pokemon","https://www.shopto.net"),
    ("Zatu","https://www.board-game.co.uk/?s=pokemon","https://www.board-game.co.uk"),
    ("ElementGames","https://elementgames.co.uk/search?search=pokemon","https://elementgames.co.uk"),
    ("Smyths","https://www.smythstoys.com/uk/en-gb/c/toys/plush-and-collectables/pokemon/c-1000-pokemon","https://www.smythstoys.com"),
]

def load_json(fn, default):
    if not os.path.exists(fn): return default
    try: return json.load(open(fn,encoding="utf-8"))
    except: return default

last = load_json(FILE, {})
if not is_manual:
    seen = set(load_json(SEEN_FILE, []))
else:
    seen = set()

print("="*60)
print(f"POKEMON MONITOR {datetime.now()} - Manual reset: {is_manual}")
print(f"Previously seen: {len(seen)}")
print("="*60)

send_tg(f"🔎 Monitor started {'(MANUAL RESET)' if is_manual else ''}\n⏰ {datetime.now().strftime('%H:%M:%S')}\n🏪 {len(SITES)} stores")

total_found=total_new=0
for name,surl,base in SITES:
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {name}...")
    prods = get_products(surl, base)
    print(f"{name}: {len(prods)} matches")
    for p in prods:
        print(f" - {p['title'][:70]} | {p['price']} | {p['url']}")
    if not prods: continue
    total_found+=len(prods)
    last[name]=prods

    # If manual reset, everything is new. If auto, only unseen
    to_alert = prods if is_manual or is_first else [p for p in prods if p["url"] not in seen]

    if to_alert:
        msg = f"{'🔥' if is_first or is_manual else '🚨 NEW at'} {name} ({len(to_alert)})\n"
        for p in to_alert:
            msg += f"\n• {p['title'][:75]}\n💷 {p['price']}\n🔗 {p['url']}\n"
            seen.add(p["url"]); total_new+=1
