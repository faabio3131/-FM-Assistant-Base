"""F8 shared commercial navigation and authenticated single-product home.

Existing CRM, knowledge, inbox, QR and consumption pages retain their own
controllers and hashed scripts. This layer adds navigation only, never
introduces a second business service or browser-side authorization authority.
"""
from __future__ import annotations

import base64
import hashlib
import json
from html import escape

from .identity import Permission, permissions_for_role
from .identity_repository import SessionPrincipal

_NAVIGATION = (
    ("Visão geral", "/app", None),
    ("Atendimento", "/app/inbox", Permission.CONVERSATION_READ),
    ("CRM e pipeline", "/app/crm", Permission.CRM_READ),
    ("Agenda", "/app/crm#agenda-workspace", Permission.CRM_READ),
    ("Cadências", "/app/crm#cadence-workspace", Permission.CRM_READ),
    ("Conhecimento", "/app/knowledge", Permission.KNOWLEDGE_READ),
    ("WhatsApp", "/v1/channels/whatsapp/qr/panel", Permission.INTEGRATION_READ),
    ("Plano e consumo", "/v1/plan/consumption/dashboard", Permission.BILLING_READ),
)

_NAV_STYLE = """
<style>
#fm-shell{box-sizing:border-box;background:#101f38;color:#eef5ff;
 padding:12px max(18px,calc((100vw - 1340px)/2));width:100%;
 font:500 14px/1.5 system-ui,Arial,sans-serif;
 border-bottom:1px solid #334862}
#fm-shell *{box-sizing:border-box}
#fm-shell .fm-nav-inner{display:flex;align-items:center;gap:16px;
 justify-content:space-between;flex-wrap:wrap}
#fm-shell .fm-brand{color:#f5fbff;text-decoration:none;font-weight:800;
 letter-spacing:.015em;font-size:16px;white-space:nowrap}
#fm-shell .fm-links{display:flex;gap:4px;flex-wrap:wrap;align-items:center}
#fm-shell a.fm-tab{display:inline-flex;text-decoration:none;color:#d6e5fb;
 padding:8px 10px;border:1px solid transparent;border-radius:9px}
#fm-shell a.fm-tab[aria-current="page"]{background:#25516b;
 border-color:#3b7594;color:white}
#fm-shell a.fm-tab:hover,#fm-shell a.fm-tab:focus-visible{
 background:#2d5472;color:white}
#fm-shell a:focus-visible{outline:3px solid #a5ebdf;outline-offset:2px}
#fm-shell .fm-scope{color:#a8c0d6;font-size:12px;
 overflow-wrap:anywhere;max-width:290px}
@media(max-width:760px){
 #fm-shell{padding:12px 14px}
 #fm-shell .fm-links{width:100%;overflow-x:auto;flex-wrap:nowrap;
 padding-bottom:5px}
 #fm-shell .fm-tab{white-space:nowrap}
 #fm-shell .fm-scope{max-width:100%}
}
</style>
"""


def allowed_navigation(principal: SessionPrincipal) -> tuple[tuple[str, str], ...]:
    permissions = permissions_for_role(principal.role)
    return tuple(
        (label, href) for label, href, permission in _NAVIGATION
        if permission is None or permission in permissions
    )


def navigation_markup(principal: SessionPrincipal, current: str) -> str:
    items = []
    for label, href in allowed_navigation(principal):
        base = href.split("#", 1)[0]
        active = current == href or (base == current and base != "/app/crm")
        state = ' aria-current="page"' if active else ""
        items.append(
            '<a class="fm-tab" href="' + escape(href, quote=True) + '"'
            + state + ">" + escape(label) + "</a>"
        )
    return (
        '<nav id="fm-shell" aria-label="Navegação principal">'
        '<div class="fm-nav-inner"><a class="fm-brand" href="/app">'
        'VendeAtendeIA</a><div class="fm-links">'
        + "".join(items) + '</div><span class="fm-scope">'
        + escape(principal.display_name) + ' · Unidade '
        + escape(principal.unit_id) + "</span></div></nav>"
    )


def attach_navigation(html: str, principal: SessionPrincipal, current: str) -> str:
    """Inject static, escaped navigation without touching page JS/CSP hashes."""
    if 'id="fm-shell"' in html:
        raise ValueError("commercial_shell_already_attached")
    if html.count("</head>") != 1 or html.count("<body>") != 1:
        raise ValueError("commercial_shell_document_invalid")
    return (html.replace("</head>", _NAV_STYLE + "</head>", 1)
            .replace("<body>", "<body>" + navigation_markup(principal, current), 1))


def render_home(principal: SessionPrincipal) -> tuple[str, str]:
    permissions = permissions_for_role(principal.role)
    sources = []
    if Permission.CRM_READ in permissions:
        sources.append({
            "key": "crm", "label": "Oportunidades em aberto",
            "url": "/v1/crm/analytics", "field": "open_opportunities",
            "href": "/app/crm",
        })
    if Permission.CONVERSATION_READ in permissions:
        sources.append({
            "key": "inbox", "label": "Atendimento humano",
            "url": "/v1/inbox?page=0&limit=50", "field": "items",
            "href": "/app/inbox",
        })
    if Permission.KNOWLEDGE_READ in permissions:
        sources.append({
            "key": "knowledge", "label": "Fontes de conhecimento",
            "url": "/v1/knowledge/sources?page=0", "field": "items",
            "href": "/app/knowledge",
        })
    if Permission.CRM_READ in permissions:
        sources.append({
            "key": "agenda", "label": "Próximos compromissos",
            "url": "/v1/followups/agenda", "field": "items",
            "href": "/app/crm#agenda-workspace",
        })

    source_json = json.dumps(sources, ensure_ascii=False, separators=(",", ":"))
    script = r"""
(() => {
"use strict";
const specs = __SOURCES__;
const root = document.getElementById("fm-overview");
const globalStatus = document.getElementById("fm-status");
const refresh = document.getElementById("fm-reload");
const dom = (tag, value, className) => {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = String(value);
  if (className) node.className = className;
  return node;
};
const statusLabel = (code) => {
  if (code === 401) return "Sessão expirada. Entre novamente.";
  if (code === 403) return "Acesso restrito ao seu perfil.";
  if (code === 503) return "Serviço temporariamente indisponível.";
  return "Não foi possível consultar este módulo.";
};
let loading = false;
async function load() {
  if (loading) return;
  loading = true;
  refresh.disabled = true;
  root.replaceChildren();
  globalStatus.textContent = "Consultando as informações da unidade...";
  const now = new Date();
  const start = now.toISOString();
  const end = new Date(now.getTime() + 30 * 86400000).toISOString();
  const results = await Promise.all(specs.map(async spec => {
    const url = spec.key === "agenda" ?
      spec.url + "?start_at=" + encodeURIComponent(start) +
      "&end_at=" + encodeURIComponent(end) : spec.url;
    try {
      const response = await fetch(url, {credentials:"same-origin",
        cache:"no-store", headers:{"Accept":"application/json"}});
      if (!response.ok) return {spec, error: statusLabel(response.status)};
      const json = await response.json();
      const value = json[spec.field];
      if (spec.field === "items" && Array.isArray(value)) {
        const more = json.has_more === true || json.next_page !== null &&
          json.next_page !== undefined;
        return {spec, value: String(value.length) + (more ? "+" : "")};
      }
      if (typeof value === "number" && Number.isFinite(value)) {
        return {spec, value: String(value)};
      }
      return {spec, error: "Dados não verificados."};
    } catch {
      return {spec, error: "Serviço não disponível."};
    }
  }));
  let failed = 0;
  for (const result of results) {
    const card = dom("article", undefined, "fm-tile");
    const heading = dom("h2", result.spec.label);
    const value = dom("p", result.error || result.value,
      result.error ? "fm-unavailable" : "fm-value");
    if (result.error) failed++;
    const link = dom("a", "Abrir módulo");
    link.href = result.spec.href;
    card.append(heading, value, link);
    root.append(card);
  }
  globalStatus.textContent = results.length === 0 ?
    "Nenhum indicador disponível para este perfil." :
    failed === 0 ? "Indicadores consultados nesta unidade." :
    failed === results.length ? "Os indicadores estão indisponíveis." :
    "Consulta parcial. Alguns módulos estão indisponíveis.";
  refresh.disabled = false;
  loading = false;
}
refresh.addEventListener("click", load);
load();
})();
""".replace("__SOURCES__", source_json)
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = (
        "default-src 'none'; script-src 'sha256-" + digest + "'; "
        "style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    )
    links = "".join(
        '<a class="fm-action" href="' + escape(href, quote=True) + '">'
        + escape(label) + "</a>"
        for label, href in allowed_navigation(principal)
        if href != "/app"
    )
    body = (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        '<title>Visão geral | VendeAtendeIA</title>'
        '<style>'
        ':root{font:15px/1.55 system-ui,Arial,sans-serif;'
        'background:#f2f5fa;color:#172c43}'
        '*{box-sizing:border-box}body{margin:0}'
        'main{max-width:1220px;margin:0 auto;padding:32px 22px 58px}'
        'h1{font-size:clamp(25px,4vw,36px);margin:0 0 8px}'
        'h2{font-size:16px;margin:0;color:#223b56}'
        '.fm-lede{color:#52667b;max-width:720px}'
        '.fm-grid{display:grid;grid-template-columns:'
        'repeat(auto-fit,minmax(230px,1fr));gap:16px;margin:24px 0}'
        '.fm-tile{background:white;border:1px solid #dce4ef;'
        'border-radius:14px;padding:22px;min-height:160px;'
        'box-shadow:0 8px 24px #1429420a}'
        '.fm-value{font-size:32px;font-weight:800;margin:15px 0}'
        '.fm-unavailable{font-size:14px;color:#805233;min-height:40px}'
        '.fm-action{display:inline-block;padding:12px 15px;'
        'background:#fff;border-radius:9px;border:1px solid #bacada;'
        'margin:6px;text-decoration:none;color:#184b65;font-weight:600}'
        'a{color:#155d7c}a:focus-visible,button:focus-visible{outline:3px solid #077ca2;outline-offset:3px}'
        'button{background:#185b76;color:#fff;border:0;border-radius:9px;'
        'padding:10px 16px;font:inherit;cursor:pointer}'
        'button:disabled{opacity:.6}'
        '#fm-status{color:#51687c}'
        '</style></head><body><main>'
        '<h1>Bom trabalho, ' + escape(principal.display_name) + '</h1>'
        '<p class="fm-lede">Área comercial do VendeAtendeIA. '
        'Informações consultadas apenas para sua unidade ativa, '
        'sem presumir resultados ausentes.</p>'
        '<div><button type="button" id="fm-reload">Atualizar indicadores</button></div>'
        '<p id="fm-status" role="status" aria-live="polite">Carregando...</p>'
        '<section aria-label="Indicadores comerciais">'
        '<div id="fm-overview" class="fm-grid" aria-live="polite"></div></section>'
        '<section aria-labelledby="fm-shortcuts"><h2 id="fm-shortcuts">'
        'Acessar módulos</h2><div>' + links + '</div></section>'
        '</main><script>' + script + '</script></body></html>'
    )
    return attach_navigation(body, principal, "/app"), csp
