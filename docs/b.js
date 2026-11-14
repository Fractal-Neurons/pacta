/*Pacta first-party beacon: no cookies or ids, DNT honoured, paths and referrers redacted; app.js reports copy / CTA clicks through pactaBeacon*/
(function(w,d,n){var U="https://pacta-x402.pacta.workers.dev/v1/telemetry/beacon",L=w.location,k={},N=d.querySelector("[data-nf]"),S,O=L.protocol=="https:"&&n.doNotTrack!="1",D=/reset|token|log|auth|user|acc|mail|exam|sec|priv|pass|sess|adm|\d{5}/,q=L.pathname.replace(/(\/index\.html|\/+)$/,"")||"/",m=/^\/(protocols|briefs)\/([a-z][a-z\d-]{1,39})$/.exec(q),
P=q=="/"?q:/^\/(protocols|request|briefs)$/.test(q)?q+"/":m&&!D.test(m[2])&&!(N&&m[1]<"c")?(m[1]>"c"&&(S=m[2]),q+"/"):N?"/404":"/other";
function B(e,t,f,b,r,u){if(O){b={v:1,e:e,p:P};t&&(b.t=t);if(f){try{r=new URL(d.referrer).hostname}catch(x){}
r&&(r==L.hostname?b.r="self":r.length<81&&/^([a-z\d-]+\.)+[a-z]{2,24}$/.test(r)&&!/\.(local\w*|internal|lan|arpa)$|ip\.io$|\d+-\d+-\d+-\d/.test(r)&&(b.r=r));
(u=/[?&]utm_source=([^&]*)/.exec(L.search))&&/^[a-z][\w-]{0,23}$/.test(u=u[1].toLowerCase())&&!D.test(u)&&(b.u=u)}
b=JSON.stringify(b);try{if(n.sendBeacon(U,b))return}catch(x){}fetch(U,{method:"POST",body:b,keepalive:!0,mode:"no-cors"}).catch(String)}}
function o(e){k[e]||(k[e]=1,B(e))}w.pactaBeacon=B;N?B("not_found_404",S,1):(B("page_load",S,1),S&&B("protocol_view",S));
w.addEventListener("scroll",function(f){f=(w.scrollY+w.innerHeight)/d.documentElement.scrollHeight;f<.5||o("scroll_50");f<.9||o("scroll_90")})})(window,document,navigator);
