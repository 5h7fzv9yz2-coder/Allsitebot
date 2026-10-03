import requests, json, os, re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime

TOKEN = os.environ.get("TELEGRAM_TOKEN","").strip()
CHAT = os.environ.get("TELEGRAM_CHAT","").strip()
if not TOKEN or not CHAT:
    print("ERROR: TELEGRAM_TOKEN or TELEGRAM_CHAT missing")
    exit(1)

FILE = "last_products.json"
SEEN_FILE = "seen_products.json"
KEYWORDS = ["booster","etb","elite trainer","bundle","30th","pokeball","mini tin","collection","box","tin"]

def send_tg(text):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT, "text": text[:3800]}, timeout=15)
        if not r.ok:
            print(f"Telegram error: {r.status_code} {r.text[:300]}")
            if r.status_code == 404:
                print(">> Token invalid - regenerate at @BotFather")
    except Exception as e:
        print(f"Telegram exception: {e}")

def clean_url(u):
    u = u.split(";")[0].split("?")[0].split("#")[0]
    if "amazon" in u.lower():
        m = re.search(r'/dp/([A-Z0-9]{10})', u, re.I)
        if m: return f"https://www.amazon.co.uk/dp/{m.group(1)}"
    p = urlparse(u)
    return f"{p.scheme}://{p.netloc}{re.sub(r'//+','/',p.path)}".rstrip("/")

def get_products(url, base):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-GB,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    try:
        r = requests.get(url, headers=headers, timeout=30)
        print(f"HTTP {r.status_code}: {url}")
        if r.status_code in (403,429) or len(r.text)<2000:
            print(f"Trying proxy for {url}")
            proxy = f"https://api.allorigins.win/raw?url={requests.utils.quote(url, safe='')}"
            r = requests.get(proxy, headers=headers, timeout=30)
            print(f"Proxy HTTP {r.status_code}: {url}")
        if len(r.text)<1000: return []
        soup = BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"Request failed: {e}"); return []

    found, seen_urls = [], set()
    for a in soup.find_all("a", href=True, limit=800):
        title = a.get_text(" ", strip=True)
        if not (10 < len(title) < 180): continue
        low = title.lower()
        if "pokemon" not in low: continue
        if not any(k in low for k in KEYWORDS): continue
        if any(x in low for x in ["cookie","privacy","filter","wishlist"]): continue
        if "jigsaw" in low or "puzzle" in low or "plush" in low: continue
        raw = urljoin(base, a["href"])
        clean = clean_url(raw)
        if clean in seen_urls or len(clean)<20: continue
        if "/search?" in clean.lower() or "/blogs/" in clean.lower(): continue
        price = "N/A"
        p=a
        for _ in range(5):
            if not p or not hasattr(p,'parent'): break
            p=p.parent
            m=re.search(r'£\s?\d+(?:\.\d{1,2})?', p.get_text(" ",strip=True)[:800])
            if m: price=m.group(0); break
        found.append({"title":title,"url":clean,"price":price})
        seen_urls.add(clean)
        if len(found)>=6: break
    return found

# ONLY WORKING SITES
SITES = [
    ("ChaosCards","https://www.chaoscards.co.uk/search/pok","https://www.chaoscards.co.uk"),
    ("MagicMadhouse","https://magicmadhouse.co.uk/search?q=pokemon","https://magicmadhouse.co.uk"),
    ("TotalCards","https://www.totalcards.net/search?type=product&q=pokemon","https://www.totalcards.net"),
    ("TrollTrader","https://www.trolltradercards.com/search?q=pokemon","https://www.trolltradercards.com"),
    ("ShopTo","https://www.shopto.net/en/search/?s=pokemon","https://www.shopto.net"),
    ("Zatu","https://www.board-game.co.uk/?s=pokemon","https://www.board-game.co.uk"),
    ("ElementGames","https://elementgames.co.uk/search?search=pokemon","https://elementgames.co.uk"),
    ("MagicTricks","https://www.magictricks.co.uk/search/pokemon/","https://www.magictricks.co.uk"),
    ("AxionNow","https://axionnow.com/?s=pokemon&post_type=product","https://axionnow.com"),
    ("Smyths","https://www.smythstoys.com/uk/en-gb/c/toys/plush-and-collectables/pokemon/c-1000-pokemon","https://www.smythstoys.com"),
]

def load_json(fn, default):
    if not os.path.exists(fn): return default
    try: return json.load(open(fn,encoding="utf-8"))
    except: return default

last = load_json(FILE, {})
seen = set(load_json(SEEN_FILE, []))
is_first = len(seen)==0

print("="*60)
print(f"POKEMON STOCK MONITOR {datetime.now()}")
print(f"First run: {is_first} Seen: {len(seen)}")
print("="*60)
send_tg(f"🔎 Pokemon monitor started\n⏰ {datetime.now().strftime('%H:%M:%S')}\n🏪 Checking {len(SITES)} stores")

total_found=total_new=0
for name,surl,base in SITES:
    try:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking {name}...")
        prods=get_products(surl,base)
        print(f"{name}: {len(prods)} matches")
        if not prods: continue
        total_found+=len(prods); last[name]=prods
        new_items = [p for p in prods if p["url"] not in seen] if not is_first else prods
        if new_items:
            msg = f"{'🚨 NEW at' if not is_first else '🔥'} {name}\n"
            for p in new_items:
                msg+=f"\n• {p['title'][:70]}\n💷 {p['price']}\n{p['url']}\n"
                seen.add(p["url"]); total_new+=1
            send_tg(msg)
    except Exception as e: print(f"ERROR {name}: {e}")

json.dump(last, open(FILE,"w",encoding="utf-8"), indent=2, ensure_ascii=False)
json.dump(sorted(seen), open(SEEN_FILE,"w",encoding="utf-8"), indent=2, ensure_ascii=False)

print(f"\nSCAN COMPLETE Found:{total_found} New:{total_new} Total:{len(seen)}")
send_tg(f"✅ Scan complete\n🏪 {len(SITES)} stores\n🔎 Found: {total_found}\n🚨 New: {total_new}")
