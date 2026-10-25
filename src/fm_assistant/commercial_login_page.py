"""F8 same-origin public sign-in page using the existing signed human session API.

No token in local/session storage, query parameters, JS state or HTML response.
"""
from __future__ import annotations

import base64
import hashlib


def render_login() -> tuple[str, str]:
    script = r"""
(() => {
"use strict";
const form=document.getElementById("fm-login");
const message=document.getElementById("fm-login-status");
const submit=document.getElementById("fm-login-submit");
let pending=false;
form.addEventListener("submit",async event=>{
  event.preventDefault();
  if(pending)return;
  pending=true;
  submit.disabled=true;
  message.textContent="Verificando acesso...";
  const password=document.getElementById("fm-password");
  try{
    const payload={
      tenant_id:document.getElementById("fm-tenant").value.trim(),
      email:document.getElementById("fm-email").value.trim(),
      password:password.value
    };
    const unit=document.getElementById("fm-unit").value.trim();
    if(unit)payload.unit_id=unit;
    const response=await fetch("/v1/auth/login",{
      method:"POST",credentials:"same-origin",cache:"no-store",
      headers:{"Content-Type":"application/json","Accept":"application/json"},
      body:JSON.stringify(payload)
    });
    if(response.status===401){
      message.textContent="Credenciais ou organização inválidas.";
      return;
    }
    if(!response.ok){
      message.textContent="Não foi possível concluir o login.";
      return;
    }
    message.textContent="Acesso confirmado. Abrindo seu painel...";
    window.location.assign("/app");
  }catch{
    message.textContent="Serviço de autenticação indisponível.";
  }finally{
    password.value="";
    pending=false;
    submit.disabled=false;
  }
});
})();
"""
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = (
        "default-src 'none'; script-src 'sha256-" + digest + "'; "
        "style-src 'unsafe-inline'; connect-src 'self'; "
        "form-action 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    html = (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        '<title>Entrar | VendeAtendeIA</title><style>'
        ':root{font:15px/1.6 system-ui,Arial,sans-serif;'
        'color:#172b42;background:#edf2f9}'
        '*{box-sizing:border-box}body{margin:0;min-height:100vh;'
        'display:grid;place-items:center;padding:20px}'
        'main{width:min(100%,470px);background:#fff;border:1px solid #d7e2ef;'
        'border-radius:20px;box-shadow:0 20px 65px #122c4520;'
        'padding:clamp(22px,5vw,42px)}'
        'h1{font-size:28px;margin:7px 0 4px}'
        '.brand{font-weight:800;color:#136078;letter-spacing:.035em}'
        'p{color:#62758a;margin:4px 0 20px}'
        'label{font-weight:650;display:block;margin:16px 0 6px}'
        'input{display:block;width:100%;padding:12px;border:1px solid #9daec0;'
        'border-radius:10px;font:inherit}'
        'input:focus-visible,button:focus-visible{outline:3px solid #31a1b7;outline-offset:2px}'
        'button{margin:22px 0 0;width:100%;padding:13px;border:0;border-radius:10px;'
        'background:#136581;color:#fff;font:inherit;font-weight:750;cursor:pointer}'
        'button:disabled{opacity:.6}'
        '#fm-login-status{min-height:24px;margin-top:18px;color:#315a74}'
        '.note{font-size:13px;color:#67778a;margin-top:12px}'
        '</style></head><body><main id="fm-main-content">'
        '<div class="brand">VendeAtendeIA</div>'
        '<h1>Acesse sua operação</h1>'
        '<p>Entre com sua organização e conta cadastrada.</p>'
        '<form id="fm-login">'
        '<label for="fm-tenant">Identificador da organização</label>'
        '<input id="fm-tenant" name="tenant_id" autocomplete="organization" '
        'maxlength="128" required>'
        '<label for="fm-email">E-mail</label>'
        '<input id="fm-email" name="email" type="email" '
        'autocomplete="username" maxlength="320" required>'
        '<label for="fm-password">Senha</label>'
        '<input id="fm-password" name="password" type="password" '
        'autocomplete="current-password" maxlength="256" required>'
        '<label for="fm-unit">Unidade (opcional)</label>'
        '<input id="fm-unit" name="unit_id" maxlength="128">'
        '<button id="fm-login-submit" type="submit">Entrar no painel</button>'
        '</form><p id="fm-login-status" role="status" aria-live="polite"></p>'
        '<p class="note">Sua sessão é protegida por cookie HttpOnly; '
        'não armazenamos senhas nem tokens no navegador.</p>'
        '</main><script>' + script + '</script></body></html>'
    )
    return html, csp
