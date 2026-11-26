/* Service Worker：只缓存应用壳。
 *
 * 驾驶靠 /ws，永远不经过这里；离线时页面只是能打开、能看上次状态。
 * 版本号改一次，activate 就清掉旧缓存 —— 上线新页面时只改 VERSION。
 */
const VERSION = 'duckphone-v7';
const SHELL = [
  '/',
  '/index.html',
  '/app.js',
  '/app.js?v=7',
  '/style.css',
  '/style.css?v=7',
  '/manifest.webmanifest',
  '/icon.svg',
  '/icon-192.png',
  '/icon-512.png',
  '/help.html',
];

// 逐个 add 而不是 addAll：addAll 是全有全无，一个 404 就整份壳缓存为空，
// 表现是"离线打不开页面"，而且日志里看不出来是哪一个文件惹的。
async function precache() {
  const cache = await caches.open(VERSION);
  await Promise.all(SHELL.map(async (url) => {
    try {
      await cache.add(new Request(url, { cache: 'reload' }));
    } catch (_) {
      /* 单个文件失败不该拖垮整壳；下次在线访问会由 fetch 处理器补上 */
    }
  }));
}

self.addEventListener('install', (event) => {
  event.waitUntil(precache().then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.t === 'skip-waiting') self.skipWaiting();
  if (event.data && event.data.t === 'precache') event.waitUntil(precache());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  // 实时的东西一个都不缓存：状态流、停止 beacon、诊断
  if (url.pathname === '/ws' || url.pathname === '/stop'
    || url.pathname === '/api/status' || url.pathname === '/healthz') return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/').then((hit) => hit || Response.error())),
    );
    return;
  }

  // 网络优先，缓存兜底。局域网里网络永远比缓存新——用 stale-while-revalidate
  // 会让"刚部署的新页面"第一次加载还是旧 JS，正是最难解释的那种 bug。
  event.respondWith(
    fetch(request).then((resp) => {
      if (resp && resp.status === 200 && resp.type === 'basic') {
        const copy = resp.clone();
        caches.open(VERSION).then((cache) => cache.put(request, copy)).catch(() => undefined);
      }
      return resp;
    }).catch(() => caches.match(request).then((hit) => hit || Response.error())),
  );
});
