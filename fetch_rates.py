"""Собирает курсы ЦБ и банков/обменников Калининграда -> data/rates.json"""
import json, re, html, datetime as dt
import xml.etree.ElementTree as ET
import requests

UA = {"User-Agent": "Mozilla/5.0 (kgd-rates bot)"}
OUT = "data/rates.json"

def cbr():
    r = requests.get("https://www.cbr.ru/scripts/XML_daily.asp", headers=UA, timeout=30)
    root = ET.fromstring(r.content)
    res = {"date": root.get("Date")}
    for v in root.findall("Valute"):
        code = v.findtext("CharCode")
        if code in ("USD", "EUR"):
            res[code] = round(float(v.findtext("Value").replace(",", ".")) /
                              int(v.findtext("Nominal")), 4)
    return res

def num(x):
    try:
        return float(str(x).replace(",", ".").replace(" ", ""))
    except Exception:
        return None

def walk(o, found):
    """Ищем в любом JSON словари вида {name, buy, sell}."""
    if isinstance(o, dict):
        low = {k.lower(): v for k, v in o.items()}
        name = low.get("name") or low.get("title") or low.get("bankname")
        buy = num(low.get("buy") or low.get("bid"))
        sell = num(low.get("sell") or low.get("ask"))
        if isinstance(name, str) and buy and sell and 30 < buy < 200 and 30 < sell < 200:
            found.append({"name": name.strip(), "buy": buy, "sell": sell})
        for v in o.values():
            walk(v, found)
    elif isinstance(o, list):
        for v in o:
            walk(v, found)

def banki(cur):
    """banki.ru: наличные курсы по Калининграду. Парсер — best effort."""
    url = f"https://www.banki.ru/products/currency/cash/{cur.lower()}/kaliningrad/"
    page = requests.get(url, headers=UA, timeout=30).text
    blobs = re.findall(r'<script[^>]*type="application/(?:ld\+)?json"[^>]*>(.*?)</script>', page, re.S)
    blobs += [html.unescape(b) for b in re.findall(r'data-module-options=["\'](.*?)["\']', page, re.S)]
    found = []
    for b in blobs:
        try:
            walk(json.loads(b), found)
        except Exception:
            pass
    return list({f["name"]: f for f in found}.values())

def main():
    data = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "cbr": {}, "banks": [], "errors": []}
    try:
        data["cbr"] = cbr()
    except Exception as e:
        data["errors"].append(f"cbr: {e}")
    banks = {}
    for cur in ("USD", "EUR"):
        try:
            for b in banki(cur):
                banks.setdefault(b["name"], {"name": b["name"]})[cur] = {"buy": b["buy"], "sell": b["sell"]}
        except Exception as e:
            data["errors"].append(f"banki {cur}: {e}")
    data["banks"] = sorted(banks.values(), key=lambda x: x["name"])
    if not data["banks"]:
        data["errors"].append("банки не найдены — проверьте парсер")
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(data["errors"], len(data["banks"]), "банков")

if __name__ == "__main__":
    main()
