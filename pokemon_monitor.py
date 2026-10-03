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
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id":CHAT,"text":text[:3800],"disable_web_page_preview": not with_image,"parse_mode":"HTML"}, timeout=15)
    except Exception as e:
        print(f"TG fail {e}", flush=True)

def clean(u): return u.split("?")[0].split("#")[0].rstrip("/")

def scrape_one(site):
    name, url, base = site
    try:
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=12)
        if r.status_code!=200:
            print(f"{name} HTTP {r.status_code}", flush=True)
            return name, []
        soup = BeautifulSoup(r.text, "lxml")
        found=[]
        for card in soup.select(".product-item,.product-card,.grid__item,li,article")[:150]:
            a=card.find("a", href=True)
            if not a: continue
            title=card.get_text(" ",strip=True)
            if len(title)<25 or "pokemon" not in title.lower(): continue
            raw=urljoin(base,a["href"])
            curl=clean(raw)
            if "/products/" not in curl and "/product/" not in curl and "/p/" not in curl: continue
            price="N/A"
            for sel in [".price",".money",".product__price",".product-price",".price__current"]:
                el=card.select_one(sel)
                if el:
                    m=re.search(r'£\s?\d+(?:\.\d{2})?', el.get_text())
                    if m: price=m.group(0).replace(" ",""); break
            if price=="N/A":
                m=re.search(r'£\s?\d+(?:\.\d{2})?', card.get_text())
                if m: price=m.group(0).replace(" ","")
            if curl not in [x["url"] for x in found]:
                found.append({"title":title[:120],"url":curl,"price":price})
            if len(found)>=5: break
        print(f"{name}: {len(found)}", flush=True)
        return name, found
    except Exception as e:
