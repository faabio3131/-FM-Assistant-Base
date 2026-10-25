"""F8 customer settings: persona, integrations, unit selection and team invitations.

No second auth system, credentials cache or provider calls from the browser.
API permissions remain authoritative; view controls mirror role capability.
"""
from __future__ import annotations

import base64
import hashlib
from html import escape

from .commercial_shell import attach_navigation
from .identity import Permission, permissions_for_role
from .identity_repository import SessionPrincipal


def render_settings(principal: SessionPrincipal) -> tuple[str, str]:
    rights = permissions_for_role(principal.role)
    persona = Permission.PERSONA_READ in rights
    edit_persona = Permission.PERSONA_MANAGE in rights
    integrations = Permission.INTEGRATION_READ in rights
    edit_integrations = Permission.INTEGRATION_MANAGE in rights
    team = Permission.USER_INVITE in rights
    units = Permission.UNIT_READ in rights
    script = r"""
(() => {
"use strict";
const $ = id => document.getElementById(id);
const el = (tag, text, cls) => {
  const item = document.createElement(tag);
  if(text !== undefined) item.textContent = String(text);
  if(cls) item.className=cls;
  return item;
};
function info(node, message) { node.textContent=message; }
async function api(url, method="GET", payload) {
  const opts={method, credentials:"same-origin", cache:"no-store",
    headers:{"Accept":"application/json"}};
  if(payload !== undefined){
    opts.headers["Content-Type"]="application/json";
    opts.body=JSON.stringify(payload);
  }
  const response=await fetch(url,opts);
  const data=response.status===204?{}:await response.json().catch(()=>({}));
  if(!response.ok) {
    if(response.status===401) throw Error("Sessão expirada. Entre novamente.");
    if(response.status===403) throw Error("Permissão insuficiente.");
    if(response.status===404) throw Error("Recurso ainda não configurado.");
    throw Error(data.detail || "Operação indisponível.");
  }
  return data;
}
let inFlight=false;
async function guarded(fn, feedback) {
  if(inFlight) return;
  inFlight=true;
  for(const button of document.querySelectorAll("button")) button.disabled=true;
  try {await fn();}
  catch(err) {info(feedback, "Não concluído: "+err.message);}
  finally {
    inFlight=false;
    for(const button of document.querySelectorAll("button")) button.disabled=false;
  }
}
async function loadPersona() {
  if(!$("persona-view")) return;
  info($("persona-status"),"Consultando persona...");
  try {
    const p=await api("/v1/persona");
    info($("persona-status"),"Persona atual: "+p.public_name+
      " · "+(p.enabled?"ativada":"desativada"));
    if($("persona-form")){
      $("persona-name").value=p.public_name;
      $("persona-language").value=p.language;
      $("persona-tone").value=p.tone;
      $("persona-instructions").value=p.instructions;
      $("persona-enabled").checked=p.enabled;
    }
  } catch(err) {
    info($("persona-status"),"Sem configuração acessível: "+err.message);
  }
}
if($("persona-load"))$("persona-load").addEventListener("click",
  ()=>guarded(loadPersona,$("persona-status")));
if($("persona-form"))$("persona-form").addEventListener("submit",event=>{
  event.preventDefault();
  guarded(async()=>{
    const payload={
      public_name:$("persona-name").value.trim(),
      language:$("persona-language").value.trim(),
      tone:$("persona-tone").value.trim(),
      instructions:$("persona-instructions").value,
      enabled:$("persona-enabled").checked
    };
    const p=await api("/v1/persona","PUT",payload);
    info($("persona-status"),"Persona salva: "+p.public_name+
      ". Configuração da unidade atual.");
  },$("persona-status"));
});
let catalog=[];
function renderProviderFields() {
  const target=$("provider-fields");
  if(!target)return;
  target.replaceChildren();
  const selected=catalog.find(x=>x.provider_key===$("provider-key").value);
  if(!selected)return;
  for(const key of selected.config_fields){
    const label=el("label",key.replaceAll("_"," "));
    const field=el("input");field.type="text";field.maxLength=512;
    field.dataset.field=key;field.autocomplete="off";
    field.required=selected.required_config_fields.includes(key);
    label.append(field);target.append(label);
  }
  for(const key of selected.secret_fields){
    const label=el("label",key.replaceAll("_"," ")+" (segredo)");
    const field=el("input");field.type="password";field.maxLength=4096;
    field.dataset.secret=key;field.autocomplete="new-password";
    label.append(field);target.append(label);
  }
}
async function loadIntegrations(){
  if(!$("integration-list"))return;
  info($("integration-status"),"Carregando conexões...");
  try{
    const [providers,connections]=await Promise.all([
      api("/v1/integrations/catalog"),api("/v1/integrations")
    ]);
    catalog=providers;
    const area=$("integration-list");area.replaceChildren();
    if(!connections.length) area.append(el("p","Nenhuma conexão cadastrada.","muted"));
    for(const c of connections){
      const item=el("article",undefined,"entry");
      const meta=providers.find(x=>x.provider_key===c.provider_key);
      item.append(el("strong",meta?.display_name || c.provider_key));
      item.append(el("p","Estado: "+c.status+" · revisão "+c.revision,"muted"));
      item.append(el("small","Identificador: "+c.connection_id,"muted"));
      area.append(item);
    }
    const picker=$("provider-key");
    if(picker){
      const previous=picker.value;picker.replaceChildren();
      for(const provider of providers){
        const option=el("option",provider.display_name);
        option.value=provider.provider_key;picker.append(option);
      }
      if(providers.some(p=>p.provider_key===previous))picker.value=previous;
      renderProviderFields();
    }
    info($("integration-status"),"Conexões consultadas. Credenciais nunca são exibidas.");
  }catch(err){info($("integration-status"),"Indisponível: "+err.message);}
}
if($("provider-key"))$("provider-key").addEventListener("change",renderProviderFields);
if($("integration-reload"))$("integration-reload").addEventListener("click",
  ()=>guarded(loadIntegrations,$("integration-status")));
if($("integration-form"))$("integration-form").addEventListener("submit",event=>{
  event.preventDefault();
  guarded(async()=>{
    const config={},secrets={};
    for(const field of $("provider-fields").querySelectorAll("input")){
      if(field.dataset.field && field.value.trim())
        config[field.dataset.field]=field.value.trim();
      if(field.dataset.secret && field.value)
        secrets[field.dataset.secret]=field.value;
    }
    const result=await api("/v1/integrations","POST",{
      provider_key:$("provider-key").value,config,secrets,source:"tenant_managed"
    });
    // Sensitive inputs are destroyed before any subsequent refresh.
    for(const field of $("provider-fields").querySelectorAll("input"))field.value="";
    info($("integration-status"),"Conexão "+result.status+
      ". Nenhuma credencial armazenada no navegador.");
    await loadIntegrations();
  },$("integration-status"));
});
async function loadUnits(){
  if(!$("unit-choice"))return;
  info($("unit-status"),"Carregando unidades...");
  try{
    const units=await api("/v1/units");
    const select=$("unit-choice");select.replaceChildren();
    for(const item of units){
      const option=el("option",item.display_name);
      option.value=item.unit_id;select.append(option);
    }
    const active=$("unit-current").dataset.unit;
    if(units.some(x=>x.unit_id===active))select.value=active;
    info($("unit-status"),"A troca de unidade atualizará a sessão ativa.");
  }catch(err){info($("unit-status"),"Indisponível: "+err.message);}
}
if($("unit-form"))$("unit-form").addEventListener("submit",event=>{
  event.preventDefault();
  guarded(async()=>{
    await api("/v1/auth/switch-unit","POST",{unit_id:$("unit-choice").value});
    // Reload forces server-side navigation and scope re-evaluation.
    window.location.assign("/app/settings");
  },$("unit-status"));
});
if($("team-form"))$("team-form").addEventListener("submit",event=>{
  event.preventDefault();
  guarded(async()=>{
    const response=await api("/v1/users/invitations","POST",{
      email:$("invite-email").value.trim(),
      role:$("invite-role").value,
      unit_id:$("invite-unit").value.trim(),
      expires_hours:72
    });
    $("invite-token").value=response.invitation_token;
    info($("team-status"),"Convite criado. Copie o token e compartilhe por canal seguro.");
    $("invite-email").value="";
  },$("team-status"));
});
loadPersona();
loadIntegrations();
loadUnits();
})();
"""
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = (
        "default-src 'none'; script-src 'sha256-" + digest + "'; "
        "style-src 'unsafe-inline'; connect-src 'self'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
    )
    parts = []
    if units:
        parts.append(
            '<section><h2>Unidade ativa</h2>'
            '<p id="unit-current" data-unit="' + escape(principal.unit_id, quote=True)
            + '">Unidade: ' + escape(principal.unit_id) + '</p>'
            '<form id="unit-form"><label for="unit-choice">Selecionar unidade</label>'
            '<select id="unit-choice" required></select>'
            '<button type="submit">Trocar de unidade</button></form>'
            '<p id="unit-status" role="status" aria-live="polite"></p></section>'
        )
    if persona:
        form = ""
        if edit_persona:
            form = (
                '<form id="persona-form">'
                '<label for="persona-name">Nome público da assistente</label>'
                '<input id="persona-name" maxlength="160" required>'
                '<label for="persona-language">Idioma</label>'
                '<input id="persona-language" maxlength="32" value="pt-BR" required>'
                '<label for="persona-tone">Tom de atendimento</label>'
                '<input id="persona-tone" maxlength="120" value="profissional" required>'
                '<label for="persona-instructions">Instruções da assistente</label>'
                '<textarea id="persona-instructions" maxlength="12000"></textarea>'
                '<label><input id="persona-enabled" type="checkbox" checked> '
                'Assistente habilitada</label>'
                '<button type="submit">Salvar persona</button></form>'
            )
        parts.append(
            '<section id="persona-view"><h2>Persona do atendimento</h2>'
            '<p>Nome configurável por cliente e unidade, sem codificação fixa.</p>'
            + form + '<button type="button" id="persona-load">Atualizar persona</button>'
            '<p id="persona-status" role="status" aria-live="polite"></p></section>'
        )
    if integrations:
        form = ""
        if edit_integrations:
            form = (
                '<form id="integration-form"><label for="provider-key">Provedor</label>'
                '<select id="provider-key" required></select>'
                '<div id="provider-fields"></div>'
                '<button type="submit">Salvar conexão configurável</button></form>'
                '<p class="muted">Credenciais são encaminhadas apenas ao backend '
                'autenticado. Não serão exibidas após o envio.</p>'
            )
        parts.append(
            '<section id="integration-workspace"><h2>Integrações</h2>'
            '<p>Provedores cadastrados e configuração por cliente, sem alterar código.</p>'
            + form +
            '<button type="button" id="integration-reload">Atualizar conexões</button>'
            '<p id="integration-status" role="status" aria-live="polite"></p>'
            '<div id="integration-list" aria-live="polite"></div></section>'
        )
    if team:
        parts.append(
            '<section><h2>Equipe</h2><p>Convites específicos por unidade '
            'e papel, sujeitos à permissão validada pelo servidor.</p>'
            '<form id="team-form"><label for="invite-email">E-mail do colaborador</label>'
            '<input id="invite-email" type="email" maxlength="320" required>'
            '<label for="invite-role">Papel</label>'
            '<select id="invite-role"><option value="manager">Gerente</option>'
            '<option value="sales_agent">Comercial</option>'
            '<option value="support_agent">Atendimento</option>'
            '<option value="viewer">Leitura</option></select>'
            '<label for="invite-unit">Identificador da unidade</label>'
            '<input id="invite-unit" maxlength="128" value="'
            + escape(principal.unit_id, quote=True) + '" required>'
            '<button type="submit">Gerar convite interno</button></form>'
            '<label for="invite-token">Token do convite (exibido uma vez)</label>'
            '<textarea id="invite-token" readonly autocomplete="off"></textarea>'
            '<p id="team-status" role="status" aria-live="polite"></p></section>'
        )
    if not parts:
        parts.append('<section><p>Sem configurações disponíveis para este perfil.</p></section>')
    document = (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        '<title>Configurações | VendeAtendeIA</title>'
        '<style>'
        ':root{font:15px/1.5 system-ui,sans-serif;background:#f2f5fa;color:#172c43}'
        '*{box-sizing:border-box}body{margin:0}'
        'main{max-width:1100px;margin:24px auto;padding:0 20px 40px}'
        'h1{font-size:28px;margin:0 0 8px}h2{font-size:18px}'
        '.muted,p[role=status]{color:#5b6c7c}'
        '.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:18px}'
        'section{background:white;border:1px solid #d5e0ed;'
        'border-radius:14px;padding:22px;min-width:0}'
        'label{display:block;font-size:14px;font-weight:600;margin:13px 0 5px}'
        'input,select,textarea{font:inherit;width:100%;border:1px solid #a8bac9;'
        'border-radius:8px;padding:10px;max-width:100%}'
        'textarea{min-height:90px}input[type=checkbox]{width:auto}'
        'button{background:#155d7a;color:white;border:0;border-radius:8px;'
        'font:inherit;padding:10px 16px;margin:12px 8px 0 0;cursor:pointer}'
        'button:disabled{opacity:.55}'
        'button:focus-visible,input:focus-visible,select:focus-visible,'
        'textarea:focus-visible{outline:3px solid #288cab;outline-offset:2px}'
        '.entry{padding:12px;border:1px solid #e3e8ef;border-radius:9px;margin:10px 0}'
        '.entry strong,.entry small{display:block}'
        '</style></head><body><main><h1>Configurações comerciais</h1>'
        '<p>Gestão governada da sua empresa. Permissões verificadas pelo servidor.</p>'
        '<div class="grid">' + "".join(parts) + '</div></main>'
        '<script>' + script + '</script></body></html>'
    )
    return attach_navigation(document, principal, "/app/settings"), csp
