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
const currency = cents => (cents/100).toLocaleString("pt-BR",{
  style:"currency",currency:"BRL"
});
function renderFunnel(data) {
  const summary=$("crm-funnel-summary"), funnel=$("crm-funnel-stages");
  summary.replaceChildren();funnel.replaceChildren();
  const metrics=[
    ["Contatos",data.contacts_total],
    ["Oportunidades",data.opportunities_total],
    ["Em aberto",data.open_opportunities],
    ["Funil aberto",currency(data.open_pipeline_cents)],
    ["Ganhas",data.won_opportunities],
    ["Valor ganho",currency(data.won_opportunity_value_cents)],
    ["Perdidas",data.lost_opportunities],
    ["Conversão de encerradas",data.win_rate_basis_points===null?
      "Sem encerradas":(data.win_rate_basis_points/100).toFixed(2)+"%"]
  ];
  for(const [label,value] of metrics){
    const card=el("article",undefined,"entry");
    card.append(el("small",label,"subtle"),el("strong",value));summary.append(card);
  }
  for(const stage of ["new","qualified","proposal","won","lost"]){
    const row=data.stages[stage], entry=el("span",
      labels[stage]+": "+row.count+" · "+currency(row.amount_cents),"subtle");
    funnel.append(entry);
  }
}
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
  const policyContact=$("followup-contact"), remembered=policyContact.value;
  policyContact.replaceChildren();
  for(const contact of contacts){
    const option=el("option",contact.name);option.value=contact.contact_id;
    policyContact.append(option);
  }
  if(contacts.some(c=>c.contact_id===remembered))policyContact.value=remembered;
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
    let reason=null;
    if ((stages[item.stage] || []).some(next=>["won","lost"].includes(next))) {
      reason=el("input");
      reason.type="text";reason.maxLength=500;
      reason.placeholder="Motivo do resultado (opcional; privado)";
      reason.setAttribute("aria-label","Motivo do resultado comercial");
      row.append(reason);
    }
    for (const next of stages[item.stage] || []) {
      const button=el("button","Mover para "+labels[next]);
      button.type="button";
      button.addEventListener("click",() => guarded(async () => {
        const outcome_reason=["won","lost"].includes(next) && reason?
          reason.value.trim() || null:null;
        await api("/v1/crm/opportunities/"+encodeURIComponent(item.opportunity_id)+
          "/transition","POST",{expected_revision:item.revision,stage:next,
            outcome_reason});
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
    api("/v1/crm/opportunities?stage="+encodeURIComponent($("stage-filter").value)),
    api("/v1/crm/analytics")
  ]);
  contacts=results[0].items;
  opportunities=results[1].items;
  renderContacts();
  renderOpportunities();
  renderFunnel(results[2]);
  await loadF7();
  await loadAgenda();
  $("contact-more").textContent = results[0].next_page !== null ?
    "Mostrando 50 contatos; consulte as próximas páginas pela API." : "";
  $("opportunity-more").textContent = results[1].next_page !== null ?
    "Mostrando 50 oportunidades; consulte as próximas páginas pela API." : "";
}
async function loadFollowupPolicy(){
  const contactId=$("followup-contact").value, channel=$("followup-channel").value;
  if(!contactId){$("followup-status").textContent="Cadastre um contato primeiro.";return;}
  const data=await api("/v1/followups/contacts/"+
    encodeURIComponent(contactId)+"/preferences?channel="+encodeURIComponent(channel));
  $("followup-status").textContent=data.configured?
    "Política ativa · revisão "+data.revision+" · "+data.reason:
    "Sem política: envio automatizado bloqueado por padrão.";
  $("followup-optout").checked=data.opted_out===true;
  if(data.timezone)$("followup-timezone").value=data.timezone;
  if(data.quiet_start)$("followup-start").value=data.quiet_start;
  if(data.quiet_end)$("followup-end").value=data.quiet_end;
}
$("followup-contact").addEventListener("change",()=>guarded(loadFollowupPolicy));
$("followup-channel").addEventListener("change",()=>guarded(loadFollowupPolicy));
$("followup-load").addEventListener("click",()=>guarded(loadFollowupPolicy));
$("followup-form").addEventListener("submit",event=>{
  event.preventDefault();guarded(async()=>{
    const contactId=$("followup-contact").value;
    if(!contactId)throw Error("Selecione um contato.");
    const root="/v1/followups/contacts/"+encodeURIComponent(contactId)+"/preferences";
    const channel=$("followup-channel").value;
    const before=await api(root+"?channel="+encodeURIComponent(channel));
    const result=await api(root,"PUT",{
      channel,expected_revision:before.revision,
      opted_out:$("followup-optout").checked,
      timezone:$("followup-timezone").value,
      quiet_start:$("followup-start").value,
      quiet_end:$("followup-end").value
    });
    $("followup-status").textContent="Política salva · revisão "+result.revision+
      " · "+result.reason+". Sem envio ou agendamento.";
    notice("Preferências comerciais atualizadas para o contato.");
  });
});
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


let cadenceDefinitions=[], cadenceRuns=[], pendingRunKey=null;
function renderF7Selectors() {
  const contact=$("cadence-contact"), selected=contact.value;
  contact.replaceChildren();
  for(const item of contacts){
    const option=el("option",item.name);option.value=item.contact_id;contact.append(option);
  }
  if(contacts.some(x=>x.contact_id===selected))contact.value=selected;
  renderF7OpportunityChoices();
}
function renderF7OpportunityChoices() {
  const select=$("cadence-opportunity"), current=select.value;
  select.replaceChildren();
  for(const opp of opportunities.filter(o=>o.contact_id===$("cadence-contact").value &&
      !["won","lost"].includes(o.stage))){
    const option=el("option",opp.title);option.value=opp.opportunity_id;select.append(option);
  }
  if([...select.options].some(o=>o.value===current))select.value=current;
}
function renderF7() {
  const definitions=$("cadence-definitions"), runs=$("cadence-runs");
  const selector=$("cadence-choice"), old=selector.value;
  definitions.replaceChildren();runs.replaceChildren();selector.replaceChildren();
  const latest=new Map();
  for(const item of cadenceDefinitions){
    if(!latest.has(item.cadence_id))latest.set(item.cadence_id,item);
  }
  for(const item of latest.values()){
    const option=el("option",item.name+" · v"+item.version+" · "+item.channel);
    option.value=item.cadence_id+":"+item.version;selector.append(option);
    definitions.append(el("p",item.name+" · versão "+item.version+" · "+item.channel,"subtle"));
  }
  if([...selector.options].some(o=>o.value===old))selector.value=old;
  if(!selector.options.length)definitions.append(el("p","Crie uma cadência primeiro.","subtle"));
  if(!cadenceRuns.length)runs.append(el("p","Nenhuma execução encontrada.","subtle"));
  for(const run of cadenceRuns){
    const card=el("article",undefined,"entry");
    const title=latest.get(run.cadence_id)?.name || "Cadência";
    card.append(el("strong",title+" · "+run.status));
    const contact=contacts.find(x=>x.contact_id===run.contact_id)?.name || "Contato";
    card.append(el("small",contact+" · "+run.jobs.length+" etapas · "+
      run.run_id.slice(0,8),"subtle"));
    for(const job of run.jobs){
      card.append(el("small","Etapa "+(job.step_index+1)+": "+job.state+
        " · "+new Date(job.due_at).toLocaleString("pt-BR")+
        " · tentativas "+job.attempt_count,"subtle"));
    }
    const actions=el("div",undefined,"actions");
    const events=el("button","Ver auditoria");
    events.type="button";
    events.addEventListener("click",()=>guarded(async()=>{
      const data=await api("/v1/followups/runs/"+encodeURIComponent(run.run_id)+"/events");
      const log=el("div");
      for(const item of data.items){
        log.append(el("small",new Date(item.created_at).toLocaleString("pt-BR")+
          " · "+item.action+(item.reason?" · "+item.reason:""),"subtle"));
      }
      if(!data.items.length)log.append(el("small","Sem eventos.","subtle"));
      card.append(log);
    }));
    actions.append(events);
    if(run.status==="active"){
      const cancel=el("button","Cancelar cadência");
      cancel.type="button";
      cancel.addEventListener("click",()=>guarded(async()=>{
        await api("/v1/followups/runs/"+encodeURIComponent(run.run_id)+"/cancel","POST");
        notice("Cadência cancelada; nenhum envio externo foi executado.");
        await loadF7();
      }));
      actions.append(cancel);
    }
    card.append(actions);runs.append(card);
  }
  $("cadence-more").textContent=cadenceHasMore?
    "Mostrando 50 execuções; consulte as demais via API.":"";
}
let cadenceHasMore=false;
async function loadF7(){
  const [defs,runs]=await Promise.all([
    api("/v1/followups/cadences"),api("/v1/followups/runs")
  ]);
  cadenceDefinitions=defs.items;
  cadenceRuns=runs.items;
  cadenceHasMore=runs.has_more;
  renderF7Selectors();
  renderF7();
}
$("cadence-contact").addEventListener("change",renderF7OpportunityChoices);
$("cadence-reload").addEventListener("click",()=>guarded(loadF7));
$("cadence-definition-form").addEventListener("submit",event=>{
  event.preventDefault();
  guarded(async()=>{
    const steps=[{delay_minutes:0,task:$("cadence-task1").value.trim()}];
    const task2=$("cadence-task2").value.trim();
    if(task2){
      steps.push({delay_minutes:Number($("cadence-delay2").value),task:task2});
    }
    const created=await api("/v1/followups/cadences","POST",{
      name:$("cadence-name").value.trim(),channel:$("cadence-channel").value,steps
    });
    notice("Cadência criada na versão "+created.version+".");
    $("cadence-definition-form").reset();
    await loadF7();
  });
});
$("cadence-run-form").addEventListener("submit",event=>{
  event.preventDefault();
  guarded(async()=>{
    const [cadence_id,version]=$("cadence-choice").value.split(":");
    const start=new Date($("cadence-start").value);
    if(!Number.isFinite(start.getTime()))throw Error("Data e horário inválidos.");
    if(!pendingRunKey)pendingRunKey=crypto.randomUUID();
    const result=await api("/v1/followups/runs","POST",{
      cadence_id,version:Number(version),
      contact_id:$("cadence-contact").value,
      opportunity_id:$("cadence-opportunity").value,
      idempotency_key:pendingRunKey,start_at:start.toISOString()
    });
    pendingRunKey=null;
    notice("Execução "+result.run_id.slice(0,8)+" criada com "+
      result.jobs.length+" tarefas internas. Sem disparos externos.");
    await loadF7();
  });
});


let agendaItems=[], pendingAgendaKey=null;
function localDatetime(value) {
  const date=new Date(value), offset=date.getTimezoneOffset()*60000;
  return new Date(date.getTime()-offset).toISOString().slice(0,16);
}
function renderAgendaOpportunityChoices() {
  const select=$("agenda-opportunity"), previous=select.value;
  select.replaceChildren();
  for(const opp of opportunities.filter(x=>x.contact_id===$("agenda-contact").value &&
      !["won","lost"].includes(x.stage))){
    const option=el("option",opp.title);
    option.value=opp.opportunity_id;select.append(option);
  }
  if([...select.options].some(x=>x.value===previous))select.value=previous;
}
function renderAgenda(){
  const contactSelect=$("agenda-contact"), previous=contactSelect.value;
  contactSelect.replaceChildren();
  for(const contact of contacts){
    const option=el("option",contact.name);option.value=contact.contact_id;
    contactSelect.append(option);
  }
  if(contacts.some(x=>x.contact_id===previous))contactSelect.value=previous;
  renderAgendaOpportunityChoices();
  const area=$("agenda-results");area.replaceChildren();
  if(!agendaItems.length)area.append(el("p","Nenhum compromisso encontrado.","subtle"));
  for(const item of agendaItems){
    const card=el("article",undefined,"entry");
    card.append(el("strong",item.title+" · "+item.status));
    const contact=contacts.find(x=>x.contact_id===item.contact_id)?.name || "Contato";
    card.append(el("small",contact+" · "+
      new Date(item.starts_at).toLocaleString("pt-BR")+" a "+
      new Date(item.ends_at).toLocaleString("pt-BR")+
      " · revisão "+item.revision,"subtle"));
    const actions=el("div",undefined,"actions");
    const audit=el("button","Histórico");
    audit.type="button";
    audit.addEventListener("click",()=>guarded(async()=>{
      const result=await api("/v1/followups/agenda/"+
        encodeURIComponent(item.appointment_id)+"/events");
      const log=el("div");
      for(const x of result.items)log.append(el("small",x.action+" · "+
        new Date(x.created_at).toLocaleString("pt-BR"),"subtle"));
      card.append(log);
    }));
    actions.append(audit);
    if(item.status==="scheduled"){
      const start=el("input");
      start.type="datetime-local";start.value=localDatetime(item.starts_at);
      start.setAttribute("aria-label","Novo horário do compromisso "+item.title);
      const duration=el("input");
      duration.type="number";duration.min="15";duration.max="480";
      duration.value=String(Math.round(
        (new Date(item.ends_at)-new Date(item.starts_at))/60000));
      duration.setAttribute("aria-label","Nova duração em minutos");
      card.append(start,duration);
      const reschedule=el("button","Remarcar");
      reschedule.type="button";
      reschedule.addEventListener("click",()=>guarded(async()=>{
        const when=new Date(start.value);
        if(!Number.isFinite(when.getTime()))throw Error("Data inválida.");
        await api("/v1/followups/agenda/"+
          encodeURIComponent(item.appointment_id)+"/reschedule","POST",{
            expected_revision:item.revision,starts_at:when.toISOString(),
            duration_minutes:Number(duration.value)
          });
        notice("Compromisso remarcado.");
        await loadAgenda();
      }));
      actions.append(reschedule);
      for(const [action,label] of [["cancel","Cancelar"],["complete","Concluir"]]){
        const button=el("button",label);
        button.type="button";
        button.addEventListener("click",()=>guarded(async()=>{
          await api("/v1/followups/agenda/"+
            encodeURIComponent(item.appointment_id)+"/"+action,
            "POST",{expected_revision:item.revision});
          notice("Compromisso atualizado: "+label+".");
          await loadAgenda();
        }));
        actions.append(button);
      }
    }
    card.append(actions);area.append(card);
  }
}
async function loadAgenda(){
  const now=Date.now();
  const from=new Date(now-86400000).toISOString();
  const to=new Date(now+30*86400000).toISOString();
  const result=await api("/v1/followups/agenda?start_at="+
    encodeURIComponent(from)+"&end_at="+encodeURIComponent(to));
  agendaItems=result.items;
  $("agenda-more").textContent=result.has_more?
    "Mostrando 100 compromissos. Consulte os demais pela API.":"";
  renderAgenda();
}
$("agenda-contact").addEventListener("change",renderAgendaOpportunityChoices);
$("agenda-refresh").addEventListener("click",()=>guarded(loadAgenda));
$("agenda-form").addEventListener("submit",event=>{
  event.preventDefault();
  guarded(async()=>{
    const start=new Date($("agenda-start").value);
    if(!Number.isFinite(start.getTime()))throw Error("Data e horário inválidos.");
    if(!pendingAgendaKey)pendingAgendaKey=crypto.randomUUID();
    const saved=await api("/v1/followups/agenda","POST",{
      contact_id:$("agenda-contact").value,
      opportunity_id:$("agenda-opportunity").value,
      title:$("agenda-title").value.trim(),
      starts_at:start.toISOString(),
      duration_minutes:Number($("agenda-duration").value),
      remind_minutes:Number($("agenda-reminder").value),
      idempotency_key:pendingAgendaKey
    });
    pendingAgendaKey=null;
    notice("Compromisso agendado: "+saved.title+". Lembretes são tarefas internas.");
    $("agenda-form").reset();
    await loadAgenda();
  });
});
$("agenda-slots").addEventListener("click",()=>guarded(async()=>{
  const start=new Date($("agenda-start").value);
  if(!Number.isFinite(start.getTime()))throw Error("Defina a data inicial.");
  const end=new Date(start.getTime()+4*3600000);
  const result=await api("/v1/followups/agenda/slots?start_at="+
    encodeURIComponent(start.toISOString())+"&end_at="+
    encodeURIComponent(end.toISOString())+"&duration_minutes="+
    encodeURIComponent($("agenda-duration").value));
  const area=$("agenda-slot-results");area.replaceChildren();
  for(const slot of result.items){
    area.append(el("small",new Date(slot.starts_at).toLocaleString("pt-BR")+
      " · "+(slot.available?"Livre":"Ocupado"),"subtle"));
  }
}));
$("agenda-start").value=localDatetime(new Date(Date.now()+3600000));

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
.crm-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px}
.crm-metrics .entry{margin:0}
.crm-stages{display:flex;flex-wrap:wrap;gap:15px;margin-top:16px}
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
<section class="wide"><h2>Indicadores comerciais da unidade</h2>
<p class="subtle">Valores de oportunidades, não faturamento, pagamentos ou receita contábil.</p>
<div id="crm-funnel-summary" class="crm-metrics"></div>
<div id="crm-funnel-stages" class="crm-stages"></div></section>
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

<section class="wide"><h2>F7 · Preferências de acompanhamento</h2>
<p class="subtle">Opt-out e horários de silêncio por contato e canal.
Sem política configurada, o envio automatizado é bloqueado. Esta etapa não envia mensagens.</p>
<form id="followup-form">
<label for="followup-contact">Contato</label><select id="followup-contact" required></select>
<label for="followup-channel">Canal</label>
<select id="followup-channel"><option value="whatsapp">WhatsApp</option>
<option value="email">E-mail</option></select>
<label for="followup-timezone">Fuso horário (IANA)</label>
<input id="followup-timezone" value="America/Sao_Paulo" maxlength="64" required>
<label for="followup-start">Início do silêncio</label>
<input type="time" id="followup-start" value="22:00" required>
<label for="followup-end">Fim do silêncio</label>
<input type="time" id="followup-end" value="08:00" required>
<label><input type="checkbox" id="followup-optout"> Não contatar (opt-out)</label>
<p class="subtle">Após marcar opt-out, só um novo consentimento comprovado poderá reativar o contato.</p>
<div class="actions"><button id="followup-load" type="button">Consultar preferência</button>
<button class="primary" type="submit">Salvar preferência</button></div>
</form><p id="followup-status" class="subtle" role="status"></p></section>
<section class="wide"><h2>F7 · Cadências comerciais</h2>
<p class="subtle">Regras versionadas e tarefas internas. Nenhuma mensagem é enviada automaticamente.</p>
<form id="cadence-definition-form">
<label for="cadence-name">Nome da cadência</label>
<input id="cadence-name" maxlength="120" required>
<label for="cadence-channel">Canal de consentimento</label>
<select id="cadence-channel"><option value="whatsapp">WhatsApp</option>
<option value="email">E-mail</option></select>
<label for="cadence-task1">Primeira tarefa interna (imediata)</label>
<textarea id="cadence-task1" maxlength="500" required></textarea>
<label for="cadence-task2">Segunda tarefa interna (opcional)</label>
<textarea id="cadence-task2" maxlength="500"></textarea>
<label for="cadence-delay2">Minutos até a segunda tarefa</label>
<input id="cadence-delay2" type="number" value="60" min="1" max="43200" step="1">
<button class="primary" type="submit">Criar regra versionada</button>
</form>
<div id="cadence-definitions" aria-live="polite"></div></section>
<section class="wide"><h2>Agendamento e acompanhamento de cadências</h2>
<form id="cadence-run-form">
<label for="cadence-choice">Cadência e versão</label><select id="cadence-choice" required></select>
<label for="cadence-contact">Contato</label><select id="cadence-contact" required></select>
<label for="cadence-opportunity">Oportunidade aberta</label>
<select id="cadence-opportunity" required></select>
<label for="cadence-start">Início (horário local)</label>
<input id="cadence-start" type="datetime-local" required>
<button class="primary" type="submit">Agendar tarefas internas</button></form>
<div class="actions"><button id="cadence-reload" type="button">Atualizar execuções</button></div>
<div id="cadence-runs" aria-live="polite"></div>
<p id="cadence-more" class="subtle"></p></section>
<section class="wide"><h2>F7 · Agenda e compromissos internos</h2>
<p class="subtle">Horários por usuário, prevenção de conflitos e lembretes como tarefas privadas no CRM. Sem mensagem automática ao cliente.</p>
<form id="agenda-form">
<label for="agenda-contact">Contato</label><select id="agenda-contact" required></select>
<label for="agenda-opportunity">Oportunidade aberta</label>
<select id="agenda-opportunity" required></select>
<label for="agenda-title">Compromisso (privado)</label>
<input id="agenda-title" maxlength="200" required>
<label for="agenda-start">Início (horário local)</label>
<input id="agenda-start" type="datetime-local" required>
<label for="agenda-duration">Duração (minutos)</label>
<input id="agenda-duration" type="number" min="15" max="480" step="1" value="60" required>
<label for="agenda-reminder">Antecedência do lembrete interno (minutos; zero desativa)</label>
<input id="agenda-reminder" type="number" min="0" max="10080" step="1" value="60" required>
<div class="actions"><button class="primary" type="submit">Agendar compromisso</button>
<button id="agenda-slots" type="button">Consultar horários próximos</button></div>
</form><div id="agenda-slot-results" class="crm-stages" aria-live="polite"></div>
<div class="actions"><button id="agenda-refresh" type="button">Atualizar agenda</button></div>
<div id="agenda-results" aria-live="polite"></div><p id="agenda-more" class="subtle"></p>
</section>
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
