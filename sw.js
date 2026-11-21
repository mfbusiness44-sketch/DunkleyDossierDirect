const CACHE = 'bcll-202611092337';
const CORE = ['./', 'index.html', 'leaflet.js', 'bluemarble.jpg', 'places.json', 'places.geojson', 'roads.geojson', 'cities.json', 'towns.json', 'rd.geojson', 'rd_labels.json', 'fn.json', 'forest.geojson', 'news.json', 'apple-touch-icon.png'];
self.addEventListener('install', (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting())); });
self.addEventListener('activate', (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;
  const heavy = /\.(jpg|png|js)$/.test(u.pathname) && !u.pathname.endsWith('sw.js');
  if (heavy) {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => { const c = r.clone(); caches.open(CACHE).then((x) => x.put(e.request, c)); return r; })));
  } else {
    e.respondWith(fetch(e.request).then((r) => { const c = r.clone(); caches.open(CACHE).then((x) => x.put(e.request, c)); return r; }).catch(() => caches.match(e.request, { ignoreSearch: true })));
  }
});
