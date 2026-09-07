"""HTTP-level chatbot tests.

Exercise the four routes wired in ``app.api.chat``:

    POST   /api/v1/chat/query
    GET    /api/v1/chat/sessions/{id}
    DELETE /api/v1/chat/sessions/{id}
    POST   /api/v1/chat/suggestions

We build a fresh TestClient per test so the FastAPI app is exercised
end-to-end, including exception handlers.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import _build_app

    app = _build_app()
    with TestClient(app) as c:
        yield c


class TestChatQueryEndpoint:
    def test_metric_query(self, client, corporate_dataset_id: str) -> None:
        r = client.post(
            "/api/v1/chat/query",
            json={
                "message": "What is our revenue?",
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "self_analysis",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["classification"] == "reported"
        assert body["intent"] == "metric_lookup"
        assert body["session_id"]
        # 460 must appear in the answer or the evidence.
        assert "460" in body["answer"] or any(
            e.get("value") == 460.0 for e in body["evidence"]
        )

    def test_out_of_scope_returns_refused(self, client, corporate_dataset_id: str) -> None:
        r = client.post(
            "/api/v1/chat/query",
            json={
                "message": "What is the capital of France?",
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "self_analysis",
            },
        )
        assert r.status_code == 200
        assert r.json()["classification"] == "refused"

    def test_investment_advice_returns_refused(
        self, client, corporate_dataset_id: str
    ) -> None:
        r = client.post(
            "/api/v1/chat/query",
            json={
                "message": "Should I buy this stock?",
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "self_analysis",
            },
        )
        assert r.status_code == 200
        assert r.json()["classification"] == "refused"

    def test_missing_dataset_graceful(self, client) -> None:
        r = client.post(
            "/api/v1/chat/query",
            json={
                "message": "What is our revenue?",
                "dataset_id": "does-not-exist",
                "analysis_mode": "self_analysis",
            },
        )
        # Not-found is folded into a graceful UNAVAILABLE response instead of a 500.
        assert r.status_code == 200
        assert r.json()["classification"] == "unavailable"

    def test_empty_message_returns_422(self, client) -> None:
        r = client.post("/api/v1/chat/query", json={"message": ""})
        assert r.status_code == 422

    def test_evidence_and_calculations_serialised(
        self, client, corporate_dataset_id: str
    ) -> None:
        r = client.post(
            "/api/v1/chat/query",
            json={
                "message": "What is our net profit margin?",
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "self_analysis",
            },
        )
        body = r.json()
        assert body["classification"] == "calculated"
        assert body["evidence"], "Expected at least one evidence item"
        assert body["calculations"], "Expected at least one calculation trace"
        # Evidence items include their metric attribution.
        assert any(e.get("metric_id") == "net_margin" for e in body["evidence"])


class TestChatSessionEndpoints:
    def test_history_matches_conversation(self, client, corporate_dataset_id: str) -> None:
        r1 = client.post(
            "/api/v1/chat/query",
            json={
                "message": "Overview",
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "self_analysis",
            },
        )
        session_id = r1.json()["session_id"]

        r2 = client.get(f"/api/v1/chat/sessions/{session_id}")
        assert r2.status_code == 200
        body = r2.json()
        assert body["session_id"] == session_id
        assert body["dataset_id"] == corporate_dataset_id
        assert body["analysis_mode"] == "self_analysis"
        # user + assistant
        assert len(body["messages"]) == 2
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][1]["role"] == "assistant"

    def test_history_after_multi_turn(
        self, client, corporate_dataset_id: str
    ) -> None:
        first = client.post(
            "/api/v1/chat/query",
            json={
                "message": "What is our revenue in 2024?",
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "self_analysis",
            },
        ).json()
        sid = first["session_id"]
        client.post(
            "/api/v1/chat/query",
            json={
                "message": "what about profit?",
                "session_id": sid,
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "self_analysis",
            },
        )
        body = client.get(f"/api/v1/chat/sessions/{sid}").json()
        assert len(body["messages"]) == 4

    def test_delete_session(self, client, corporate_dataset_id: str) -> None:
        r1 = client.post(
            "/api/v1/chat/query",
            json={
                "message": "Overview",
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "self_analysis",
            },
        )
        session_id = r1.json()["session_id"]
        r2 = client.delete(f"/api/v1/chat/sessions/{session_id}")
        assert r2.status_code == 204
        r3 = client.get(f"/api/v1/chat/sessions/{session_id}")
        assert r3.status_code == 404

    def test_unknown_session_returns_404(self, client) -> None:
        r = client.get("/api/v1/chat/sessions/does-not-exist")
        assert r.status_code == 404


class TestChatSuggestionsEndpoint:
    def test_self_mode_starters(self, client, corporate_dataset_id: str) -> None:
        r = client.post(
            "/api/v1/chat/suggestions",
            json={
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "self_analysis",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["suggestions"], list)
        assert body["suggestions"], "Expected at least one suggestion"

    def test_followups_after_intent(self, client, corporate_dataset_id: str) -> None:
        r = client.post(
            "/api/v1/chat/suggestions",
            json={
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "self_analysis",
                "last_intent": "financial_health",
                "limit": 4,
            },
        )
        assert r.status_code == 200
        assert r.json()["suggestions"]

    def test_missing_dataset_id_returns_422(self, client) -> None:
        r = client.post("/api/v1/chat/suggestions", json={"analysis_mode": "self_analysis"})
        assert r.status_code == 422


class TestMultiDatasetHttp:
    def test_competitor_endpoint_flow(
        self, client, corporate_dataset_id: str, competitor_dataset_id: str
    ) -> None:
        r = client.post(
            "/api/v1/chat/query",
            json={
                "message": "How does our revenue compare to the competitor?",
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "competitor_market_benchmark",
                "secondary_dataset_id": competitor_dataset_id,
            },
        )
        body = r.json()
        assert body["intent"] == "competitor_comparison"
        entities = {e.get("entity") for e in body["evidence"]}
        assert "primary" in entities
        assert "secondary" in entities

    def test_merger_endpoint_flow(
        self, client, corporate_dataset_id: str, competitor_dataset_id: str
    ) -> None:
        r = client.post(
            "/api/v1/chat/query",
            json={
                "message": "What would combined revenue look like?",
                "dataset_id": corporate_dataset_id,
                "analysis_mode": "merger_partnership_analysis",
                "secondary_dataset_id": competitor_dataset_id,
            },
        )
        body = r.json()
        assert body["classification"] == "scenario"
        combined_rev = [
            e for e in body["evidence"]
            if e.get("entity") == "combined" and e.get("metric_id") == "revenue"
        ]
        assert combined_rev
        assert abs(combined_rev[0]["value"] - 1087.0) < 1.0
