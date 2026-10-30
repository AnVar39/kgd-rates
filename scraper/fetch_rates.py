"""Курсы ЦБ и банков Калининграда + адреса пунктов обмена -> data/rates.json (банки: ru.myfin.by)"""
import json, re, html, time, datetime as dt
import xml.etree.ElementTree as ET
import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept-Language": "ru-RU,ru;q=0.9"}
BASE = "https://ru.myfin.by"
CITY = "kaliningrad"
OUT = "data/rates.json"
SEEDS = ["alfabank", "gazprombank", "rshb", "tcs", "zenit", "intesa", "maritime", "energotransbank",
         "kamkombank", "transcapitalbank", "mts-bank", "sberbank", "vtb", "psb", "sovcombank"]
NAMES = {"alfabank": "Альфа-Банк", "gazprombank": "Газпромбанк", "rshb": "Россельхозбанк",
         "tcs": "Т-Банк", "zenit": "Банк Зенит", "intesa": "Банк Интеза", "maritime": "Морской банк",
         "energotransbank": "Энерготрансбанк", "kamkombank": "Камкомбанк",
         "transcapitalbank": "ТрансКапиталБанк", "mts-bank": "МТС Банк", "sberbank": "Сбербанк",
         "vtb": "ВТБ", "psb": "ПСБ", "sovcombank": "Совкомбанк"}

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
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

def parse_bank(page):
    """Возвращает (курсы банка, список пунктов обмена с адресами)."""
    res, branches = {}, []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [strip(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if len(cells) < 3:
            continue
        code = {"Доллар": "USD", "Евро": "EUR"}.get(cells[0])
        if code:
            if code not in res:
                b, s = num(cells[1]), num(cells[2])
                if b and s:
                    res[code] = {"buy": b, "sell": s}
        elif len(cells) >= 5 and re.search(r"Калининград|г\.", cells[0]):
            br = {"address": cells[0]}
            for cur, (i, j) in (("USD", (1, 2)), ("EUR", (3, 4))):
                b, s = num(cells[i]), num(cells[j])
                if b and s:
                    br[cur] = {"buy": b, "sell": s}
            if br not in branches:
                branches.append(br)
    return res, branches

def addresses_fallback(slug):
    """Если в таблице курсов адресов нет — берём список отделений банка."""
    try:
        r = requests.get(f"{BASE}/bank/{slug}/departments-list/{CITY}", headers=UA, timeout=30)
        if r.status_code != 200:
            return []
        out = []
        for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r.text, re.S):
            t = strip(c)
            if t.startswith("Калининград") and len(t) > 14 and t not in [o["address"] for o in out]:
                out.append({"address": t})
        return out[:30]
    except Exception:
        return []

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
            rates, branches = parse_bank(page)
            if rates:
                if not branches:
                    time.sleep(0.5)
                    branches = addresses_fallback(slug)
                banks[slug] = {"name": bank_name(slug, page), "branches": branches, **rates}
        except Exception as e:
            errors.append(f"{slug}: {e}")
        time.sleep(0.7)
    return list(banks.values())

def history():
    """Динамика курса ЦБ за ~13 месяцев -> словарь {USD: [[дата, курс]], EUR: ...}"""
    fmt = "%d/%m/%Y"
    end = dt.date.today() + dt.timedelta(days=1)
    start = end - dt.timedelta(days=400)
    out = {}
    for code, vid in (("USD", "R01235"), ("EUR", "R01239")):
        r = requests.get("https://www.cbr.ru/scripts/XML_dynamic.asp", headers=UA, timeout=30,
                         params={"date_req1": start.strftime(fmt), "date_req2": end.strftime(fmt), "VAL_NM_RQ": vid})
        if b"<ValCurs" not in r.content:
            raise ValueError(f"ЦБ вернул не XML (код {r.status_code}): {r.text[:60]!r}")
        pts = []
        for rec in ET.fromstring(r.content).findall("Record"):
            d = dt.datetime.strptime(rec.get("Date").replace("/", "."), "%d.%m.%Y").strftime("%Y-%m-%d")
            v = float(rec.findtext("Value").replace(",", ".")) / int(rec.findtext("Nominal"))
            pts.append([d, round(v, 4)])
        out[code] = pts
    return out

def append_today(cbr_now):
    """Запасной вариант: дописываем сегодняшний курс в уже накопленную историю."""
    try:
        h = json.load(open("data/history.json", encoding="utf-8"))
    except Exception:
        h = {"USD": [], "EUR": []}
    if cbr_now.get("date"):
        d = dt.datetime.strptime(cbr_now["date"], "%d.%m.%Y").strftime("%Y-%m-%d")
        for c in ("USD", "EUR"):
            if c in cbr_now and not any(p[0] == d for p in h.setdefault(c, [])):
                h[c].append([d, cbr_now[c]])
                h[c].sort()
    return h

def load_prev():
    try:
        return json.load(open(OUT, encoding="utf-8"))
    except Exception:
        return {}

def sane(banks, cbr_now, tol=0.15):
    """Отбрасываем явные ошибки парсинга: курс банка далеко от курса ЦБ или покупка > продажи."""
    out = []
    for b in banks:
        for c in ("USD", "EUR"):
            r, ref = b.get(c), cbr_now.get(c)
            if not r:
                continue
            bad = r["buy"] > r["sell"] * 1.02
            if ref:
                bad = bad or any(abs(r[k] - ref) / ref > tol for k in ("buy", "sell"))
            if bad:
                b.pop(c)
        if b.get("USD") or b.get("EUR"):
            out.append(b)
    return out

def main():
    prev = load_prev()
    data = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "cbr": {}, "banks": [], "errors": []}
    try:
        data["cbr"] = cbr()
    except Exception as e:
        data["errors"].append(f"cbr: {e}")
        data["cbr"] = prev.get("cbr", {})
    banks = sane(collect(data["errors"]), data["cbr"])
    if banks:
        data["banks"] = sorted(banks, key=lambda x: x["name"])
        data["banks_updated"] = data["updated"]
    else:
        data["errors"].append("банки не найдены — показаны последние сохранённые данные")
        data["banks"] = prev.get("banks", [])
        data["banks_updated"] = prev.get("banks_updated") or prev.get("updated")
    try:
        h = history()
    except Exception as e:
        data["errors"].append(f"history: {e}")
        h = append_today(data["cbr"])
    if h and all(h.values()):
        json.dump(h, open("data/history.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(data["errors"], len(data["banks"]), "банков")

if __name__ == "__main__":
    main()
