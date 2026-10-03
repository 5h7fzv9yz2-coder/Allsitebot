import requests, json, os, re, sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime

TOKEN = os.environ.get("TELEGRAM_TOKEN","").strip()
CHAT = os.environ.get("TELEGRAM_CHAT","").strip()

FILE = "last_products.json"
SEEN_FILE = "seen_products.json"

IS_MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" or "--reset" in sys.argv

# FORCE CLEAR ON MANUAL
if IS_MANUAL:
    seen = set()
    is_first = True
    print("MANUAL RESET - ignoring old history")
else:
    seen = set(json.load(open(SEEN_FILE)) if os.path.exists(SEEN_FILE) else [])
    is_first = len(seen)==0

KEYWORDS = ["booster","etb","elite trainer box","bundle","mini tin","collection","charizard","mew","evolving","151"]

def send_tg(text):
    # Send with preview so image shows like your Ravensburger one
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id":CHAT,"text":text,"disable_web_page_preview":False}, timeout=20)
        print(f"TG {r.status_code}: {r.text[:200]}")
    except Exception as e: print(e)

def clean_url(u):
    u = u.split("?")[0].split("#")[0].split(";")[0]
    if "/dp/" in u:
        m=re.search(r'/dp/([A-Z0-9]{10})', u, re.I)
        if m: return f"https://www.amazon.co.uk/dp/{m.group(1)}"
    parsed=urlparse(u)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

def get_products(url, base):
    headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=25)
        if r.status_code!=200 or len(r.text)<2000:
            r = requests.get(f"https://api.allorigins.win/raw?url={requests.utils.quote(url, safe='')}", headers=headers, timeout=25)
        soup = BeautifulSoup(r.text, "lxml")
    except: return []

    found=[]
    # Look for product cards, not every <a>
    for card in soup.select("[class*=product], [class*=card], li, article")[:120]:
        a = card.find("a", href=True)
        if not a: continue
        title = card.get_text(" ", strip=True)
        # shorten title to actual product name
        m = re.search(r'(Pokemon.{0,80}?(Booster|ETB|Elite|Bundle|Tin|Box|Collection|151)[^£\n]{0,40})', title, re.I)
        if not m: continue
        clean_title = re.sub(r'\s+',' ', m.group(1)).strip()[:110]
        low=clean_title.lower()
        if "jigsaw" in low or "puzzle" in low: continue

        raw = urljoin(base, a["href"])
        clean = clean_url(raw)
        if "/search" in clean or len(clean)<20: continue
        if not any(x in clean for x in ["/products/","/product/","/p/","/dp/","/item/"]):
            continue

        # Price
        price="Check site"
        pm = re.search(r'£\s?\d+(?:\.\d{2})?', card.get_text(" ", strip=True))
        if pm: price=pm.group(0).replace(" ","")

        if clean not in [f["url"] for f in found]:
            found.append({"title":clean_title, "url":clean, "price":price})
        if len(found)>=6: break
    print(f" -> {len(found)} products")
    return found

SITES = [
    ("ChaosCards","https://www.chaoscards.co.uk/collections/pokemon-sealed-product","https://www.chaoscards.co.uk"),
    ("MagicMadhouse","https://magicmadhouse.co.uk/collections/pokemon-sealed-products","https://magicmadhouse.co.uk"),
    ("TotalCards","https://www.totalcards.net/collections/pokemon-sealed-products","https://www.totalcards.net"),
    ("TrollTrader","https://www.trolltradercards.com/collections/pokemon-sealed-product","https://www.trolltradercards.com"),
]

send_tg(f"🔎 Pokemon monitor started {'MANUAL RESET - will show all' if IS_MANUAL else ''}\n⏰ {datetime.now().strftime('%H:%M:%S')}")

all_found=[]
for name,surl,base in SITES:
    print(f"\nChecking {name}...")
    prods = get_products(surl, base)
    for p in prods:
        print(f"{p['price']} | {p['title']} | {p['url']}")
        if IS_MANUAL or p["url"] not in seen:
            all_found.append((name,p))

# Send ONE message per product so link is clickable (like your image)
for name,p in all_found[:12]:
    msg = f"🔥 {name}\n{p['title']}\n💷 {p['price']}\n\n🔗 {p['url']}"
    send_tg(msg)
    seen.add(p["url"])

json.dump({n:[] for n,_ in SITES}, open(FILE,"w"), indent=2)
json.dump(sorted(list(seen)), open(SEEN_FILE,"w"), indent=2)

send_tg(f"✅ Done\nFound: {len(all_found)}\nManual: {IS_MANUAL}")
