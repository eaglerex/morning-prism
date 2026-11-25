// 모닝 프리즘 서비스 워커: 앱 화면을 기기에 저장해 오프라인(지하철)에서도 열리게 합니다.
const CACHE = "morning-prism-v8";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE && k !== "morning-prism-audio").map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
// 네트워크 우선, 실패하면 저장본 사용 (새 버전이 올라가면 자동 반영)
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;
  if (new URL(e.request.url).pathname.includes("/audio/")) { // 암호화된 음성 파일: 별도 보관(지하철 오프라인용), 오래된 것은 정리
    e.respondWith(
      fetch(e.request).then((r) => { if (r.ok) { const c2 = r.clone(); caches.open("morning-prism-audio").then(async (c) => { await c.put(e.request, c2); const ks = await c.keys(); for (const k of ks.slice(0, Math.max(0, ks.length - 16))) await c.delete(k); }); } return r; })
        .catch(() => caches.match(e.request, { cacheName: "morning-prism-audio" }))
    );
    return;
  }
  e.respondWith(
    fetch(e.request).then((r) => { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); return r; })
      .catch(() => caches.match(e.request).then((m) => m || caches.match("./index.html")))
  );
});
