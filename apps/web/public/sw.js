/* Offline shell only. API writes and private offer links are never cached. */
const CACHE='pehchaan-shell-v1';
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/soundbox','/offline.html','/icon-192.png','/icon-512.png'])));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('pehchaan-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url);
 if(request.method!=='GET'||url.origin!==self.location.origin||url.pathname.startsWith('/api/')||url.pathname.startsWith('/o/'))return;
 const asset=url.pathname.startsWith('/_next/static/')||/^\/icon-(192|512)\.png$/.test(url.pathname);
 if(request.mode!=='navigate'&&!asset)return;
 event.respondWith(fetch(request).then(response=>{if(response.ok&&response.status===200){const copy=response.clone();void caches.open(CACHE).then(cache=>cache.put(request,copy));}return response;}).catch(async()=>{const cached=await caches.match(request);if(cached)return cached;if(request.mode==='navigate')return await caches.match('/soundbox')||await caches.match('/offline.html');return Response.error();}));
});
