import requests
import json
import os
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT = os.environ["TELEGRAM_CHAT"]

FILE = "last_products.json"
SEEN_FILE = "seen_products.json"

KEYWORDS = [
    "booster",
    "etb",
    "elite trainer",
    "bundle",
    "30th",
    "pokeball",
    "mini tin"
]

# ============================================================
# TELEGRAM
# ============================================================

def send_tg(text):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT,
                "text": text[:3800],
                "disable_web_page_preview": False
            },
            timeout=15
        )

        if not response.ok:
            print(f"Telegram error: {response.status_code} {response.text}")

    except Exception as e:
        print(f"Telegram exception: {e}")


# ============================================================
# URL CLEANING
# ============================================================

def clean_url(dirty_url):

    # Remove tracking/query fragments
    dirty_url = dirty_url.split(";")[0]
    dirty_url = dirty_url.split("?")[0]
    dirty_url = dirty_url.split("#")[0]

    # Amazon -> direct ASIN URL
    if "amazon" in dirty_url.lower():

        m = re.search(r'/dp/([A-Z0-9]{10})', dirty_url, re.I)

        if m:
            return f"https://www.amazon.co.uk/dp/{m.group(1)}"

        m = re.search(r'/product/([A-Z0-9]{10})', dirty_url, re.I)

        if m:
            return f"https://www.amazon.co.uk/dp/{m.group(1)}"

    # Other sites
    parsed = urlparse(dirty_url)

    path = re.sub(r'//+', '/', parsed.path)

    clean = f"{parsed.scheme}://{parsed.netloc}{path}"

    return clean.rstrip("/")


# ============================================================
# PRODUCT SCRAPER
# ============================================================

def get_products(url, base):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        r = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        print(f"HTTP {r.status_code}: {url}")

        if len(r.text) < 4000:
            return []

        soup = BeautifulSoup(r.text, "lxml")

    except Exception as e:
        print(f"Request failed: {e}")
        return []

    found = []
    found_urls = set()

    for a in soup.find_all("a", href=True, limit=700):

        title = a.get_text(" ", strip=True)

        if len(title) < 10 or len(title) > 180:
            continue

        low = title.lower()

        # Must contain Pokemon
        if "pokemon" not in low and "pokémon" not in low:
            continue

        # Must contain one of our product keywords
        if not any(k in low for k in KEYWORDS):
            continue

        # Ignore navigation/legal text
        if any(
            x in low
            for x in [
                "cookie",
                "privacy",
                "filter",
                "wishlist"
            ]
        ):
            continue

        raw = urljoin(base, a["href"])

        clean = clean_url(raw)

        if clean in found_urls:
            continue

        if len(clean) < 20:
            continue

        # Ignore search/category/blog pages
        if any(
            x in clean.lower()
            for x in [
                "/search",
                "/collections/",
                "/blogs/"
            ]
        ):
            continue

        # ====================================================
        # FIND PRICE
        # ====================================================

        price = "N/A"

        p = a

        for _ in range(4):

            if not p or not p.parent:
                break

            p = p.parent

            txt = p.get_text(
                " ",
                strip=True
            )[:600]

            m = re.search(
                r'£\s?\d+(?:\.\d{1,2})?',
                txt
            )

            if m:
                price = m.group(0)
                break

        found.append({
            "title": title,
            "url": clean,
            "price": price
        })

        found_urls.add(clean)

        # Limit alerts/results per site
        if len(found) >= 6:
            break

    return found


# ============================================================
# SITES
# ============================================================

SITES = [

    (
        "PokemonCenter",
        "https://www.pokemoncenter.com/en-gb/search?q=pokemon",
        "https://www.pokemoncenter.com"
    ),

    (
        "AmazonUK",
        "https://www.amazon.co.uk/s?k=pokemon+booster+etb+bundle",
        "https://www.amazon.co.uk"
    ),

    (
        "Smyths",
        "https://www.smythstoys.com/uk/en-gb/search?q=pokemon",
        "https://www.smythstoys.com"
    ),

    (
        "Argos",
        "https://www.argos.co.uk/search/pokemon/",
        "https://www.argos.co.uk"
    ),

    (
        "JohnLewis",
        "https://www.johnlewis.com/search?search-term=pokemon",
        "https://www.johnlewis.com"
    ),

    (
        "GAME",
        "https://www.game.co.uk/en/search/?sSearch=pokemon",
        "https://www.game.co.uk"
    ),

    (
        "Very",
        "https://www.very.co.uk/e/q-end-pokemon?q=pokemon",
        "https://www.very.co.uk"
    ),

    (
        "Zavvi",
        "https://www.zavvi.com/search/pokemon/",
        "https://www.zavvi.com"
    ),

    (
        "ShopTo",
        "https://www.shopto.net/en/search/?s=pokemon",
        "https://www.shopto.net"
    ),

    (
        "365Games",
        "https://www.365games.co.uk/search/pokemon",
        "https://www.365games.co.uk"
    ),

    (
        "TheWorks",
        "https://www.theworks.co.uk/search?qsearch=pokemon",
        "https://www.theworks.co.uk"
    ),

    (
        "TGJones",
        "https://www.tgjones.co.uk/search?q=pokemon",
        "https://www.tgjones.co.uk"
    ),

    (
        "ChaosCards",
        "https://www.chaoscards.co.uk/search/pok",
        "https://www.chaoscards.co.uk"
    ),

    (
        "MagicMadhouse",
        "https://magicmadhouse.co.uk/search?q=pokemon",
        "https://magicmadhouse.co.uk"
    ),

    (
        "TotalCards",
        "https://www.totalcards.net/search?type=product&q=pokemon",
        "https://www.totalcards.net"
    ),

    (
        "ForbiddenPlanet",
        "https://forbiddenplanet.com/search/?q=pokemon",
        "https://forbiddenplanet.com"
    ),

    (
        "TheGameCollection",
        "https://www.thegamecollection.net/search/pok",
        "https://www.thegamecollection.net"
    ),

    (
        "Base",
        "https://www.base.com/search?q=pokemon",
        "https://www.base.com"
    ),

    (
        "OnBuy",
        "https://www.onbuy.com/gb/search/?query=pokemon",
        "https://www.onbuy.com"
    ),

    (
        "Zatu",
        "https://www.board-game.co.uk/?s=pokemon",
        "https://www.board-game.co.uk"
    ),

    (
        "ElementGames",
        "https://elementgames.co.uk/search?search=pokemon",
        "https://elementgames.co.uk"
    ),

    (
        "Wayland",
        "https://www.waylandgames.co.uk/search?qsearch=pokemon",
        "https://www.waylandgames.co.uk"
    ),

    (
        "Firestorm",
        "https://www.firestormcards.co.uk/search/pokemon",
        "https://www.firestormcards.co.uk"
    ),

    (
        "Sneak",
        "https://www.sneakattackgames.co.uk/search?q=pokemon",
        "https://www.sneakattackgames.co.uk"
    ),

    (
        "TrollTrader",
        "https://www.trolltradercards.com/search?q=pokemon",
        "https://www.trolltradercards.com"
    ),

    (
        "AxionNow",
        "https://axionnow.com/?s=pokemon&post_type=product",
        "https://axionnow.com"
    ),

    (
        "NinNin",
        "https://www.nin-nin-game.com/en/search?controller=search&s=pokemon",
        "https://www.nin-nin-game.com"
    ),

    (
        "MagicTricks",
        "https://www.magictricks.co.uk/search/pokemon/",
        "https://www.magictricks.co.uk"
    ),

    (
        "ToysForABaby",
        "https://www.toysforababy.co.uk/search?type=product&q=pokemon",
        "https://www.toysforababy.co.uk"
    ),

    (
        "ShopPokemonUK",
        "https://www.shop4pokemon.co.uk/search?q=pokemon",
        "https://www.shop4pokemon.co.uk"
    )
]


# ============================================================
# LOAD HISTORY
# ============================================================

def load_json(filename, default):

    if not os.path.exists(filename):
        return default

    try:

        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as e:

        print(f"Could not load {filename}: {e}")

        return default


last = load_json(FILE, {})
seen = load_json(SEEN_FILE, [])

seen = set(seen)

is_first = len(seen) == 0

print("=" * 60)
print("POKEMON STOCK MONITOR")
print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print(f"First run: {is_first}")
print(f"Previously seen products: {len(seen)}")
print("=" * 60)


# ============================================================
# START MESSAGE
# ============================================================

send_tg(
    "🔎 Pokemon stock monitor started\n"
    f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
    f"🏪 Checking {len(SITES)} stores"
)


# ============================================================
# CHECK ALL SITES
# ============================================================

total_found = 0
total_new = 0

for name, surl, base in SITES:

    try:

        print(
            f"\n[{datetime.now().strftime('%H:%M:%S')}] "
            f"Checking {name}..."
        )

        prods = get_products(
            surl,
            base
        )

        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"{name}: {len(prods)} matches"
        )

        if not prods:
            continue

        total_found += len(prods)

        # Save latest results for this store
        last[name] = prods

        # ====================================================
        # FIRST RUN
        # ====================================================

        if is_first:

            msg = (
                f"🔥 {name} FOUND "
                f"{len(prods)}\n"
            )

            for p in prods:

                msg += (
                    f"\n• {p['title'][:65]}\n"
                    f"💷 {p['price']}\n"
                    f"{p['url']}\n"
                )

                seen.add(p["url"])

                total_new += 1

            send_tg(msg)

        # ====================================================
        # SUBSEQUENT RUNS
        # ====================================================

        else:

            new_items = [
                p
                for p in prods
                if p["url"] not in seen
            ]

            if new_items:

                msg = (
                    f"🚨 NEW at {name}\n"
                    f"Found {len(new_items)} new product(s)\n"
                )

                for p in new_items:

                    msg += (
                        f"\n• {p['title'][:65]}\n"
                        f"💷 {p['price']}\n"
                        f"{p['url']}\n"
                    )

                    seen.add(p["url"])

                    total_new += 1

                send_tg(msg)

    except Exception as e:

        print(
            f"ERROR checking {name}: {e}"
        )


# ============================================================
# SAVE HISTORY
# ============================================================

try:

    with open(
        FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            last,
            f,
            indent=2,
            ensure_ascii=False
        )

    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            sorted(seen),
            f,
            indent=2,
            ensure_ascii=False
        )

except Exception as e:

    print(f"Could not save history: {e}")


# ============================================================
# FINISHED
# ============================================================

print("\n" + "=" * 60)
print("SCAN COMPLETE")
print(f"Products found: {total_found}")
print(f"New products: {total_new}")
print(f"Total remembered products: {len(seen)}")
print("=" * 60)

send_tg(
    "✅ Pokemon stock scan complete\n"
    f"🏪 Stores checked: {len(SITES)}\n"
    f"🔎 Matches found: {total_found}\n"
    f"🚨 New products: {total_new}\n"
    f"⏰ {datetime.now().strftime('%H:%M:%S')}"
)
