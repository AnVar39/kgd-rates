// Живые курсы: ЦБ РФ + банки Калининграда (источник: ru.myfin.by). Формат ответа = data/rates.json
const BASE = "https://ru.myfin.by";
const CITY = "kaliningrad";
const CACHE_SEC = 120;
const MAX_PAGES = 36;
const UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36";
const SEEDS = ["alfabank", "gazprombank", "rshb", "tcs", "zenit", "intesa", "maritime", "energotransbank",
  "kamkombank", "transcapitalbank", "mts-bank", "sberbank", "vtb", "psb", "sovcombank"];
const NAMES = { alfabank: "Альфа-Банк", gazprombank: "Газпромбанк", rshb: "Россельхозбанк", tcs: "Т-Банк",
  zenit: "Банк Зенит", intesa: "Банк Интеза", maritime: "Морской банк", energotransbank: "Энерготрансбанк",
  kamkombank: "Камкомбанк", transcapitalbank: "ТрансКапиталБанк", "mts-bank": "МТС Банк", sberbank: "Сбербанк",
  vtb: "ВТБ", psb: "ПСБ", sovcombank: "Совкомбанк" };
const NAME_FIX = { "Райффайзенбанке": "Райффайзенбанк", "Росбанке": "Росбанк", "Открытии": "Открытие" };
const CORS = { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, OPTIONS" };

const unent = (s) => s.replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&quot;/g, '"')
  .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n));
export const strip = (s) => unent(s.replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
export const num = (x) => {
  const v = parseFloat(String(x).replace(",", ".").replace(/\s/g, ""));
  return v > 30 && v < 200 ? v : null;
};

export function parseCbr(xml) {
  const out = { date: (xml.match(/<ValCurs[^>]*Date="([^"]+)"/) || [])[1] };
  for (const m of xml.matchAll(/<Valute[\s\S]*?<\/Valute>/g)) {
    const b = m[0];
    const code = (b.match(/<CharCode>(\w+)<\/CharCode>/) || [])[1];
    if (code !== "USD" && code !== "EUR") continue;
    const nom = parseInt((b.match(/<Nominal>(\d+)<\/Nominal>/) || [])[1] || "1", 10);
    const val = parseFloat(((b.match(/<Value>([\d,]+)<\/Value>/) || [])[1] || "").replace(",", "."));
    if (val) out[code] = Math.round((val / nom) * 1e4) / 1e4;
  }
  return out;
}

export function parseBank(page) {
  const rates = {}, branches = [];
  for (const row of page.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
    const cells = [...row[1].matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/g)].map((c) => strip(c[1]));
    if (cells.length < 3) continue;
    const code = { "Доллар": "USD", "Евро": "EUR" }[cells[0]];
    if (code) {
      if (!rates[code]) {
        const b = num(cells[1]), s = num(cells[2]);
        if (b && s) rates[code] = { buy: b, sell: s };
      }
    } else if (cells.length >= 5 && /Калининград|г\./.test(cells[0])) {
      const br = { address: cells[0] };
      for (const [cur, i, j] of [["USD", 1, 2], ["EUR", 3, 4]]) {
        const b = num(cells[i]), s = num(cells[j]);
        if (b && s) br[cur] = { buy: b, sell: s };
      }
      if (!branches.some((x) => x.address === br.address)) branches.push(br);
    }
  }
  return { rates, branches };
}

function bankName(slug, page) {
  if (NAMES[slug]) return NAMES[slug];
  const m = page.match(/<h1[^>]*>([\s\S]*?)<\/h1>/);
  let t = m ? strip(m[1]) : slug;
  t = t.replace(/^Курсы валют в\s+/, "").replace(/\s+в Калининграде.*$/, "");
  return NAME_FIX[t] || t;
}

export function sane(banks, cbr) {
  const out = [];
  for (const b of banks) {
    for (const c of ["USD", "EUR"]) {
      const r = b[c], ref = cbr[c];
      if (!r) continue;
      let bad = r.buy > r.sell * 1.02;
      if (ref) bad = bad || ["buy", "sell"].some((k) => Math.abs(r[k] - ref) / ref > 0.15);
      if (bad) delete b[c];
    }
    if (b.USD || b.EUR) out.push(b);
  }
  return out;
}

async function get(url, ms = 8000) {
  const r = await fetch(url, { headers: { "user-agent": UA, "accept-language": "ru-RU,ru;q=0.9" },
    signal: AbortSignal.timeout(ms) });
  if (!r.ok) throw new Error("HTTP " + r.status + " " + url);
  return r.text();
}

export async function collect(errors) {
  const banks = new Map(), seen = new Set();
  let queue = [...SEEDS];
  while (queue.length && seen.size < MAX_PAGES) {
    const batch = queue.filter((s) => !seen.has(s)).slice(0, MAX_PAGES - seen.size);
    queue = [];
    batch.forEach((s) => seen.add(s));
    const res = await Promise.allSettled(batch.map((s) => get(`${BASE}/bank/${s}/currency/${CITY}`)));
    res.forEach((r, i) => {
      const slug = batch[i];
      if (r.status !== "fulfilled") { errors.push(`${slug}: ${r.reason && r.reason.message || r.reason}`); return; }
      const page = r.value;
      for (const m of page.matchAll(new RegExp(`/bank/([\\w-]+)/currency/${CITY}`, "g")))
        if (!seen.has(m[1]) && !queue.includes(m[1])) queue.push(m[1]);
      const { rates, branches } = parseBank(page);
      if (rates.USD || rates.EUR) banks.set(slug, { name: bankName(slug, page), branches, ...rates });
    });
  }
  return [...banks.values()];
}

async function build() {
  const now = new Date().toISOString();
  const data = { updated: now, banks_updated: now, live: true, cbr: {}, banks: [], errors: [] };
  const [c, b] = await Promise.allSettled([
    get("https://www.cbr.ru/scripts/XML_daily.asp").then(parseCbr),
    collect(data.errors),
  ]);
  if (c.status === "fulfilled") data.cbr = c.value; else data.errors.push("cbr: " + c.reason);
  if (b.status === "fulfilled") data.banks = sane(b.value, data.cbr).sort((x, y) => x.name.localeCompare(y.name, "ru"));
  if (!data.banks.length) throw new Error("банки не найдены: " + data.errors.slice(0, 3).join("; "));
  if (!data.cbr.USD) throw new Error("курс ЦБ недоступен");
  return data;
}

export default {
  async fetch(req, env, ctx) {
    if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
    const cache = caches.default;
    const key = new Request(new URL("/rates", req.url).toString());
    const hit = await cache.match(key);
    if (hit) return new Response(hit.body, { headers: { ...Object.fromEntries(hit.headers), ...CORS, "x-cache": "HIT" } });
    try {
      const body = JSON.stringify(await build());
      const res = new Response(body, { headers: { "content-type": "application/json; charset=utf-8",
        "cache-control": `public, max-age=${CACHE_SEC}` } });
      ctx.waitUntil(cache.put(key, res.clone()));
      return new Response(body, { headers: { "content-type": "application/json; charset=utf-8", ...CORS, "x-cache": "MISS" } });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e.message || e) }),
        { status: 502, headers: { "content-type": "application/json; charset=utf-8", ...CORS } });
    }
  },
};
