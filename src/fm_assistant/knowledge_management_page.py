"""Customer knowledge workspace. Same-origin, session-bound and no HTML injection."""
from __future__ import annotations

import base64
import hashlib


def render_knowledge_management_page() -> tuple[str, str]:
    script = r"""
(() => {
"use strict";
const $ = id => document.getElementById(id);
const notice = message => { $("notice").textContent=message; };
const element = (tag,text,cls="") => {
  const node=document.createElement(tag);node.textContent=text;
  if(cls)node.className=cls;
  return node;
};
async function api(path,method="GET",body=null) {
  const headers={"Accept":"application/json"};
  const config={method,headers,credentials:"same-origin",cache:"no-store"};
  if(body instanceof FormData){config.body=body;}
  else if(body!==null){headers["Content-Type"]="application/json";
    config.body=JSON.stringify(body);}
  const res=await fetch(path,config);
  let data={};
  try{data=await res.json();}catch{}
  if(!res.ok)throw Error(data.detail||"Operação não disponível.");
  return data;
}
let busy=false;
async function withBusy(work){
  if(busy)return;busy=true;for(const btn of document.querySelectorAll("button"))
    btn.disabled=true;
  try{await work();}catch(e){notice("Operação não concluída: "+e.message);}
  finally{busy=false;for(const btn of document.querySelectorAll("button"))
    btn.disabled=false;}
}
async function sources(page=0){
  const res=await api("/v1/knowledge/sources?page="+page);
  $("sources").replaceChildren();
  if(!res.items.length)$("sources").append(element("p","Nenhuma fonte nesta página.","muted"));
  for(const item of res.items){
    const card=element("article","","item");
    card.append(element("strong",item.title));
    card.append(element("small",item.source_kind+" · "+
      (item.active?"Ativa":"Revogada")+" · revisão "+(item.revision??"legado"),"muted"));
    if(item.source_ref)card.append(element("small","Origem: "+item.source_ref,"muted"));
    if(item.content_sha256)card.append(element("small",
      "SHA-256: "+item.content_sha256,"hash"));
    if(item.active){
      const btn=element("button","Revogar fonte","danger");
      btn.addEventListener("click",()=>withBusy(async()=>{
        if(!window.confirm("Revogar esta fonte da IA e das consultas?"))return;
        await api("/v1/knowledge/"+encodeURIComponent(item.document_id),"DELETE");
        notice("Fonte revogada e retirada do contexto.");
        await sources(page);
      }));
      card.append(btn);
    }
    $("sources").append(card);
  }
  $("previous").disabled=page===0;
  $("next").disabled=res.next_page===null;
  $("previous").onclick=()=>withBusy(()=>sources(page-1));
  $("next").onclick=()=>withBusy(()=>sources(res.next_page));
}
$("refresh").onclick=()=>withBusy(()=>sources());
$("file-form").addEventListener("submit",event=>{
  event.preventDefault();withBusy(async()=>{
    const form=new FormData($("file-form"));
    const selected=form.get("file");
    if(!(selected instanceof File)||!selected.size||selected.size>1500000)
      throw Error("Escolha um arquivo válido de até 1,5 MB.");
    const imported=await api("/v1/knowledge/sources/file","POST",form);
    notice("Arquivo indexado: revisão "+imported.revision+"; "+
      imported.chunks+" trecho(s). Fonte externa não verificada.");
    $("file-form").reset();await sources();
  });
});
$("url-form").addEventListener("submit",event=>{
  event.preventDefault();withBusy(async()=>{
    const imported=await api("/v1/knowledge/sources/url","POST",{
      title:$("url-title").value,url:$("url-address").value
    });
    notice("URL indexada: revisão "+imported.revision+"; "+
      imported.chunks+" trecho(s). Fonte externa não verificada.");
    $("url-form").reset();await sources();
  });
});
$("preview-form").addEventListener("submit",event=>{
  event.preventDefault();withBusy(async()=>{
    const result=await api("/v1/knowledge/context-preview","POST",{
      question:$("question").value
    });
    $("evidence").replaceChildren();
    if(!result.grounded){
      $("evidence").append(element("p","Nenhuma evidência relevante ou recuperação desativada."));
    }else{
      if(result.corpus_truncated)$("evidence").append(
        element("p","Consulta limitada ao corpus de segurança.","muted"));
      for(const proof of result.evidence){
        const article=element("article","","item");
        article.append(element("small","Documento: "+proof.document_id+
          " · versão: "+(proof.source_revision??"legado")+
          " · trecho: "+(proof.chunk_ordinal??"não indexado"),"muted"));
        if(proof.chunk_sha256)article.append(
          element("small","SHA-256: "+proof.chunk_sha256,"hash"));
        article.append(element("p",proof.snippet));
        $("evidence").append(article);
      }
    }
    notice(result.evidence.length+" fonte(s) pertinentes na prévia.");
  });
});
withBusy(()=>sources());
})();
"""
    script_hash = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    csp = (
        "default-src 'none'; script-src 'sha256-" + script_hash +
        "'; style-src 'unsafe-inline'; connect-src 'self'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )
    page = """<!doctype html><html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Conhecimento | VendeAtendeIA</title>
<style>
:root{font:15px/1.5 system-ui,Arial;background:#f3f6fa;color:#193248}
*{box-sizing:border-box}body{margin:0}header{background:#142d42;color:white;padding:23px 5%}
h1{margin:0;font-size:24px}h2{margin:0 0 14px;font-size:18px}
header p{margin:5px 0 8px;color:#cee1f2}nav a{color:#dbf5ff;margin-right:15px}
main{max-width:1220px;margin:24px auto;padding:0 20px;display:grid;gap:18px;
 grid-template-columns:1fr 1fr}
section{min-width:0;background:white;border:1px solid #d9e2e9;border-radius:14px;
 padding:22px;box-shadow:0 3px 16px #142d420b}
section.wide{grid-column:1/-1}
label{display:block;font-size:13px;font-weight:650;margin:10px 0 4px}
input,textarea{display:block;width:100%;padding:11px;font:inherit;border-radius:8px;
 border:1px solid #aabfcc;min-width:0}
textarea{min-height:76px;resize:vertical}
button{margin-top:12px;border:1px solid #286681;color:#16516c;background:white;
 padding:9px 15px;border-radius:8px;font:inherit;cursor:pointer}
button.primary{background:#155c7c;color:white}button.danger{border-color:#ab5b50;color:#873628}
button:disabled{opacity:.55;cursor:not-allowed}
.item{padding:14px;border:1px solid #e1e7ed;border-radius:10px;margin:10px 0;
 display:grid;gap:5px;overflow-wrap:anywhere}
small{font-size:12px}.muted{color:#556d7c}.hash{font:11px/1.4 monospace;color:#61727b}
#notice{min-height:22px;color:#195b72;font-weight:600}
.actions{display:flex;gap:10px;flex-wrap:wrap}
footer{padding:16px;text-align:center;color:#5d7080}
@media(max-width:740px){main{grid-template-columns:1fr}section.wide{grid-column:auto}}
</style></head>
<body>
<header><h1>VendeAtendeIA · Base de conhecimento</h1>
<p>Fontes isoladas por empresa e unidade · controle de versões e evidências</p>
<nav><a href="/app/inbox">Atendimento humano</a>
<a href="/v1/plan/consumption/dashboard">Consumo do plano</a></nav></header>
<main>
<section><h2>Importar arquivo</h2>
<p class="muted">TXT, Markdown, CSV, HTML e PDF. Até 1,5 MB por arquivo;
 texto extraído até 24 mil caracteres. Sem executar conteúdo enviado.</p>
<form id="file-form"><label for="file-title">Título da fonte</label>
<input id="file-title" name="title" maxlength="255" required>
<label for="file">Documento</label>
<input id="file" name="file" type="file" accept=".txt,.md,.csv,.html,.htm,.pdf" required>
<button class="primary" type="submit">Importar e versionar</button></form>
</section>
<section><h2>Importar URL autorizada</h2>
<p class="muted">Somente HTTPS e domínios previamente liberados pela FM.
 A busca de URLs permanece desabilitada até configuração do ambiente.</p>
<form id="url-form"><label for="url-title">Título da página</label>
<input id="url-title" maxlength="255" required>
<label for="url-address">Endereço HTTPS</label>
<input id="url-address" type="url" maxlength="512" required>
<button class="primary" type="submit">Importar conteúdo e versionar</button></form>
</section>
<section class="wide"><h2>Verificar evidências antes do uso pela IA</h2>
<form id="preview-form"><label for="question">Pergunta de teste</label>
<textarea id="question" minlength="2" maxlength="500" required
 placeholder="Quais são as condições do plano?"></textarea>
<button class="primary" type="submit">Consultar Context Pack</button></form>
<div id="evidence" aria-live="polite"></div></section>
<section class="wide"><h2>Fontes cadastradas</h2>
<div class="actions"><button id="refresh">Atualizar</button>
<button id="previous" disabled>Anterior</button><button id="next" disabled>Próxima</button></div>
<p id="notice" role="status" aria-live="polite"></p>
<div id="sources" aria-live="polite"></div></section>
</main>
<footer>Fontes externas não são certificados de veracidade. Revogação impede novo contexto.</footer>
<script>""" + script + """</script></body></html>"""
    return page, csp
