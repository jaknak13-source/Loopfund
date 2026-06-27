"""Phase 7: dashboard API endpoints against an offline orchestrator."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dashboard.api.server import create_app
from tests.helpers import build_offline_orchestrator


@pytest.fixture
def client(tmp_path) -> TestClient:
    orch = build_offline_orchestrator(tmp_path)
    return TestClient(create_app(orch))


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == "dry"
    assert body["loop"]["running"] is False


def test_portfolio_empty(client: TestClient) -> None:
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    assert r.json()["snapshot"]["cash_eur"] == 1000.0


def test_post_instruction_parses_intent(client: TestClient) -> None:
    r = client.post("/api/instructions", json={"text": "Don't trade this week."})
    assert r.status_code == 200
    assert r.json()["parsed_intent"] == "no_trade"
    assert any(i["parsed_intent"] == "no_trade" for i in client.get("/api/instructions").json())


def test_run_cycle_then_reads(client: TestClient) -> None:
    r = client.post("/api/cycle/run")
    assert r.status_code == 200
    assert r.json()["decision"]["action"] == "buy"
    # decisions, trades, reports, agents now populated
    assert client.get("/api/decisions").json()
    assert client.get("/api/trades").json()
    assert client.get("/api/reports").json()
    agents = client.get("/api/agents").json()
    assert any(a["agent"] == "QuantAgent" and a["at"] for a in agents)
    # memory search works
    mem = client.get("/api/memory", params={"q": "markets"}).json()
    assert mem["size"] > 0


def test_activity_feed_populated_after_cycle(client: TestClient) -> None:
    client.post("/api/cycle/run")
    acts = client.get("/api/activity").json()
    assert acts, "activity feed should have events after a cycle"
    kinds = {a["kind"] for a in acts}
    assert "thinking" in kinds and "decision" in kinds
    # filter by kind
    decs = client.get("/api/activity", params={"kind": "decision"}).json()
    assert all(a["kind"] == "decision" for a in decs) and decs
    # filter by agent
    qa = client.get("/api/activity", params={"agent": "QuantAgent"}).json()
    assert qa and all(a["agent"] == "QuantAgent" for a in qa)


def test_cycle_progress_endpoint(client: TestClient) -> None:
    client.post("/api/cycle/run")
    prog = client.get("/api/cycle/progress").json()
    assert prog["cycle_id"]
    assert isinstance(prog["agents"], list) and prog["agents"]
    assert any(a["state"] == "done" for a in prog["agents"])


def test_decision_blockers_endpoint(client: TestClient) -> None:
    client.post("/api/cycle/run")
    body = client.get("/api/decisions/blockers").json()
    assert body["n"] >= 1
    assert sum(body["blockers"].values()) == body["n"]


def test_settings_read(client: TestClient) -> None:
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert "settings" in r.json() and "risk_limits" in r.json()


def test_loop_status(client: TestClient) -> None:
    assert client.get("/api/loop/status").json()["running"] is False


def test_calibration_endpoint(client: TestClient) -> None:
    r = client.get("/api/calibration")
    assert r.status_code == 200
    body = r.json()
    assert "benchmark" in body and "agents" in body and "learned_priors" in body


def test_briefings_endpoint_lists_seed(client: TestClient) -> None:
    r = client.get("/api/briefings")
    assert r.status_code == 200
    assert any(b["name"] == "SupplyChainAgent" for b in r.json())


def test_briefings_reject_reserved_name(client: TestClient) -> None:
    r = client.post("/api/briefings", json={"name": "QuantAgent", "body": "x"})
    assert r.status_code == 400  # reserved core name


def test_backups_list_endpoint(client: TestClient) -> None:
    r = client.get("/api/backups")
    assert r.status_code == 200 and "backups" in r.json()


def test_errors_endpoint(client: TestClient) -> None:
    r = client.get("/api/errors")
    assert r.status_code == 200 and "errors" in r.json()


def test_market_endpoint(client: TestClient) -> None:
    r = client.get("/api/market")
    assert r.status_code == 200
    body = r.json()
    assert "quotes" in body and body["quotes"]  # fake-priced in offline orchestrator


def test_agents_have_descriptions(client: TestClient) -> None:
    agents = client.get("/api/agents").json()
    quant = next(a for a in agents if a["agent"] == "QuantAgent")
    assert quant["description"] and quant["role"]
    assert any(a["agent"] == "SupplyChainAgent" and a["dynamic"] for a in agents)
