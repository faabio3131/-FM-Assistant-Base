"""F7 CRM operational cadence listing and same-origin UI regression."""
from __future__ import annotations

import base64
import hashlib
import re
from test_f7_cadence_engine import _plan, _setup


def test_runs_list_is_scoped_and_bounded(client):
    cid, oid, cadence = _setup(client)
    one = _plan(client, cid, oid, cadence)
    assert one.status_code == 201, one.text
    two = _plan(client, cid, oid, cadence, key="f7-operations-0002")
    assert two.status_code == 201, two.text

    listed = client.get("/v1/followups/runs")
    assert listed.status_code == 200, listed.text
    ids = {r["run_id"] for r in listed.json()["items"]}
    assert {one.json()["run_id"], two.json()["run_id"]} <= ids
    assert listed.json()["has_more"] is False
    assert all(len(r["jobs"]) == 2 for r in listed.json()["items"])
    assert "orçamento sigiloso" not in listed.text
    assert client.get("/v1/followups/runs?status=active").status_code == 200
    assert client.get("/v1/followups/runs?status=unknown").status_code == 422

    cancelled = client.post(
        f"/v1/followups/runs/{one.json()['run_id']}/cancel",
    )
    assert cancelled.status_code == 200
    active = client.get("/v1/followups/runs?status=active").json()["items"]
    assert one.json()["run_id"] not in {row["run_id"] for row in active}
    closed = client.get("/v1/followups/runs?status=cancelled").json()["items"]
    assert one.json()["run_id"] in {row["run_id"] for row in closed}

    assert client.post("/v1/units", json={
        "unit_id": "other-unit", "display_name": "Outra unidade",
    }).status_code == 200
    assert client.post("/v1/auth/switch-unit", json={
        "unit_id": "other-unit",
    }).status_code == 200
    response = client.get("/v1/followups/runs")
    assert response.status_code == 200
    assert response.json() == {"items": [], "has_more": False}


def test_crm_has_operational_cadence_ui_with_hashed_script_csp(client):
    _setup(client)
    page = client.get("/app/crm")
    assert page.status_code == 200, page.text
    for expected in (
        'id="cadence-definition-form"', 'id="cadence-run-form"',
        'id="cadence-runs"', "Ver auditoria", "Cancelar cadência",
        'api("/v1/followups/runs")',
        'api("/v1/followups/cadences")',
        'id="followup-form"',
    ):
        assert expected in page.text
    assert "innerHTML" not in page.text
    # CSP protects dynamically generated same-origin JS even as forms evolve.
    match = re.search(r"<script>(.*?)</script>", page.text, re.DOTALL)
    assert match
    digest = base64.b64encode(hashlib.sha256(
        match.group(1).encode(),
    ).digest()).decode()
    assert f"script-src 'sha256-{digest}'" in page.headers["content-security-policy"]
