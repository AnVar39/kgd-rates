"""Курсы ЦБ и банков Калининграда -> data/rates.json (источник банков: ru.myfin.by)"""
import json, re, html, time, datetime as dt
import xml.etree.ElementTree as ET
import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept-Language": "ru-RU,ru;q=0.9"}
BASE = "https://ru.myfin.by"
CITY = "kaliningrad"
OUT = "data/rates.json"
SEEDS = ["alfabank", "gazprombank", "rshb", "tcs", "zenit", "intesa", "maritime",
         "kamkombank", "transcapitalbank", "mts-bank", "sberbank", "vtb", "psb", "sovcombank"]
NAMES = {"alfabank": "Альфа-Банк", "gazprombank": "Газпромбанк", "rshb": "Россельхозбанк",
         "tcs": "Т-Банк", "zenit": "Банк Зенит", "intesa": "Банк Интеза", "maritime": "Морской банк",
         "kamkombank": "Камкомбанк", "transcapitalbank": "ТрансКапиталБанк", "mts-bank": "МТС Банк",
         "sberbank": "Сбербанк", "vtb": "ВТБ", "psb": "ПСБ", "sovcombank": "Совкомбанк"}

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
        v = float(str(x).replace(",", ".").replace(" ", ""))
        return v if 30 < v < 200 else None
    except Exception:
        return None

def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()

def parse_bank(page):
    res = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [strip(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if len(cells) >= 3:
            code = {"Доллар": "USD", "Евро": "EUR"}.get(cells[0])
            if code and code not in res:
                b, s = num(cells[1]), num(cells[2])
                if b and s:
                    res[code] = {"buy": b, "sell": s}
    return res

def bank_name(slug, page):
    if slug in NAMES:
        return NAMES[slug]
    m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    t = strip(m.group(1)) if m else slug
    return re.sub(r"^Курсы валют в\s+|\s+в Калининграде.*$", "", t)

def collect(errors):
    queue, seen, banks = list(SEEDS), set(), {}
    while queue and len(seen) < 60:
        slug = queue.pop(0)
        if slug in seen:
            continue
        seen.add(slug)
        try:
            r = requests.get(f"{BASE}/bank/{slug}/currency/{CITY}", headers=UA, timeout=30)
            if r.status_code != 200:
                continue
            page = r.text
            for s in re.findall(rf"/bank/([\w-]+)/currency/{CITY}", page):
                if s not in seen:
                    queue.append(s)
            rates = parse_bank(page)
            if rates:
                banks[slug] = {"name": bank_name(slug, page), **rates}
        except Exception as e:
            errors.append(f"{slug}: {e}")
        time.sleep(0.7)
    return list(banks.values())

def main():
    data = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "cbr": {}, "banks": [], "errors": []}
    try:
        data["cbr"] = cbr()
    except Exception as e:
        data["errors"].append(f"cbr: {e}")
    data["banks"] = sorted(collect(data["errors"]), key=lambda x: x["name"])
    if not data["banks"]:
        data["errors"].append("банки не найдены — проверьте парсер")
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(data["errors"], len(data["banks"]), "банков")

if __name__ == "__main__":
    main()
