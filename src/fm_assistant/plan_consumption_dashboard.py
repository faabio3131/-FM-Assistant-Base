"""Server-rendered customer consumption dashboard with conservative unknowns."""
from __future__ import annotations

from html import escape


def render_consumption_dashboard(data: dict) -> str:
    def safely(value: object) -> str:
        return escape(str(value), quote=True)

    cards = []
    for row in data["consumption"]:
        verified = row["status"] == "observed"
        remaining = row["remaining_units"]
        used = row["consumed_units"]
        limit = row["limit_units"]
        if verified and limit > 0:
            percent = min(100, round(100 * (limit - remaining) / limit))
            state = f"{safely(percent)}% da franquia comprometida"
            value = f"{safely(used)} utilizados · {safely(remaining)} disponíveis"
            label = "Consumo confirmado pelo Core"
        else:
            percent = 0
            state = "Aguardando telemetria autenticada"
            value = "Saldo não verificado"
            label = "O saldo não pode ser presumido como zero"
        cards.append(
            '<section class="metric" aria-label="' + safely(row["resource"]) + '">'
            '<div class="metric-name">' + safely(row["resource"]) + '</div>'
            '<div class="metric-count">Franquia: ' + safely(limit) + '</div>'
            '<div class="metric-count">' + value + '</div>'
            '<div class="metric-info">' + state + '</div>'
            '<progress max="100" value="' + str(percent) + '"></progress>'
            '<p class="quiet">' + label + '</p>'
            '</section>'
        )
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Meu consumo · VendeAtendeIA</title>'
        '<style>'
        ':root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;background:#090f1b;color:#f1f6ff}'
        '*{box-sizing:border-box}main{max-width:1050px;margin:auto;padding:clamp(24px,5vw,60px)}'
        '.eyebrow{letter-spacing:.2em;text-transform:uppercase;color:#83d4c6;font-size:.75rem}'
        'h1{font-size:clamp(2rem,4vw,3.3rem);margin:.6rem 0}.quiet{color:#9badc8}'
        '.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:18px}'
        '.metric{border:1px solid #293b56;background:#121e31;border-radius:18px;padding:22px}'
        '.metric-name{font-weight:700;font-size:1.1rem}.metric-count{margin-top:12px}'
        '.metric-info{margin-top:14px;color:#8ddbcc}progress{width:100%;height:9px;margin:16px 0}'
        '.subtitle{line-height:1.6;max-width:700px;margin-bottom:30px}'
        '</style></head><body><main>'
        '<div class="eyebrow">VendeAtendeIA · Consumo e franquias</div>'
        '<h1>' + safely(data["plan_name"]) + '</h1>'
        '<p class="subtitle">Todas as funcionalidades estão disponíveis em todos os planos.'
        ' O que varia é a franquia de consumo. Vigência até '
        + safely(data["licensed_until"]) + '.</p>'
        '<div class="grid">' + ''.join(cards) + '</div>'
        '<p class="quiet">Preços e limites são definidos exclusivamente pela FM Tecnologia.'
        ' Os custos de provedores de IA não são expostos neste painel.</p>'
        '</main></body></html>'
    )
