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
header h1{margin:0;font-size:22px}header p{margin:4px 0 0;color:#d7e5f0}header a{color:#d9efff;display:inline-block;margin-top:8px}
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
#transcript{max-height:360px;overflow-y:auto;padding:12px;background:#f7fafc;border-radius:9px}
.bubble{max-width:94%;margin:8px 0;padding:9px 12px;background:#fff;border:1px solid #dce6eb;border-radius:11px;white-space:pre-wrap;overflow-wrap:anywhere}
.bubble.answer{background:#eaf5f9;margin-left:auto}
.bubble small{display:block;color:#607786;font-size:11px;font-weight:600;margin-bottom:4px}
#detail{overflow-wrap:anywhere}.tools{display:flex;gap:8px;flex-wrap:wrap}
.event{padding:9px;border-bottom:1px solid #edf0f2;font-size:13px}
.event .note{white-space:pre-wrap;color:#364d5b}
.empty{color:#637785;font-size:14px}
@media(max-width:790px){main{display:block}section{margin-bottom:18px}}
</style></head>
<body><header><h1>VendeAtendeIA · Atendimento humano</h1>
<p>Conversas aguardando ou em atendimento • Unidade da sua sessão</p><a href="/app/knowledge">Gerenciar base de conhecimento</a> <a href="/app/crm">CRM comercial</a></header>
<main>
<section aria-label="Fila de atendimento"><h2>Caixa de entrada</h2>
<nav><button id="refresh" class="primary">Atualizar fila</button>
<button id="previous" disabled>Anterior</button>
<button id="next" disabled>Próxima</button></nav>
<p id="notice" role="status" aria-live="polite"></p>
<div id="queue"></div>
<h3>Envios WhatsApp pendentes ou incertos</h3>
<div id="outbox-operations" class="meta">Carregando operações...</div>
<h3>Agentes disponíveis</h3>
<div id="agents" class="meta">Carregando presença...</div>
<h3>Limites operacionais</h3><p class="meta">Ajuste permitido aos gestores.</p>
<label for="sla-minutes">Tempo máximo de espera (minutos)</label>
<input id="sla-minutes" inputmode="numeric" type="number" min="1" max="1440">
<label for="presence-seconds">Presença ativa (segundos)</label>
<input id="presence-seconds" inputmode="numeric" type="number" min="30" max="900">
<button id="save-policy">Salvar política</button>
</section>
<section aria-label="Conversa selecionada"><h2>Detalhes e responsável</h2>
<div id="detail" class="empty">Selecione uma conversa na fila.</div>
<h3>Histórico da conversa</h3><div id="transcript" class="empty">Selecione uma conversa.</div>
<div id="controls" hidden>
<div class="tools">
<button class="primary" id="claim">Assumir atendimento</button>
<button class="critical" id="return">Devolver à IA</button></div>
<div id="reply-panel" hidden><h3 id="reply-heading">Resposta humana</h3>
<label for="reply">Mensagem ao cliente</label><textarea id="reply" maxlength="20000"></textarea>
<button class="primary" id="send-reply">Enviar resposta</button>
<button id="check-reply" hidden>Consultar situação do envio</button>
<div id="uncertain-review" hidden><h3>Investigar envio incerto</h3>
<p class="meta">Uma evidência candidata não prova entrega e não libera reenvio.</p>
<label for="candidate-ref">ID da mensagem no provedor (se encontrado)</label>
<input id="candidate-ref" maxlength="160">
<button id="investigate">Consultar evidência no provedor</button>
<label for="review-note">Nota da revisão administrativa</label>
<textarea id="review-note" maxlength="2000"></textarea>
<button id="review">Registrar revisão sem liberar reenvio</button></div>
</div>
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
let selectedChannel=null,policyRevision=0;
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
        elt("small","meta",item.channel+" • "+(item.assigned_to||"Sem responsável")),
        elt("small",item.sla_overdue?"tag":"meta",
          "Espera "+item.waiting_minutes+" min / SLA "+item.sla_minutes+" min"+
          (item.sla_overdue?" • SLA excedido":"")));
      button.onclick=()=>select(item);
      box.append(button);
    }
    if(!result.items.length)box.append(elt("p","empty","Nenhuma conversa aguardando."));
    note(result.items.length+" conversa(s) nesta página.");
    await refreshAgents();await refreshOutbox();
  }catch(error){note("Não foi possível carregar a fila: "+error.message);}
  finally{busy=false;$("refresh").disabled=false;}
}
async function refreshOutbox(){
  try{
    const result=await api("/v1/inbox/outbound-operations?limit=50");
    $("outbox-operations").replaceChildren();
    if(!result.items.length)
      $("outbox-operations").textContent="Sem envios humanos pendentes.";
    for(const item of result.items){
      const button=elt("button","item",
        item.status+" • "+item.message_id.slice(0,8)+
        (item.reviewed?" • revisado":""));
      button.onclick=()=>{
        current=item.conversation_id;selectedChannel="whatsapp";
        pendingReplyId=item.message_id;
        $("controls").hidden=false;$("reply-panel").hidden=false;
        $("send-reply").disabled=true;$("check-reply").hidden=false;
        $("uncertain-review").hidden=item.status!=="sending_uncertain";
        $("detail").replaceChildren(
          elt("strong","","Operação WhatsApp sob acompanhamento"),
          elt("p","meta","ID da mensagem: "+item.message_id),
          elt("p","meta","Estado: "+item.status),
        );
        activity();transcript();
      };
      $("outbox-operations").append(button);
    }
  }catch{$("outbox-operations").textContent="Operações indisponíveis.";}
}
async function refreshAgents(){
  try{
    const online=await api("/v1/inbox/presence");
    $("agents").replaceChildren();
    if(!online.items.length)$("agents").textContent="Nenhum agente com presença ativa.";
    for(const agent of online.items)
      $("agents").append(elt("p","meta",agent.display_name));
  }catch{$("agents").textContent="Presença indisponível.";}
}
async function loadPolicy(){
  try{
    const policy=await api("/v1/inbox/policy");
    $("sla-minutes").value=policy.first_response_minutes;
    $("presence-seconds").value=policy.presence_timeout_seconds;
    policyRevision=policy.revision;
  }catch{note("Política SLA indisponível.");}
}
async function select(item) {
  current=item.conversation_id;pendingReplyId=null;$("controls").hidden=false;
  $("send-reply").disabled=false;$("uncertain-review").hidden=true;
  selectedChannel=item.channel;$("reply-panel").hidden=false;
  $("check-reply").hidden=true;
  $("reply-heading").textContent=item.channel==="whatsapp"?
    "Resposta WhatsApp (Evolution ou Meta; fila segura)":
    "Resposta humana Webchat/API";
  $("detail").replaceChildren(
    elt("p","",item.external_ref||item.conversation_id),
    elt("p","meta","Canal: "+item.channel+" • Estado: "+item.status),
    elt("p","", "Responsável: "+(item.assigned_to||"aguardando")));
  await load();await transcript();await activity();
}
async function transcript(){
  if(!current)return;
  try{
    const messages=await api("/v1/inbox/"+encodeURIComponent(current)+"/transcript");
    if(!Array.isArray(messages)||messages.length>200)throw Error("invalid_transcript");
    const box=$("transcript");box.replaceChildren();
    if(!messages.length){box.textContent="Ainda não há mensagens registradas.";return;}
    for(const item of messages){
      if(!item||typeof item.content!=="string"||
        typeof item.role!=="string"||item.content.length>20000)continue;
      const customer=item.role==="user";
      const bubble=elt("div",customer?"bubble":"bubble answer");
      bubble.append(elt("small","",customer?"Cliente":"Resposta"),
        elt("div","",item.content));
      box.append(bubble);
    }
    box.scrollTop=box.scrollHeight;
  }catch{$("transcript").textContent="Histórico indisponível para esta sessão.";}
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
    await load();await transcript();await activity();note(statusText);
  }catch(error){note("Ação não concluída: "+error.message);}
  finally{busy=false;}
}
$("save-policy").onclick=async()=>{
  const mins=Number($("sla-minutes").value);
  const secs=Number($("presence-seconds").value);
  if(!Number.isInteger(mins)||mins<1||mins>1440||
    !Number.isInteger(secs)||secs<30||secs>900){
    note("Verifique os limites da política.");return;
  }
  try{
    await api("/v1/inbox/policy","PUT",{
      first_response_minutes:mins,presence_timeout_seconds:secs,
      expected_revision:policyRevision,
    });
    await loadPolicy();await load();note("SLA atualizado para esta unidade.");
  }catch{note("Política não alterada: permissão ou revisão inválida.");}
};
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
    note("Situação do envio: "+status.status+
      (status.delivery_status?" • transportador: "+status.delivery_status:"")+
      (status.provider_candidate?" • evidência candidata (não conclusiva)":"")+
      ". ACK não equivale a entrega ou leitura.");
    $("uncertain-review").hidden=status.status!=="sending_uncertain";
    if(status.status==="provider_acknowledged"){
      $("reply").value="";pendingReplyId=null;$("check-reply").hidden=true;}
  }catch{note("Não foi possível consultar o estado do envio.");}
};
$("investigate").onclick=async()=>{
  if(!current||!pendingReplyId)return;
  const ref=$("candidate-ref").value.trim();
  if(!/^[A-Za-z0-9._:-]{1,160}$/.test(ref)){
    note("Informe um ID de mensagem válido do provedor.");return;
  }
  try{
    const result=await api("/v1/inbox/"+encodeURIComponent(current)+"/outbound/"+
      encodeURIComponent(pendingReplyId)+"/investigate","POST",
      {provider_reference:ref});
    note(result.status==="candidate_only"?
      "Evidência candidata encontrada; a entrega continua não comprovada.":
      "Nenhuma evidência correspondente encontrada.");
  }catch{note("Investigação não concluída. Nenhum reenvio foi realizado.");}
};
$("review").onclick=async()=>{
  if(!current||!pendingReplyId)return;
  const value=$("review-note").value.trim();
  if(value.length<10){note("A revisão exige uma justificativa.");return;}
  try{
    const result=await api("/v1/inbox/"+encodeURIComponent(current)+"/outbound/"+
      encodeURIComponent(pendingReplyId)+"/review","POST",{note:value});
    note(result.status==="reviewed_uncertain"?
      "Revisão registrada; envio continua incerto e bloqueado contra reenvio.":
      "Revisão não alterou o estado.");
    await refreshOutbox();
  }catch{note("A revisão exige permissão administrativa ou estado incerto.");}
};
$("send-reply").onclick=()=>{const value=$("reply").value.trim();
  if(value){pendingReplyId ||= crypto.randomUUID();
    action("reply",{message_id:pendingReplyId,content:value});}};
$("save-note").onclick=()=>{const value=$("note").value.trim();
  if(value)action("notes",{note:value});};
load();loadPolicy();
api("/v1/inbox/presence","POST").catch(()=>{});
setInterval(()=>api("/v1/inbox/presence","POST").catch(()=>{}),60000);
})();
</script>
</body></html>"""
