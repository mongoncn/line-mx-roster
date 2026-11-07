/* 排班表 Service Worker：页面壳离线可开，接口永不缓存 */
const CACHE = "ss-shell-v1";
const SHELL = ["/", "/index.html", "/icon-64.png", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png", "/favicon.ico", "/manifest.webmanifest"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;   // 数据一律走网络，不缓存

  // 页面导航：网络优先，断网回落到缓存壳
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req).then(res => {
        const cp = res.clone();
        caches.open(CACHE).then(c => c.put("/index.html", cp));
        return res;
      }).catch(() => caches.match("/index.html").then(r => r || caches.match("/")))
    );
    return;
  }

  // 静态资源：缓存优先，未命中再取网络
  e.respondWith(
    caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok) {
        const cp = res.clone();
        caches.open(CACHE).then(c => c.put(req, cp));
      }
      return res;
    }))
  );
});
