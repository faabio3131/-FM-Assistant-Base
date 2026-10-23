"""Web inbox VendeAtendeIA: one team UI for claiming handoffs.

Static shell; all customer data originates from authenticated same-origin API.
No tenant IDs in URLs, no HTML injection from conversation content.
"""
from __future__ import annotations


def render_human_inbox_page() -> str:
    return """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Caixa de Entrada | VendeAtendeIA</title>
<style>
:root{font:15px/1.5 system-ui,Arial;color:#1c2b36;background:#f5f7fa}
*{box-sizing:border-box}body{margin:0}
header{padding:22px clamp(18px,4vw,48px);background:#11283b;color:#fff}
header h1{margin:0;font-size:22px}header p{margin:4px 0 0;color:#d7e5f0}
main{max-width:1300px;margin:26px auto;padding:0 18px;display:grid;
 grid-template-columns:minmax(270px,390px) 1fr;gap:18px}
section{background:white;border:1px solid #dee5eb;border-radius:13px;
 padding:22px;box-shadow:0 3px 14px #11283b0a;min-width:0}
h2{font-size:17px;margin:0 0 14px}h3{font-size:15px;margin:22px 0 10px}
button{font:inherit;border-radius:8px;border:1px solid #b4c4d0;
 background:white;padding:9px 13px;cursor:pointer;color:#13364b}
button:hover{background:#eef4f8}button:disabled{opacity:.55;cursor:default}
button.primary{background:#155b74;border-color:#155b74;color:white}
button.primary:hover{background:#10485d}
button.critical{color:#8a361c;border-color:#d7b7a8}
nav{display:flex;gap:8px;margin-bottom:15px}
input,textarea{display:block;width:100%;font:inherit;padding:11px;
 border:1px solid #bccbd5;border-radius:8px;margin:6px 0 12px}
textarea{resize:vertical;min-height:82px}
label{font-weight:600;font-size:13px}
.item{display:block;text-align:left;width:100%;padding:13px;
 border-radius:10px;margin:0 0 8px;overflow-wrap:anywhere}
.item strong,.item small{display:block}
.item[aria-pressed=true]{border-color:#156c92;background:#e7f4f8}
.meta{font-size:12px;color:#586f7e}
.tag{background:#eaf5eb;color:#226241;border-radius:4px;padding:2px 6px;font-size:12px}
#notice{min-height:25px;color:#265368;margin:0 0 12px}
#detail{overflow-wrap:anywhere}.tools{display:flex;gap:8px;flex-wrap:wrap}
.event{padding:9px;border-bottom:1px solid #edf0f2;font-size:13px}
.event .note{white-space:pre-wrap;color:#364d5b}
.empty{color:#637785;font-size:14px}
@media(max-width:790px){main{display:block}section{margin-bottom:18px}}
</style></head>
<body><header><h1>VendeAtendeIA · Atendimento humano</h1>
<p>Conversas aguardando ou em atendimento • Unidade da sua sessão</p></header>
<main>
<section aria-label="Fila de atendimento"><h2>Caixa de entrada</h2>
<nav><button id="refresh" class="primary">Atualizar fila</button>
<button id="previous" disabled>Anterior</button>
<button id="next" disabled>Próxima</button></nav>
<p id="notice" role="status" aria-live="polite"></p>
<div id="queue"></div></section>
<section aria-label="Conversa selecionada"><h2>Detalhes e responsável</h2>
<div id="detail" class="empty">Selecione uma conversa na fila.</div>
<div id="controls" hidden>
<div class="tools">
<button class="primary" id="claim">Assumir atendimento</button>
<button class="critical" id="return">Devolver à IA</button></div>
<div id="reply-panel" hidden><h3 id="reply-heading">Resposta humana</h3>
<label for="reply">Mensagem ao cliente</label><textarea id="reply" maxlength="20000"></textarea>
<button class="primary" id="send-reply">Enviar resposta</button>
<button id="check-reply" hidden>Consultar situação do envio</button></div>
<h3>Transferir para agente da unidade</h3>
<label for="target">ID do agente</label><input id="target" maxlength="64"
 placeholder="Identificador do usuário">
<button id="transfer">Transferir</button>
<h3>Nota interna (não enviada ao cliente)</h3>
<label for="note">Informação para a equipe</label>
<textarea id="note" maxlength="4000"></textarea>
<button id="save-note">Salvar nota</button>
<h3>Histórico de operações</h3><div id="activity"></div>
</div></section>
</main>
<script>
(() => {
"use strict";
const $ = id => document.getElementById(id);
let page=0, nextPage=null, current=null, busy=false, pendingReplyId=null;
let selectedChannel=null;
const note = message => { $("notice").textContent=message; };
async function api(path, method="GET", body=null) {
  const init={method,credentials:"same-origin",cache:"no-store",
    headers:{"Accept":"application/json"}};
  if(body!==null){init.headers["Content-Type"]="application/json";
    init.body=JSON.stringify(body);}
  const response=await fetch(path,init);
  const data=await response.json();
  if(!response.ok) throw Error(data.detail || "Operação indisponível.");
  return data;
}
function elt(tag,cls,value) {
  const node=document.createElement(tag);
  if(cls)node.className=cls;
  if(value!==undefined)node.textContent=String(value);
  return node;
}
async function load() {
  if(busy)return;
  busy=true;$("refresh").disabled=true;
  try{
    const result=await api("/v1/inbox?page="+page+"&limit=50");
    nextPage=result.next_page;
    $("previous").disabled=page===0;
    $("next").disabled=nextPage===null;
    const box=$("queue");box.replaceChildren();
    for(const item of result.items){
      const button=elt("button","item");
      button.type="button";
      button.setAttribute("aria-pressed",String(current===item.conversation_id));
      button.append(elt("strong","",item.external_ref||item.conversation_id),
        elt("small","meta",item.channel+" • "+(item.assigned_to||"Sem responsável")));
      button.onclick=()=>select(item);
      box.append(button);
    }
    if(!result.items.length)box.append(elt("p","empty","Nenhuma conversa aguardando."));
    note(result.items.length+" conversa(s) nesta página.");
  }catch(error){note("Não foi possível carregar a fila: "+error.message);}
  finally{busy=false;$("refresh").disabled=false;}
}
async function select(item) {
  current=item.conversation_id;pendingReplyId=null;$("controls").hidden=false;
  selectedChannel=item.channel;$("reply-panel").hidden=false;
  $("check-reply").hidden=true;
  $("reply-heading").textContent=item.channel==="whatsapp"?
    "Resposta WhatsApp Evolution (fila segura; sem confirmação imediata)":
    "Resposta humana Webchat/API";
  $("detail").replaceChildren(
    elt("p","",item.external_ref||item.conversation_id),
    elt("p","meta","Canal: "+item.channel+" • Estado: "+item.status),
    elt("p","", "Responsável: "+(item.assigned_to||"aguardando")));
  await load();await activity();
}
async function activity() {
  if(!current)return;
  try{
    const result=await api("/v1/inbox/"+encodeURIComponent(current)+"/activity?limit=50");
    $("activity").replaceChildren();
    for(const e of result.items){
      const row=elt("div","event");
      row.append(elt("strong","",e.action+" • "+e.actor_id),
        elt("div","meta",e.created_at));
      if(e.private_note)row.append(elt("p","note",e.private_note));
      $("activity").append(row);
    }
  }catch{note("Histórico indisponível ou acesso não permitido.");}
}
async function action(name,body=null){
  if(!current||busy)return;
  busy=true;
  try{
    const result=await api("/v1/inbox/"+encodeURIComponent(current)+"/"+name,"POST",body);
    const statusText=name==="reply"&&selectedChannel==="whatsapp"?
      "Mensagem enfileirada ("+result.status+"). Consulte o envio; não reenvie.":
      "Operação registrada.";
    $("check-reply").hidden=!(name==="reply"&&selectedChannel==="whatsapp");
    if(name==="return-to-ai"){current=null;$("controls").hidden=true;
      $("detail").textContent="Conversa devolvida à IA.";}
    if(name==="notes")$("note").value="";
    if(name==="reply"&&selectedChannel!=="whatsapp"){
      $("reply").value="";pendingReplyId=null;}
    busy=false;
    await load();await activity();note(statusText);
  }catch(error){note("Ação não concluída: "+error.message);}
  finally{busy=false;}
}
$("refresh").onclick=()=>load();
$("previous").onclick=()=>{if(page>0){page--;load();}};
$("next").onclick=()=>{if(nextPage!==null){page=nextPage;load();}};
$("claim").onclick=()=>action("claim");
$("return").onclick=()=>action("return-to-ai");
$("transfer").onclick=()=>{const target=$("target").value.trim();
  if(target)action("transfer",{user_id:target});};
$("check-reply").onclick=async()=>{
  if(!current||!pendingReplyId)return;
  try{const status=await api("/v1/inbox/"+encodeURIComponent(current)+
    "/outbound/"+encodeURIComponent(pendingReplyId));
    note("Situação do envio no VendeAtendeIA: "+status.status+
      ". Confirmação do provedor não equivale a leitura pelo destinatário.");
    if(status.status==="provider_acknowledged"){
      $("reply").value="";pendingReplyId=null;$("check-reply").hidden=true;}
  }catch{note("Não foi possível consultar o estado do envio.");}
};
$("send-reply").onclick=()=>{const value=$("reply").value.trim();
  if(value){pendingReplyId ||= crypto.randomUUID();
    action("reply",{message_id:pendingReplyId,content:value});}};
$("save-note").onclick=()=>{const value=$("note").value.trim();
  if(value)action("notes",{note:value});};
load();
})();
</script>
</body></html>"""
