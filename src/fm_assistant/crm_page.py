"""Same-origin CRM workspace for contacts and deterministic opportunities."""
from __future__ import annotations

import base64
import hashlib


def render_crm_page() -> tuple[str, str]:
    script = r"""
(() => {
"use strict";
const $ = id => document.getElementById(id);
const el = (tag, text, cls) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (cls) node.className = cls;
  return node;
};
let contacts = [], opportunities = [], running = false;
const notice = text => { $("notice").textContent = text; };
async function api(path, method="GET", payload) {
  const options = {method, credentials:"same-origin", cache:"no-store",
    headers:{"Accept":"application/json"}};
  if (payload !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(payload);
  }
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(data.detail || "Falha na operação.");
  return data;
}
async function guarded(work) {
  if (running) return;
  running = true;
  document.querySelectorAll("button").forEach(x => {x.disabled=true;});
  try {await work();} catch (e) {notice("Não concluído: " + e.message);}
  finally {running=false;document.querySelectorAll("button").forEach(x => {x.disabled=false;});}
}
const stages = {
  new:["qualified","lost"], qualified:["proposal","lost"],
  proposal:["won","lost"], won:[], lost:[]
};
const labels = {
  new:"Novo", qualified:"Qualificado", proposal:"Proposta",
  won:"Ganho", lost:"Perdido"
};
function renderContacts() {
  const area = $("contacts");
  const selector = $("opportunity-contact");
  const current = selector.value;
  area.replaceChildren();
  selector.replaceChildren();
  if (!contacts.length) area.append(el("p","Nenhum contato nesta página.","subtle"));
  for (const contact of contacts) {
    const row = el("article", undefined, "entry");
    row.append(el("strong",contact.name));
    if (contact.email) row.append(el("small",contact.email,"subtle"));
    row.append(el("small","Contato #" + contact.contact_id.slice(0,8),"subtle"));
    area.append(row);
    const option = el("option",contact.name);
    option.value=contact.contact_id;
    selector.append(option);
  }
  if (contacts.some(c => c.contact_id === current)) selector.value=current;
  const linkContact=$("link-contact"), prior=linkContact.value;
  linkContact.replaceChildren();
  for(const contact of contacts){
    const option=el("option",contact.name);option.value=contact.contact_id;
    linkContact.append(option);
  }
  if(contacts.some(c=>c.contact_id===prior))linkContact.value=prior;
}
function renderOpportunities() {
  const area = $("opportunities");
  area.replaceChildren();
  if (!opportunities.length) area.append(el("p","Nenhuma oportunidade neste filtro.","subtle"));
  const select=$("workflow-opportunity"), current=select.value;
  const linkOpp=$("link-opportunity"), prior=linkOpp.value;
  select.replaceChildren();linkOpp.replaceChildren();
  const blank=el("option","Sem oportunidade vinculada");blank.value="";
  linkOpp.append(blank);
  for(const opp of opportunities){
    const option=el("option",opp.title);option.value=opp.opportunity_id;select.append(option);
    const candidate=el("option",opp.title);candidate.value=opp.opportunity_id;linkOpp.append(candidate);
  }
  if(opportunities.some(x=>x.opportunity_id===current))select.value=current;
  if(opportunities.some(x=>x.opportunity_id===prior))linkOpp.value=prior;
  for (const item of opportunities) {
    const row = el("article",undefined,"entry");
    row.append(el("strong",item.title));
    const name = contacts.find(c => c.contact_id === item.contact_id)?.name || "Contato vinculado";
    row.append(el("small",name+" · "+(item.amount_cents/100).toLocaleString("pt-BR",{
      style:"currency",currency:"BRL"})+" · "+labels[item.stage],"subtle"));
    const actions = el("div",undefined,"actions");
    for (const next of stages[item.stage] || []) {
      const button=el("button","Mover para "+labels[next]);
      button.type="button";
      button.addEventListener("click",() => guarded(async () => {
        await api("/v1/crm/opportunities/"+encodeURIComponent(item.opportunity_id)+
          "/transition","POST",{expected_revision:item.revision,stage:next});
        notice("Etapa atualizada: "+labels[next]+".");
        await refresh();
      }));
      actions.append(button);
    }
    row.append(actions);
    area.append(row);
  }
}
async function refresh() {
  const results = await Promise.all([
    api("/v1/crm/contacts"),
    api("/v1/crm/opportunities?stage="+encodeURIComponent($("stage-filter").value))
  ]);
  contacts=results[0].items;
  opportunities=results[1].items;
  renderContacts();
  renderOpportunities();
  $("contact-more").textContent = results[0].next_page !== null ?
    "Mostrando 50 contatos; consulte as próximas páginas pela API." : "";
  $("opportunity-more").textContent = results[1].next_page !== null ?
    "Mostrando 50 oportunidades; consulte as próximas páginas pela API." : "";
}
$("contact-form").addEventListener("submit", event => {
  event.preventDefault();
  guarded(async () => {
    const result=await api("/v1/crm/contacts","POST",{
      name:$("contact-name").value,email:$("contact-email").value || null
    });
    $("contact-form").reset();
    notice("Contato cadastrado: "+result.name+".");
    await refresh();
  });
});
$("opportunity-form").addEventListener("submit", event => {
  event.preventDefault();
  guarded(async () => {
    const cents=Number($("amount-cents").value);
    if(!Number.isSafeInteger(cents) || cents<0) throw Error("Valor em centavos inválido.");
    const result=await api("/v1/crm/opportunities","POST",{
      contact_id:$("opportunity-contact").value,
      title:$("opportunity-title").value,amount_cents:cents
    });
    $("opportunity-form").reset();
    notice("Oportunidade cadastrada na etapa "+labels[result.stage]+".");
    await refresh();
  });
});
$("stage-filter").addEventListener("change",() => guarded(refresh));
$("refresh").addEventListener("click",() => guarded(refresh));

function activeOpportunity(){
  const id=$("workflow-opportunity").value;
  if(!id)throw Error("Selecione uma oportunidade.");
  return "/v1/crm/opportunities/"+encodeURIComponent(id);
}
$("link-form").addEventListener("submit",event=>{
  event.preventDefault();guarded(async()=>{
    const id=$("link-conversation").value.trim();
    if(!id)throw Error("Informe o ID da conversa.");
    const path="/v1/crm/conversations/"+encodeURIComponent(id)+"/link";
    const prior=await api(path).catch(err=>{
      if(String(err.message).includes("crm.link_not_found"))return {revision:0};
      throw err;
    });
    const payload={
      contact_id:$("link-contact").value,
      opportunity_id:$("link-opportunity").value || null,
      expected_revision:prior.revision
    };
    const result=await api(path,"PUT",payload);
    notice("Conversa vinculada à revisão "+result.revision+".");
  });
});
$("qualification-form").addEventListener("submit",event=>{
  event.preventDefault();guarded(async()=>{
    const root=activeOpportunity(),path=root+"/qualification";
    const prior=await api(path).catch(err=>{
      if(String(err.message).includes("crm.qualification_not_found"))return {revision:0};
      throw err;
    });
    const days=$("timeline-days").value;
    const result=await api(path,"PUT",{
      expected_revision:prior.revision,
      need_confirmed:$("need-confirmed").checked,
      budget_confirmed:$("budget-confirmed").checked,
      decision_maker_confirmed:$("decision-confirmed").checked,
      timeline_days:days===""?null:Number(days)
    });
    notice("Qualificação registrada: "+result.score+"/100; nenhuma mudança automática de etapa.");
    await showWorkflow();
  });
});
$("proposal-form").addEventListener("submit",event=>{
  event.preventDefault();guarded(async()=>{
    const root=activeOpportunity();
    const result=await api(root+"/proposals","POST",{
      title:$("proposal-title").value,terms:$("proposal-terms").value
    });
    $("proposal-form").reset();
    notice("Proposta interna criada: "+result.title+". Nenhum envio foi realizado.");
    await showWorkflow();
  });
});
$("activity-form").addEventListener("submit",event=>{
  event.preventDefault();guarded(async()=>{
    await api(activeOpportunity()+"/activities","POST",{
      kind:$("activity-kind").value,details:$("activity-details").value
    });
    $("activity-details").value="";
    notice("Atividade registrada.");
    await showWorkflow();
  });
});
async function showWorkflow(){
  const root=activeOpportunity();
  const [qualification,proposals,activities,links]=await Promise.all([
    api(root+"/qualification").catch(e=>{
      if(String(e.message).includes("crm.qualification_not_found"))return null;
      throw e;
    }),api(root+"/proposals"),api(root+"/activities"),api(root+"/conversations")
  ]);
  $("qualification-summary").textContent=qualification?
    "Pontuação: "+qualification.score+"/100 · revisão "+qualification.revision:
    "Sem qualificação registrada.";
  $("linked-summary").textContent=links.items.length+
    " conversa(s) vinculada(s) à oportunidade.";
  const quoteArea=$("proposal-results");quoteArea.replaceChildren();
  if(!proposals.items.length)quoteArea.append(el("p","Sem propostas internas.","subtle"));
  for(const proposal of proposals.items){
    const card=el("article",undefined,"entry");
    card.append(el("strong",proposal.title));
    card.append(el("small","Status: "+proposal.status+" · "+(proposal.amount_cents/100)
      .toLocaleString("pt-BR",{style:"currency",currency:"BRL"}),"subtle"));
    card.append(el("p",proposal.terms));
    if(proposal.status==="draft"){
      for(const state of ["ready","withdrawn"]){
        const btn=el("button",state==="ready"?"Aprovar internamente":"Retirar proposta");
        btn.addEventListener("click",()=>guarded(async()=>{
          await api(root+"/proposals/"+encodeURIComponent(proposal.proposal_id)+"/status",
            "POST",{expected_revision:proposal.revision,status:state});
          notice("Estado atualizado; nenhuma mensagem enviada ao cliente.");
          await showWorkflow();
        }));
        card.append(btn);
      }
    }
    quoteArea.append(card);
  }
  const area=$("activities"), items=activities.items;area.replaceChildren();
  if(!items.length)area.append(el("p","Nenhuma atividade registrada.","subtle"));
  for(const a of items){
    const entry=el("article",undefined,"entry");
    entry.append(el("strong",a.kind+" · "+new Date(a.created_at).toLocaleString("pt-BR")));
    if(a.details)entry.append(el("p",a.details));
    if(a.related_id)entry.append(el("small","Referência "+a.related_id,"subtle"));
    area.append(entry);
  }
}
$("show-workflow").addEventListener("click",()=>guarded(showWorkflow));

const initial = new URLSearchParams(window.location.search).get("conversation");
if(initial && initial.length<=64)$("link-conversation").value=initial;
guarded(refresh);
})();
"""
    signature = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = (
        "default-src 'none'; script-src 'sha256-" + signature +
        "'; style-src 'unsafe-inline'; connect-src 'self'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    )
    markup = """<!doctype html><html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>CRM | VendeAtendeIA</title>
<style>
:root{font:15px/1.5 system-ui,Arial;background:#f3f6fa;color:#193248}
*{box-sizing:border-box}body{margin:0}header{background:#142d42;color:white;padding:23px 5%}
h1{margin:0;font-size:24px}h2{margin:0 0 12px;font-size:18px}
header p{margin:5px 0 10px;color:#cee1f2}header a{color:#d8f2ff;margin-right:16px}
main{max-width:1240px;margin:26px auto;padding:0 20px;display:grid;
grid-template-columns:1fr 1fr;gap:20px}
section{background:#fff;border:1px solid #d9e2e9;border-radius:14px;
padding:22px;box-shadow:0 3px 16px #142d420b;min-width:0}
.wide{grid-column:1/-1}
label{display:block;font-size:13px;font-weight:650;margin:12px 0 4px}
input,select{display:block;width:100%;padding:11px;font:inherit;border-radius:8px;
border:1px solid #aabfcc;min-width:0}
button{margin-top:12px;border:1px solid #286681;color:#16516c;background:#fff;
padding:9px 15px;border-radius:8px;font:inherit;cursor:pointer}
button.primary{background:#155c7c;color:#fff}button:disabled{opacity:.55;cursor:not-allowed}
textarea{display:block;width:100%;min-height:90px;padding:11px;border:1px solid #aabfcc;border-radius:8px;font:inherit}
input[type=checkbox]{display:inline;width:auto;margin-right:6px}
.entry{border:1px solid #e1e7ed;border-radius:10px;padding:14px;
margin:10px 0;display:grid;gap:4px;overflow-wrap:anywhere}
.actions{display:flex;gap:8px;flex-wrap:wrap}.subtle{color:#556d7c}
#notice{min-height:24px;font-weight:600;color:#195b72}
@media(max-width:750px){main{grid-template-columns:1fr}.wide{grid-column:auto}}
</style></head><body>
<header><h1>VendeAtendeIA · CRM</h1>
<p>Contatos e oportunidades da sua empresa e unidade, com histórico de movimentação.</p>
<nav><a href="/app/inbox">Atendimento</a><a href="/app/knowledge">Conhecimento</a></nav>
</header><main>
<section><h2>Novo contato</h2>
<form id="contact-form"><label for="contact-name">Nome</label>
<input id="contact-name" maxlength="255" required>
<label for="contact-email">E-mail (opcional)</label>
<input type="email" id="contact-email" maxlength="320">
<button class="primary" type="submit">Cadastrar contato</button></form>
</section>
<section><h2>Nova oportunidade</h2>
<form id="opportunity-form"><label for="opportunity-contact">Contato</label>
<select id="opportunity-contact" required></select>
<label for="opportunity-title">Descrição</label>
<input id="opportunity-title" maxlength="255" required>
<label for="amount-cents">Valor em centavos (BRL)</label>
<input id="amount-cents" type="number" min="0" max="2000000000" step="1" required>
<button class="primary" type="submit">Abrir oportunidade</button></form>
</section>
<section class="wide"><h2>Pipeline comercial</h2>
<label for="stage-filter">Filtrar por etapa</label><select id="stage-filter">
<option value="">Todas</option><option value="new">Novas</option>
<option value="qualified">Qualificadas</option><option value="proposal">Proposta</option>
<option value="won">Ganhas</option><option value="lost">Perdidas</option>
</select><button id="refresh" type="button">Atualizar</button>
<p id="notice" role="status" aria-live="polite"></p>
<div id="opportunities"></div><small id="opportunity-more" class="subtle"></small>
</section><section class="wide"><h2>Contatos cadastrados</h2>
<div id="contacts"></div><small id="contact-more" class="subtle"></small></section>

<section class="wide"><h2>Relacionar conversa ao CRM</h2>
<p class="subtle">Informe o identificador de uma conversa da sua unidade. O vínculo é auditado e pode ser revisado.</p>
<form id="link-form"><label for="link-conversation">ID da conversa</label>
<input id="link-conversation" maxlength="64" required>
<label for="link-contact">Contato</label><select id="link-contact" required></select>
<label for="link-opportunity">Oportunidade (opcional)</label>
<select id="link-opportunity"></select>
<button class="primary" type="submit">Vincular conversa</button></form></section>
<section class="wide"><h2>Qualificação, propostas e histórico</h2>
<label for="workflow-opportunity">Oportunidade selecionada</label>
<select id="workflow-opportunity" required></select>
<button id="show-workflow">Consultar histórico</button>
<p id="qualification-summary" class="subtle"></p>
<p id="linked-summary" class="subtle"></p></section>
<section><h2>Qualificação comercial</h2>
<form id="qualification-form">
<label><input type="checkbox" id="need-confirmed"> Necessidade confirmada</label>
<label><input type="checkbox" id="budget-confirmed"> Orçamento confirmado</label>
<label><input type="checkbox" id="decision-confirmed"> Decisor identificado</label>
<label for="timeline-days">Prazo de decisão (dias, opcional)</label>
<input type="number" id="timeline-days" min="0" max="3650" step="1">
<button class="primary" type="submit">Salvar qualificação</button></form>
<p class="subtle">Pontuação objetiva de 0 a 100; não altera a etapa automaticamente.</p>
</section>
<section><h2>Preparar proposta comercial</h2>
<form id="proposal-form"><label for="proposal-title">Título</label>
<input id="proposal-title" maxlength="255" required>
<label for="proposal-terms">Condições</label>
<textarea id="proposal-terms" maxlength="4000" required></textarea>
<button class="primary" type="submit">Criar proposta interna</button></form>
<p class="subtle">O valor é o da oportunidade. Aprovação interna não envia nem cobra.</p>
</section>
<section><h2>Registrar atividade</h2><form id="activity-form">
<label for="activity-kind">Tipo</label><select id="activity-kind">
<option value="note">Nota</option><option value="call">Ligação</option>
<option value="meeting">Reunião</option><option value="task">Tarefa</option></select>
<label for="activity-details">Descrição privada</label>
<textarea id="activity-details" maxlength="4000" required></textarea>
<button class="primary" type="submit">Registrar atividade</button></form>
</section>
<section><h2>Propostas internas</h2><div id="proposal-results"></div></section>
<section class="wide"><h2>Linha do tempo comercial</h2>
<div id="activities"></div></section>
</main><script>""" + script + """</script></body></html>"""
    return markup, csp
