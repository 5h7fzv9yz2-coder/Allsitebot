import requests, os, re, json, sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN = os.environ.get("TELEGRAM_TOKEN","").strip()
CHAT = os.environ.get("TELEGRAM_CHAT","").strip()
IS_MANUAL = "--reset" in sys.argv or os.environ.get("GITHUB_EVENT_NAME")=="workflow_dispatch"

KEYWORDS = ["booster","etb","elite trainer","30th","upc","bundle","mini tin","ultra premium"]

def send_tg(text, with_image=False):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT, "text": text[:3800], "disable_web_page_preview": not with_image, "parse_mode": "HTML"},
            timeout=15
        )
    except Exception as ex:
        print(f"TG fail {ex}", flush=True)

def clean(u):
    return u.split("?")[0].split("#")[0].rstrip("/")

def scrape_one(site):
    name, url, base = site
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=12)
        if r.status_code!= 200:
            print(f"{name} HTTP {r.status_code}", flush=True)
            return name, []
        soup = BeautifulSoup(r.text, "lxml")
        found = []
        for card in soup.select(".product-item,.product-card,.grid__item,li,article")[:150]:
            a = card.find("a", href=True)
            if not a:
                continue
            title = card.get_text(" ", strip=True)
            if len(title) < 25 or "pokemon" not in title.lower():
                continue
            raw = urljoin(base, a["href"])
            curl = clean(raw)
            if "/products/" not in curl and "/product/" not in curl and "/p/" not in curl:
                continue
            price = "N/A"
            m = re.search(r'£\s?\d+(?:\.\d{2})?', card.get_text())
            if m:
                price = m.group(0).replace(" ","")
            if curl not in [x["url"] for x in found]:
                found.append({"title": title[:120], "url": curl, "price": price})
            if len(found) >= 5:
                break
        print(f"{name}: {len(found)}", flush=True)
        return name, found
    except Exception as e:
        print(f"{name} fail {e}", flush=True)
        return name, []

SITES = [
    ("ChaosCards","https://www.chaoscards.co.uk/collections/pokemon-sealed-product","https://www.chaoscards.co.uk"),
    ("MagicMadhouse","https://magicmadhouse.co.uk/collections/pokemon-sealed-products","https://magicmadhouse.co.uk"),
    ("TotalCards","https://www.totalcards.net/collections/pokemon-sealed-products","https://www.totalcards.net"),
    ("TitanCards","https://www.titancards.co.uk/collections/pokemon-sealed-product","https://www.titancards.co.uk"),
    ("SnK Gaming","https://snkgaming.co.uk/collections/pokemon-sealed-products","https://snkgaming.co.uk"),
    ("NeoCards","https://www.neocards.co.uk/collections/pokemon-sealed-products","https://www.neocards.co.uk"),
    ("GatheringGames","https://gatheringgames.uk/collections/pokemon-sealed","https://gatheringgames.uk"),
    ("BBSTCG","https://www.bbstcg.co.uk/collections/pokemon-sealed-products","https://www.bbstcg.co.uk"),
    ("TCG House","https://www.tcg-house.co.uk/collections/pokemon-sealed-products","https://www.tcg-house.co.uk"),
    ("Geek-Aboo","https://geek-aboo.com/collections/pokemon-sealed-product","https://geek-aboo.com"),
    ("UnderdogCards","https://underdogcards.co.uk/collections/pokemon-sealed-products","https://underdogcards.co.uk"),
    ("TheCardVault","https://thecardvault.co.uk/collections/pokemon-sealed","https://thecardvault.co.uk"),
    ("PokeGeeks","https://pokegeeks.co.uk/collections/pokemon-sealed-products","https://pokegeeks.co.uk"),
    ("GameCentre","https://www.game-centre.co.uk/collections/pokemon-sealed","https://www.game-centre.co.uk"),
    ("MagicAndMonsters","https://magicandmonsters.co.uk/collections/pokemon-sealed","https://magicandmonsters.co.uk"),
    ("DiceAndDecks","https://diceanddecks.co.uk/collections/pokemon-sealed","https://diceanddecks.co.uk"),
    ("TrollTrader","https://www.trolltradercards.co.uk/collections/pokemon-sealed","https://www.trolltradercards.co.uk"),
    ("TotalCards Boxes","https://www.totalcards.net/collections/pokemon-booster-boxes","https://www.totalcards.net"),
    ("ChaosCards ETB","https://www.chaoscards.co.uk/collections/pokemon-elite-trainer-boxes","https://www.chaoscards.co.uk"),
    ("MagicMadhouse ETB","https://magicmadhouse.co.uk/collections/pokemon-elite-trainer-boxes","https://magicmadhouse.co.uk"),
    ("SmythsToys","https://www.smythstoys.com/uk/en-gb/c/toys/pokemon/cards/","https://www.smythstoys.com"),
    ("GAME UK","https://www.game.co.uk/en/m/toys/pokemon-trading-card-game/","https://www.game.co.uk"),
    ("ShopTo","https://www.shopto.net/en/search/?s=Pokemon+booster","https://www.shopto.net"),
    ("365Games","https://www.365games.co.uk/search?q=pokemon+sealed","https://www.365games.co.uk"),
    ("LittleShopMagic","https://www.thelittleshopofmagic.co.uk/collections/pokemon-sealed","https://www.thelittleshopofmagic.co.uk"),
    ("PokeChamp","https://pokechamp.co.uk/collections/pokemon-sealed-product","https://pokechamp.co.uk"),
    ("PokeMole","https://pokemole.co.uk/collections/pokemon-sealed-products","https://pokemole.co.uk"),
    ("CardMarket","https://www.cardmarket.com/en/Pokemon/Products/Booster-Boxes","https://www.cardmarket.com"),
    ("PokemonCenter","https://www.pokemoncenter.com/en-gb/category/trading-card-game","https://www.pokemoncenter.com"),
    ("Argos","https://www.argos.co.uk/search/pokemon-cards/","https://www.argos.co.uk"),
]

is_first_run = IS_MANUAL or not os.path.exists("seen_products.json")
if is_first_run:
    seen = set()
else:
    seen = set(json.load(open("seen_products.json"))) if os.path.exists("seen_products.json") else set()

send_tg(f"Scanning 30 sites {'FIRST RUN' if is_first_run else 'auto'} {datetime.now().strftime('%H:%M')}")

all_results = []
with ThreadPoolExecutor(max_workers=10) as ex:
    futures = {ex.submit(scrape_one, s): s for s in SITES}
    for f in as_completed(futures):
        name, prods = f.result()
        for p in prods:
            low = p["title"].lower()
            if not any(k in low for k in KEYWORDS):
                continue
            if p["price"] == "N/A":
                continue
            if "simplified chinese" in low or "plush" in low or "japanese" in low:
                continue
            if p["url"] in seen and not is_first_run:
                continue
            all_results.append((name, p))

to_send = all_results if is_first_run else [x for x in all_results if x[1]["url"] not in seen]
print(f"FIRST={is_first_run} TOTAL={len(all_results)} TO_SEND={len(to_send)}", flush=True)

for name, p in to_send[:30]:
    msg = f"<b>{name}</b>\n{p['title']}\n\nRetail: <b>{p['price']}</b>\n{p['url']}"
    send_tg(msg, with_image=True)
    seen.add(p["url"])

open("seen_products.json","w").write(json.dumps(sorted(list(seen)), indent=2))
send_tg(f"Done. First={is_first_run} Sent:{len(to_send)} Found:{len(all_results)}/30", with_image=False)
