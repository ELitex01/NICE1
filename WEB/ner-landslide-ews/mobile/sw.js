const CACHE = "ner-ews-v1";
const STATIC = ["/", "/index.html", "/app.js", "/db.js", "/manifest.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)));
  self.skipWaiting();
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then(cached =>
      cached || fetch(e.request).then(r => {
        if (r.ok && e.request.url.includes("/api/districts/risk")) {
          // cache latest risk for offline viewing
          const clone = r.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return r;
      }).catch(() => cached)   // fall back to cache when offline
    )
  );
});

// Background sync for queued reports
self.addEventListener("sync", e => {
  if (e.tag === "sync-reports") e.waitUntil(syncReports());
});

async function syncReports() {
  const db = await openDB();
  const pending = await getAllPending(db);
  for (const rep of pending) {
    try {
      const r = await fetch("/api/reports", {
        method: "POST",
        headers: {"Content-Type": "application/json",
                  Authorization: `Bearer ${localStorage.getItem("jwt")}`},
        body: JSON.stringify(rep),
      });
      if (r.ok) await markSynced(db, rep.id);
    } catch(e) { /* still offline — retry next sync */ }
  }
}