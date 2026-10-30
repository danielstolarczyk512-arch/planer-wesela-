const VERSION='nd-film-v86-shell-1';
const SHELL=['/','/index.html','/style.css','/app.js','/favicon.svg','/manifest.json'];
self.addEventListener('install',e=>e.waitUntil(caches.open(VERSION).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(u.origin!==location.origin||u.pathname.startsWith('/api/'))return;e.respondWith(fetch(e.request).then(r=>{if(r.ok)caches.open(VERSION).then(c=>c.put(e.request,r.clone()));return r}).catch(()=>caches.match(e.request)))});
