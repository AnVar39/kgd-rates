const C="kgd-v17",SHELL=["./","index.html","coat.png","manifest.webmanifest"];
self.addEventListener("install",e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(SHELL)));self.skipWaiting()});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))));self.clients.claim()});
const netFirst=e=>e.respondWith(fetch(e.request).then(r=>{if(r.ok){const c=r.clone();caches.open(C).then(x=>x.put(e.request,c))}return r}).catch(()=>caches.match(e.request)));
self.addEventListener("fetch",e=>{
  if(e.request.method!=="GET")return;
  const u=new URL(e.request.url);
  if(u.origin!==location.origin)return;
  if(e.request.mode==="navigate"||u.pathname.includes("/data/")||u.pathname.endsWith("/index.html")||u.pathname.endsWith("/sw.js"))return netFirst(e);
  e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));
});
