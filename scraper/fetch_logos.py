"""Скачивает логотипы банков в logos/<домен>.png (запускается в GitHub Actions)."""
import hashlib, io, os, re, sys, urllib.parse
import requests
from PIL import Image

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
OUT = "logos"
BOGUS = "nonexistent-domain-for-placeholder-check.example"

def domains():
    h = open("index.html", encoding="utf-8").read()
    block = re.search(r"const DOM=\[(.*?)\];", h, re.S).group(1)
    return sorted(set(re.findall(r'\["[^"]+","([\w.\-]+)"\]', block)))

def get(url, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=15, **kw)
        return r.content if r.status_code == 200 and r.content else None
    except Exception:
        return None

def sources(d):
    yield "gstatic", f"https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&url=https://{d}&size=128"
    yield "ddg", f"https://icons.duckduckgo.com/ip3/{d}.ico"
    yield "google-s2", f"https://www.google.com/s2/favicons?domain={d}&sz=128"

def site_icons(d):
    for host in (f"https://{d}/", f"https://www.{d}/"):
        try:
            r = requests.get(host, headers=UA, timeout=15)
        except Exception:
            continue
        if r.status_code != 200:
            continue
        urls = []
        for tag in re.findall(r"<link[^>]+>", r.text, re.I):
            if re.search(r'rel=["\'][^"\']*(apple-touch-icon|icon)', tag, re.I):
                m = re.search(r'href=["\']([^"\']+)', tag)
                if m and not m.group(1).lower().split("?")[0].endswith(".svg"):
                    pri = 0 if "apple-touch" in tag.lower() else 1
                    urls.append((pri, urllib.parse.urljoin(r.url, m.group(1))))
        for _, u in sorted(urls):
            yield "site", u
        yield "site", urllib.parse.urljoin(r.url, "/favicon.ico")
        return

def load(data):
    try:
        im = Image.open(io.BytesIO(data))
        if getattr(im, "n_frames", 1) > 1 and im.format == "ICO":
            sizes = im.info.get("sizes") or []
            if sizes:
                im.size = max(sizes)
        im = im.convert("RGBA")
        return im
    except Exception:
        return None

def main():
    os.makedirs(OUT, exist_ok=True)
    bogus = set()
    for name, url in sources(BOGUS):
        b = get(url)
        if b:
            bogus.add(hashlib.sha256(b).hexdigest())
    print("placeholders:", len(bogus))
    ok = 0
    for d in domains():
        best = None
        for name, url in list(sources(d)) + list(site_icons(d)):
            b = get(url)
            if not b or hashlib.sha256(b).hexdigest() in bogus:
                continue
            im = load(b)
            if not im:
                continue
            side = min(im.size)
            if side < 24:
                continue
            if best is None or side > best[0]:
                best = (side, name, im)
            if side >= 120:
                break
        if best:
            side, name, im = best
            im.thumbnail((128, 128), Image.LANCZOS)
            im.save(f"{OUT}/{d}.png", optimize=True)
            ok += 1
            print(f"OK   {d:28s} {name:10s} {side}px")
        else:
            print(f"FAIL {d}")
    print(f"saved {ok}")

if __name__ == "__main__":
    main()
