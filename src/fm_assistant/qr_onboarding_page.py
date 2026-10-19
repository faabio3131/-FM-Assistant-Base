"""Self-contained owner QR onboarding page; no external script or font dependencies."""
from __future__ import annotations

import html
import secrets

PAGE = """<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conectar WhatsApp | VendeAtendeIA</title>
<style>
:root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;background:#0b1120;color:#eff6ff}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:28px}
main{width:min(100%,590px);background:#111c30;border:1px solid #30415a;border-radius:20px;padding:36px;box-shadow:0 16px 60px #0005}
header{display:flex;align-items:center;gap:12px} .logo{background:#1d5365;border-radius:12px;padding:12px;font-size:24px}
h1{font-size:24px;margin:26px 0 10px}p{line-height:1.6;color:#bbcde2}
.status{display:flex;align-items:center;gap:9px;margin:22px 0;padding:14px 16px;border-radius:12px;background:#19283f}
.dot{height:9px;width:9px;border-radius:50%;background:#e4b55c}
button{padding:13px 19px;border:0;border-radius:11px;background:#36c6b3;color:#08212e;font-weight:700;cursor:pointer}
button:disabled{opacity:.5;cursor:wait}.qr{background:white;padding:16px;border-radius:15px;width:fit-content;max-width:100%;margin:22px auto}
.qr img{display:block;width:260px;max-width:100%}.hide{display:none}
small{color:#9fb3cf}.steps{margin-top:20px;padding-left:22px;color:#cad9e9;line-height:1.9}
a{color:#8de5e5}@media(max-width:500px){main{padding:22px}}
</style></head>
<body><main><header><div class="logo" aria-hidden="true">◈</div><strong>VendeAtendeIA</strong></header>
<h1>Conecte seu WhatsApp</h1>
<p>Sem configurar servidores ou copiar chaves. Apenas vincule seu telefone para preparar o atendimento.</p>
<div class="status" role="status" aria-live="polite"><span class="dot" id="dot"></span><span id="status">Verificando conexão…</span></div>
<div id="qrbox" class="qr hide"><img id="qrcode" alt="QR Code temporário para vincular seu WhatsApp"></div>
<div><button id="connect" type="button" class="hide">Gerar minha conexão</button>
<button id="refresh" type="button" class="hide">Atualizar QR Code</button>
<button id="pause" type="button" class="hide">Pausar atendimento</button>
<button id="logout" type="button" class="hide">Desvincular WhatsApp</button>
<button id="resume" type="button" class="hide">Retomar atendimento</button></div>
<ol class="steps"><li>Abra o WhatsApp no celular.</li><li>Vá até <strong>Aparelhos conectados</strong> e escolha <strong>Conectar aparelho</strong>.</li><li>Leia o código exibido acima.</li></ol>
<small>O QR Code é temporário e fica visível apenas nesta sessão autorizada. Se a conexão estiver indisponível, tente atualizar ou procure suporte.</small>
</main>
<script nonce="__NONCE__">
"use strict";
(() => {
 const base="/v1/channels/whatsapp/qr";
 const status=document.getElementById("status"), dot=document.getElementById("dot");
 const connect=document.getElementById("connect"), refresh=document.getElementById("refresh");
 const pause=document.getElementById("pause");
 const logout=document.getElementById("logout");
 const resume=document.getElementById("resume");
 const qrbox=document.getElementById("qrbox"), qr=document.getElementById("qrcode");
 let connection=null, waiting=false, paused=false;
 // FM corporate default. Signed Command policy projection is a separate gate.
 const QR_DISPLAY_CAP_MS=45000;
 let shownQr=null, shownAt=0, expiryTimer=null;
 function show(message,mode) {
   status.textContent=message;
   dot.style.background=mode==="ok"?"#36c6b3":mode==="error"?"#f58c7d":"#e4b55c";
 }
 function visible(el,yes){el.classList.toggle("hide",!yes);}
 async function request(path,options) {
   const response=await fetch(path,{credentials:"same-origin",cache:"no-store",...options});
   if(!response.ok)throw new Error("request_failed");
   return response.json();
 }
 async function sync() {
   if(waiting)return; waiting=true;
   try {
     if(!connection) {
       const latest=await request(base+"/current");
       if(!latest.connection_id) {show("Pronto para conectar","pending");visible(connect,true);return;}
       connection=latest.connection_id;
     }
     visible(connect,false);
     const current=await request(base+"/current");
     if(current.connection_id===connection && current.status==="disabled") {
       paused=true;shownQr=null;shownAt=0;
       if(expiryTimer!==null){clearTimeout(expiryTimer);expiryTimer=null;}
       qr.removeAttribute("src");visible(qrbox,false);
       visible(refresh,false);visible(pause,false);visible(logout,true);visible(resume,true);
       show("Atendimento pausado. A vinculação do aparelho não foi removida; procure suporte para reativar.","pending");
       return;
     }
     visible(pause,true);visible(logout,true);visible(resume,false);
     const data=await request(base+"/"+encodeURIComponent(connection));
     qr.removeAttribute("src");visible(qrbox,false);
     if(data.status==="connected") {
       shownQr=null;shownAt=0;
       if(expiryTimer!==null){clearTimeout(expiryTimer);expiryTimer=null;}
       show("WhatsApp conectado","ok");visible(refresh,false);
     }
     else if(data.qr_data_url && data.qr_data_url.startsWith("data:image/png;base64,")) {
       const now=Date.now();
       if(shownQr!==data.qr_data_url) {
         shownQr=data.qr_data_url;shownAt=now;
         if(expiryTimer!==null)clearTimeout(expiryTimer);
         const currentQr=shownQr;
         expiryTimer=setTimeout(()=>{
           if(shownQr===currentQr){
             qr.removeAttribute("src");visible(qrbox,false);
             show("QR Code expirado na tela. Aguardando código novo do provedor…","pending");
           }
         },QR_DISPLAY_CAP_MS);
       }
       if(now-shownAt>=QR_DISPLAY_CAP_MS) {
         show("QR Code expirado na tela. Aguardando código novo do provedor…","pending");
         visible(refresh,true);
       } else {
         qr.src=data.qr_data_url;visible(qrbox,true);
         show("Aguardando leitura do QR Code","pending");visible(refresh,true);
       }
     } else {show("Conexão em preparação","pending");visible(refresh,true);}
   } catch {show("Não foi possível consultar a conexão. Atualize ou contate o suporte.","error");visible(refresh,true);}
   finally {waiting=false;}
 }
 connect.addEventListener("click",async()=>{
   connect.disabled=true;
   try{
     const result=await request(base+"/provision",{method:"POST"});
     connection=result.connection_id;await sync();
   }catch {show("Provisionamento não confirmado. Não repita; procure o suporte.","error");visible(connect,false);}
   finally{connect.disabled=false;}
 });
 pause.addEventListener("click",async()=>{
   if(!connection||waiting||paused)return;
   pause.disabled=true;
   try {
     const response=await request(base+"/"+encodeURIComponent(connection)+"/pause",{method:"POST"});
     if(response.status==="disabled"){paused=true;await sync();}
   } catch {show("Não foi possível pausar. Verifique suas permissões.","error");}
   finally{pause.disabled=false;}
 });
 resume.addEventListener("click",async()=>{
   if(!connection||waiting)return;
   resume.disabled=true;
   try{
     const result=await request(base+"/"+encodeURIComponent(connection)+"/resume",{method:"POST"});
     if(result.status==="active"){
       paused=false;visible(resume,false);await sync();
     }
   }catch {
     show("Não foi possível retomar: conexão remota não confirmada. Procure suporte.","error");
   }finally{resume.disabled=false;}
 });
 logout.addEventListener("click",async()=>{
   if(!connection || waiting || !window.confirm(
     "Desvincular o WhatsApp deste atendimento? Será necessário escanear um novo QR Code futuramente."
   ))return;
   logout.disabled=true;
   try{
     const result=await request(base+"/"+encodeURIComponent(connection)+"/logout",{method:"POST"});
     if(result.status==="revoked"){
       paused=true;shownQr=null;shownAt=0;
       if(expiryTimer!==null)clearTimeout(expiryTimer);
       qr.removeAttribute("src");visible(qrbox,false);
       visible(refresh,false);visible(pause,false);visible(logout,false);visible(resume,false);
       show("WhatsApp desvinculado. A reconexão exige novo provisionamento governado.","ok");
     }
   }catch{
     paused=true;qr.removeAttribute("src");visible(qrbox,false);
     show("Desconexão remota não confirmada. Atendimento bloqueado; procure suporte.","error");
   }finally{logout.disabled=false;}
 });
 refresh.addEventListener("click",sync);
 sync();
 setInterval(() => { if (!document.hidden && connection && !paused) sync(); }, 8000);
})();
</script></body></html>"""


def render_qr_page() -> tuple[str, str]:
    nonce = secrets.token_urlsafe(24)
    page = PAGE.replace("__NONCE__", html.escape(nonce, quote=True))
    csp = (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
        "form-action 'none'; connect-src 'self'; "
        "img-src data:; style-src 'unsafe-inline'; script-src 'nonce-" + nonce + "'"
    )
    return page, csp
