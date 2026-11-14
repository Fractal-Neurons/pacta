/* Pacta first-party beacon: no cookies, ids or third parties; DNT honoured */
(function(w,d,n){var U="https://pacta-x402.pacta.workers.dev/v1/telemetry/beacon",L=w.location,P=L.pathname.slice(0,120),k={},S,O=L.protocol=="https:"&&n.doNotTrack!="1";
if(!/^\/[\w\/.~%-]*$/.test(P))P="/";S=(P.match(/^\/protocols\/([a-z0-9-]{1,60})(\/|$)/)||0)[1];
function B(e,t,f){if(!O)return;var b={v:1,e:e,p:P},r,u;if(t)b.t=t;
if(f){try{r=new URL(d.referrer).hostname}catch(x){}if(r)b.r=r==L.hostname?"self":r.slice(0,80);
if(u=/[?&]utm_source=([\w.-]{1,40})/i.exec(L.search))b.u=u[1].toLowerCase()}
b=JSON.stringify(b);try{if(n.sendBeacon(U,b))return}catch(x){}fetch(U,{method:"POST",body:b,keepalive:!0,mode:"no-cors"}).catch(String)}
function o(e){k[e]||(k[e]=1,B(e))}w.pactaBeacon=B;
d.querySelector("[data-nf]")?B("not_found_404",S,1):(B("page_load",S,1),S&&B("protocol_view",S));
w.addEventListener("scroll",function(){var f=(w.scrollY+w.innerHeight)/d.documentElement.scrollHeight;f<.5||o("scroll_50");f<.9||o("scroll_90")},{passive:!0});
d.addEventListener("click",function(v){var x=v.target,c,a,q;if(!x.closest)return;
if(c=x.closest(".copy")){q=c.getAttribute("data-copy");if(q==null)q=(q=c.closest(".term"))&&(q=q.querySelector("pre"))?q.textContent:"";
/\/mcp\b/.test(q)?B("copy_mcp_url"):/^curl /.test(q)&&B("copy_curl")}
else if(a=x.closest("a"))/SKILL\.md$/.test(a.getAttribute("href"))?B("copy_skill_md"):a.closest("a.primary,.memo-foot a")&&B("cta_click")},!0)})(window,document,navigator);
