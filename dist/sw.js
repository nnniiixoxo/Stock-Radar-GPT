const CACHE='stock-radar-v1';
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['./','index.html','styles.css','app.js','config.js','icon.svg']))));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));});
self.addEventListener('push',e=>{const d=e.data?e.data.json():{title:'Stock Radar',body:'새 스크리닝 결과가 도착했습니다.'};e.waitUntil(self.registration.showNotification(d.title,{body:d.body,icon:'icon.svg'}));});
self.addEventListener('notificationclick',e=>{e.notification.close();e.waitUntil(clients.openWindow('./'));});
