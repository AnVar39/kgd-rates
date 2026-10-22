// Курсы USD/EUR в Калининграде. Node 18+, без зависимостей: node server.js
const http = require('http'), fs = require('fs'), path = require('path');
const PORT = process.env.PORT || 3000, TTL = 15 * 60e3;
// [название, slug на ru.myfin.by]. Проверенные slug'и — первые 8; sberbank/vtb — предположение.
const BANKS = [["МТС Банк","mts-bank"],["Совкомбанк","sovcombank"],["Морской банк","maritime"],
  ["Россельхозбанк","rshb"],["Газпромбанк","gazprombank"],["Альфа-Банк","alfabank"],
  ["Банк Зенит","zenit"],["Банк Интеза","intesa"],["Сбербанк","sberbank"],["ВТБ","vtb"]];
const sleep = ms => new Promise(r => setTimeout(r, ms));
const get = async u => { const r = await fetch(u, { headers: { 'User-Agent': 'Mozilla/5.0 kgd-rates' }, signal: AbortSignal.timeout(15000) });
  if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); };
const num = s => parseFloat(String(s).replace(',', '.'));

async function loadCbr() {
  const j = JSON.parse(await get('https://www.cbr-xml-daily.ru/daily_json.js'));
  return { date: j.Date.slice(0, 10).split('-').reverse().join('.'), usd: j.Valute.USD.Value, eur: j.Valute.EUR.Value };
}
function parseBank(html, cbr) {
  const t = html.replace(/<(script|style)[\s\S]*?<\/\1>/g, ' ').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');
  const pick = (w, ref) => {
    const m = t.match(new RegExp(w + ' ([\\d.,]+) ([\\d.,]+)')); if (!m) return null;
    const b = num(m[1]), s = num(m[2]);
    return (b > 0 && b <= s && b > ref * .85 && s < ref * 1.2) ? [b, s] : null; // защита от кривого разбора
  };
  const u = pick('Доллар', cbr.usd), e = pick('Евро', cbr.eur);
  if (!u || !e) throw new Error('не удалось разобрать страницу');
  return { u, e };
}
let cache = { cbr: null, banks: [], updated: null, errors: [] }, busy = false;
async function refresh() {
  if (busy) return; busy = true; const errors = [];
  try {
    let cbr = cache.cbr; try { cbr = await loadCbr(); } catch (e) { errors.push('ЦБ: ' + e.message); }
    if (!cbr) throw new Error('нет курса ЦБ');
    const old = Object.fromEntries(cache.banks.map(b => [b.n, b])), banks = [];
    for (const [n, slug] of BANKS) {
      try {
        const r = parseBank(await get(`https://ru.myfin.by/bank/${slug}/currency/kaliningrad`), cbr);
        banks.push({ n, t: 'Банк', ...r, upd: new Date().toISOString(), src: 'myfin.by' });
      } catch (e) { errors.push(n + ': ' + e.message); if (old[n]) banks.push({ ...old[n], stale: true }); }
      await sleep(1500);
    }
    try { // обменники и ручные правки: manual.json
      for (const m of JSON.parse(fs.readFileSync(path.join(__dirname, 'manual.json'), 'utf8')))
        banks.push({ t: 'Обменник', src: 'вручную', ...m });
    } catch (e) { errors.push('manual.json: ' + e.message); }
    cache = { cbr, banks, updated: new Date().toISOString(), errors };
  } catch (e) { cache.errors = [e.message]; }
  busy = false;
}
refresh(); setInterval(refresh, TTL);

http.createServer((req, res) => {
  if (req.url.startsWith('/api/rates')) {
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify(cache));
  }
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  fs.createReadStream(path.join(__dirname, 'public', 'index.html')).pipe(res);
}).listen(PORT, () => console.log('http://localhost:' + PORT));
