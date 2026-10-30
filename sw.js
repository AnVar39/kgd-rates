var C="compass-v18";
var F=["./","index.html","manifest.webmanifest","icon-192.png","icon-512.png","icon-maskable-512.png"];
var OPT=["tides-data.js"];
self.addEventListener("install",function(e){
  e.waitUntil(caches.open(C).then(function(c){
    var req=Promise.all(F.map(function(u){
      return fetch(new Request(u,{cache:"reload"})).then(function(r){if(!r.ok)throw new Error(u);return c.put(u,r)});
    }));
    var opt=Promise.all(OPT.map(function(u){
      return fetch(new Request(u,{cache:"reload"})).then(function(r){if(r.ok)return c.put(u,r)}).catch(function(){});
    }));
    return Promise.all([req,opt]);
  }));
  self.skipWaiting();
});
self.addEventListener("activate",function(e){
  e.waitUntil(caches.keys().then(function(k){return Promise.all(k.filter(function(x){return x!==C}).map(function(x){return caches.delete(x)}))}).then(function(){return self.clients.claim()}));
});
self.addEventListener("fetch",function(e){
  var r=e.request;
  if(r.method!=="GET"||new URL(r.url).origin!==self.location.origin)return;
  e.respondWith(caches.match(r,{ignoreSearch:true}).then(function(hit){
    var net=fetch(r).then(function(x){
      if(x&&x.ok){var cp=x.clone();caches.open(C).then(function(c){c.put(r,cp)})}
      return x;
    }).catch(function(){return null});
    if(hit){e.waitUntil(net);return hit}
    return net.then(function(x){return x||caches.match("index.html")});
  }));
});
