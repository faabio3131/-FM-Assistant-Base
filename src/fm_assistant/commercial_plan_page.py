"""F8 customer plan workspace over the existing authenticated usage authority.

Never invent balance or expose private FM costs. The API, not the browser,
determines tenant/unit, licensed plan and authorization.
"""
from __future__ import annotations

import base64
import hashlib
from html import escape

from .commercial_shell import attach_navigation
from .identity_repository import SessionPrincipal


def render_plan_page(principal: SessionPrincipal) -> tuple[str, str]:
    script = r"""
(() => {
"use strict";
const $ = id => document.getElementById(id);
const node = (tag, text, cls) => {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = String(text);
  if (cls) item.className = cls;
  return item;
};
const status = $("fm-plan-status");
const summary = $("fm-plan-summary");
const rows = $("fm-plan-rows");
const capabilities = $("fm-plan-capabilities");
const reload = $("fm-plan-reload");
const legacy = $("fm-plan-detail");
let loading = false;
function reset(message) {
  summary.replaceChildren();
  rows.replaceChildren();
  capabilities.replaceChildren();
  legacy.hidden = true;
  status.textContent = message;
}
async function fetchJSON(url) {
  const response = await fetch(url, {credentials:"same-origin",
    cache:"no-store", headers:{"Accept":"application/json"}});
  const data = await response.json().catch(() => ({}));
  return {response, data};
}
function showPlan(data) {
  if (!data || typeof data.plan_name !== "string" ||
      !Array.isArray(data.consumption)) {
    reset("A resposta do plano não pôde ser validada.");
    return false;
  }
  summary.append(
    node("h2", data.plan_name),
    node("p", "Vigência informada: " +
      (typeof data.licensed_until === "string" ? data.licensed_until : "não disponível")),
    node("p", "Os recursos do SaaS são oferecidos em todos os planos; "+
      "as franquias variam conforme o contrato.")
  );
  if (!data.consumption.length) {
    rows.append(node("p", "Não há franquias verificáveis para exibição."));
  }
  for (const reading of data.consumption) {
    if (!reading || typeof reading.resource !== "string" ||
        /(cost|price|secret|credential|key)/i.test(reading.resource)) continue;
    const box = node("article", undefined, "fm-plan-card");
    box.append(node("h3", reading.resource));
    if (Number.isSafeInteger(reading.limit_units) && reading.limit_units >= 0) {
      box.append(node("p", "Franquia contratada: " + reading.limit_units));
    }
    const verified = reading.status === "observed" &&
      ["consumed_units","reserved_units","remaining_units"].every(
        key => Number.isSafeInteger(reading[key]) && reading[key] >= 0
      );
    if (verified) {
      box.append(node("p", reading.consumed_units + " utilizados · " +
        reading.reserved_units + " reservados · " +
        reading.remaining_units + " disponíveis"));
      if (Number.isSafeInteger(reading.utilization_percent) &&
          reading.utilization_percent >= 0) {
        const progress = node("progress");
        progress.max = 100;
        progress.value = Math.min(100, reading.utilization_percent);
        progress.setAttribute("aria-label", "Franquia utilizada: " +
          reading.resource);
        box.append(progress);
      }
    } else {
      box.append(node("p", "Saldo não verificado. Aguardando telemetria autenticada.",
        "fm-plan-unknown"));
    }
    rows.append(box);
  }
  legacy.hidden = false;
  status.textContent = data.usage_verified === true ?
    "Plano e consumo consultados com medições verificadas." :
    "Plano consultado. Uma ou mais medições de consumo não estão verificadas.";
  return true;
}
async function load() {
  if (loading) return;
  loading = true;
  reload.disabled = true;
  $("fm-plan").setAttribute("aria-busy", "true");
  reset("Consultando plano e franquias desta unidade...");
  try {
    const {response, data} = await fetchJSON("/v1/plan/consumption");
    if (response.status === 401) {
      reset("Sessão expirada. Entre novamente.");
      const login = node("a", "Entrar novamente");
      login.href = "/app/login";
      summary.append(login);
      return;
    }
    if (response.status === 403 && data.detail === "plan_unavailable") {
      reset("Plano ou licença ainda não disponível para consulta. "+
        "Nenhum saldo foi presumido.");
      return;
    }
    if (!response.ok) {
      reset(response.status === 403 ? "Seu perfil não possui acesso ao plano." :
        "Não foi possível consultar o plano. Atualize para tentar novamente.");
      return;
    }
    if (!showPlan(data)) return;
    try {
      const result = await fetchJSON("/v1/entitlements");
      if (result.response.ok && Array.isArray(result.data)) {
        const list = result.data.filter(item => item &&
          typeof item.capability === "string" &&
          !/(cost|price|secret|credential|key)/i.test(item.capability));
        capabilities.append(node("h2", "Permissões e capacidades do plano"));
        if (!list.length) capabilities.append(
          node("p", "Nenhuma capacidade individual informada.")
        );
        for (const item of list) {
          capabilities.append(node("p", item.capability + " · " +
            (item.enabled === true ? "Habilitada" : "Não habilitada")));
        }
      } else {
        capabilities.append(node("p",
          "A relação de capacidades não está disponível no momento."));
      }
    } catch {
      capabilities.append(node("p",
        "A relação de capacidades não está disponível no momento."));
    }
  } catch {
    reset("Serviço indisponível. Atualize para tentar novamente.");
  } finally {
    $("fm-plan").setAttribute("aria-busy", "false");
    loading = false;
    reload.disabled = false;
  }
}
reload.addEventListener("click", load);
load();
})();
"""
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = (
        "default-src 'none'; script-src 'sha256-" + digest + "'; "
        "style-src 'unsafe-inline'; connect-src 'self'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    html = (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        '<title>Meu plano | VendeAtendeIA</title>'
        '<style>'
        ':root{font:15px/1.5 system-ui,sans-serif;background:#f3f6fa;color:#182f42}'
        '*{box-sizing:border-box}body{margin:0}'
        'main{max-width:1120px;margin:28px auto;padding:0 20px 48px}'
        'h1{font-size:clamp(24px,5vw,36px)}h2{font-size:21px}'
        '.fm-plan-grid{display:grid;grid-template-columns:'
        'repeat(auto-fit,minmax(min(100%,260px),1fr));gap:16px}'
        '.fm-plan-card{background:white;border:1px solid #d3e1ec;'
        'border-radius:13px;padding:18px;min-width:0;overflow-wrap:anywhere}'
        '.fm-plan-card h3{font-size:16px;margin:0 0 10px}'
        '.fm-plan-unknown{color:#71552a}progress{width:100%;height:13px}'
        '#fm-plan-summary,#fm-plan-capabilities{margin:16px 0}'
        '#fm-plan-status{min-height:24px;color:#375c73}'
        '.fm-action{display:inline-flex;padding:12px 16px;background:white;'
        'border:1px solid #a8c2d1;border-radius:9px;text-decoration:none;'
        'color:#104f70;margin:12px 0}'
        'button{font:inherit;background:#175c78;color:white;'
        'border:0;border-radius:8px;padding:10px 18px;cursor:pointer}'
        'button:disabled{opacity:.6}'
        'button:focus-visible,a:focus-visible{outline:3px solid #077ca2;'
        'outline-offset:3px}'
        '</style></head><body><main><h1>Meu plano e consumo</h1>'
        '<p>Informações do contrato da unidade <strong>'
        + escape(principal.unit_id)
        + '</strong>. Uso e saldo só aparecem quando comprovados.</p>'
        '<button id="fm-plan-reload" type="button">Atualizar informações</button>'
        '<div id="fm-plan" aria-busy="true">'
        '<p id="fm-plan-status" role="status" aria-live="polite">Carregando...</p>'
        '<section id="fm-plan-summary" aria-label="Plano contratado"></section>'
        '<section id="fm-plan-rows" class="fm-plan-grid" '
        'aria-label="Franquias e consumo"></section>'
        '<section id="fm-plan-capabilities" '
        'aria-label="Capacidades do plano"></section>'
        '</div><a id="fm-plan-detail" class="fm-action" '
        'href="/v1/plan/consumption/dashboard" hidden>'
        'Ver franquias detalhadas</a>'
        '<p>Esta área não informa preços nem custos privados da FM Tecnologia.</p>'
        '</main><script>' + script + '</script></body></html>'
    )
    return attach_navigation(html, principal, "/app/plan"), csp
