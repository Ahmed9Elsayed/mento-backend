"""
tests/test_endpoints.py
-----------------------
Unit tests for all Flask API endpoints.
Covers happy paths and error cases for every rubric-required route.
The pipeline and feedback logger are always mocked — no real models or
API keys needed to run these tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app import app as flask_app
from app import public_error


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


@pytest.fixture()
def pipeline():
    """A fully mocked MentoPipeline."""
    mock = MagicMock()
    mock.rag.metadata.return_value = {
        "collection": "Mental-Health",
        "vectors": 500,
        "status": "ready",
    }
    mock.rag.rebuild_index.return_value = {"vectors": 500}
    mock.last_mental_health_topic = {}
    return mock


@pytest.fixture()
def feedback_logger():
    """A fully mocked FeedbackLogger."""
    return MagicMock()


def make_stream(*tokens: str, route: str = "rag_pipeline", emotion: str = "sadness"):
    """Helper: build the real pipeline stream event sequence."""
    from dataclasses import asdict
    events = [
        # metadata event — wraps a RouteResult-like dict under "data"
        {
            "type": "metadata",
            "data": {
                "route": route,
                "intent": "asking_mental_health_question",
                "translated": "I feel anxious",
                "language": "en",
                "confidence": 0.9,
                "layer_used": "Layer 2",
                "language_hint": "en",
                "language_hint_confidence": 0.85,
                "emotion": {
                    "emotion": emotion,
                    "confidence": 0.82,
                    "scores": {},
                    "high_distress": emotion in {"sadness", "anger", "fear"},
                },
                "chunks": [],
                "guardrails": None,
                "mental_health_topic": None,
                "crisis": None,
                "response": None,
            },
        },
        # token events — each word as a separate dict with key "text"
        *[{"type": "token", "text": t} for t in tokens],
        # done event
        {"type": "done", "data": {}},
    ]
    return iter(events)


# ---------------------------------------------------------------------------
# GET /health  (rubric: GET /health)
# ---------------------------------------------------------------------------

class TestHealth:
    def test_returns_200(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.get("/health")
        assert response.status_code == 200

    def test_api_prefix_alias_also_works(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.get("/api/health")
        assert response.status_code == 200

    def test_contains_status_ok(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            data = client.get("/health").get_json()
        assert data["status"] == "ok"

    def test_contains_system_name(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            data = client.get("/health").get_json()
        assert data["system"] == "Mento"

    def test_contains_required_top_level_keys(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            data = client.get("/health").get_json()
        for key in ("rag", "groq", "feedback", "local_models"):
            assert key in data, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# POST /chat  (rubric: POST /chat)
# ---------------------------------------------------------------------------

class TestChat:
    def test_happy_path_returns_200(self, client, pipeline):
        pipeline.stream.return_value = make_stream("Hello, ", "I'm here.")
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.post("/chat", json={"message": "I feel anxious"})
        assert response.status_code == 200

    def test_response_contains_assembled_text(self, client, pipeline):
        pipeline.stream.return_value = make_stream("Hello, ", "I'm here.")
        with patch("app.get_pipeline", return_value=pipeline):
            data = client.post("/chat", json={"message": "I feel anxious"}).get_json()
        # tokens are joined from "text" field
        assert "Hello, " in data["response"]
        assert "I'm here." in data["response"]

    def test_response_contains_session_id(self, client, pipeline):
        pipeline.stream.return_value = make_stream("Hi")
        with patch("app.get_pipeline", return_value=pipeline):
            data = client.post(
                "/chat", json={"message": "Hello", "session_id": "sess-abc"}
            ).get_json()
        assert data["session_id"] == "sess-abc"

    def test_auto_generates_session_id_when_missing(self, client, pipeline):
        pipeline.stream.return_value = make_stream("Hi")
        with patch("app.get_pipeline", return_value=pipeline):
            data = client.post("/chat", json={"message": "Hello"}).get_json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    def test_empty_message_returns_400(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.post("/chat", json={"message": ""})
        assert response.status_code == 400

    def test_missing_message_field_returns_400(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.post("/chat", json={})
        assert response.status_code == 400

    def test_whitespace_only_message_returns_400(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.post("/chat", json={"message": "   "})
        assert response.status_code == 400

    def test_pipeline_error_event_returns_500(self, client, pipeline):
        pipeline.stream.return_value = iter([
            {"type": "error", "message": "Groq API unavailable"},
        ])
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.post("/chat", json={"message": "help me"})
        assert response.status_code == 500
        assert response.get_json()["status"] == "error"

    def test_unhandled_exception_returns_500(self, client, pipeline):
        pipeline.stream.side_effect = RuntimeError("unexpected crash")
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.post("/chat", json={"message": "help me"})
        assert response.status_code == 500

    def test_direct_route_reflected_in_response(self, client, pipeline):
        pipeline.stream.return_value = make_stream("Hello!", route="direct")
        with patch("app.get_pipeline", return_value=pipeline):
            data = client.post("/chat", json={"message": "Hi"}).get_json()
        assert data["route"] == "direct"

    def test_pipeline_called_with_correct_message(self, client, pipeline):
        pipeline.stream.return_value = make_stream("Hi")
        with patch("app.get_pipeline", return_value=pipeline):
            client.post("/chat", json={"message": "I need help", "session_id": "s1"})
        pipeline.stream.assert_called_once_with("I need help", "s1")


# ---------------------------------------------------------------------------
# POST /api/chat/stream
# ---------------------------------------------------------------------------

class TestChatStream:
    def test_returns_200(self, client, pipeline):
        pipeline.stream.return_value = iter([{"type": "done", "data": {}}])
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.post("/api/chat/stream", json={"message": "hello"})
        assert response.status_code == 200

    def test_content_type_is_event_stream(self, client, pipeline):
        pipeline.stream.return_value = iter([{"type": "done", "data": {}}])
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.post("/api/chat/stream", json={"message": "hello"})
        assert "text/event-stream" in response.content_type

    def test_response_contains_session_event(self, client, pipeline):
        pipeline.stream.return_value = iter([{"type": "done", "data": {}}])
        with patch("app.get_pipeline", return_value=pipeline):
            raw = client.post(
                "/api/chat/stream",
                json={"message": "hello", "session_id": "my-session"},
            ).data.decode()
        assert '"type": "session"' in raw
        assert "my-session" in raw

    def test_token_events_are_included(self, client, pipeline):
        pipeline.stream.return_value = iter([
            {"type": "token", "text": "hello"},
            {"type": "done", "data": {}},
        ])
        with patch("app.get_pipeline", return_value=pipeline):
            raw = client.post("/api/chat/stream", json={"message": "hi"}).data.decode()
        assert "hello" in raw


# ---------------------------------------------------------------------------
# POST /api/chat/clear
# ---------------------------------------------------------------------------

class TestChatClear:
    def test_returns_200_with_cleared_status(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.post("/api/chat/clear", json={"session_id": "abc"})
        assert response.status_code == 200
        assert response.get_json()["status"] == "cleared"

    def test_calls_pipeline_clear_history(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            client.post("/api/chat/clear", json={"session_id": "abc"})
        pipeline.clear_history.assert_called_once_with("abc")

    def test_no_session_id_still_returns_200(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            response = client.post("/api/chat/clear", json={})
        assert response.status_code == 200

    def test_no_session_id_does_not_call_clear_history(self, client, pipeline):
        with patch("app.get_pipeline", return_value=pipeline):
            client.post("/api/chat/clear", json={})
        pipeline.clear_history.assert_not_called()


# ---------------------------------------------------------------------------
# POST /feedback  (rubric: POST /feedback)
# ---------------------------------------------------------------------------

class TestFeedback:
    VALID_PAYLOAD = {
        "query": "I feel sad",
        "response": "I hear you.",
        "feedback": "like",
    }

    def test_like_returns_logged(self, client, feedback_logger):
        with patch("app.get_feedback_logger", return_value=feedback_logger):
            response = client.post("/feedback", json=self.VALID_PAYLOAD)
        assert response.status_code == 200
        assert response.get_json()["status"] == "logged"

    def test_dislike_returns_logged(self, client, feedback_logger):
        payload = {**self.VALID_PAYLOAD, "feedback": "dislike"}
        with patch("app.get_feedback_logger", return_value=feedback_logger):
            response = client.post("/feedback", json=payload)
        assert response.status_code == 200

    def test_api_prefix_alias_works(self, client, feedback_logger):
        with patch("app.get_feedback_logger", return_value=feedback_logger):
            response = client.post("/api/feedback", json=self.VALID_PAYLOAD)
        assert response.status_code == 200

    def test_thumbs_up_alias_works(self, client, feedback_logger):
        payload = {**self.VALID_PAYLOAD, "feedback": "thumbs_up"}
        with patch("app.get_feedback_logger", return_value=feedback_logger):
            response = client.post("/feedback", json=payload)
        assert response.status_code == 200

    def test_invalid_feedback_value_returns_400(self, client, feedback_logger):
        payload = {**self.VALID_PAYLOAD, "feedback": "not_valid"}
        with patch("app.get_feedback_logger", return_value=feedback_logger):
            response = client.post("/feedback", json=payload)
        assert response.status_code == 400

    def test_missing_query_returns_400(self, client, feedback_logger):
        payload = {"response": "r", "feedback": "like"}
        with patch("app.get_feedback_logger", return_value=feedback_logger):
            response = client.post("/feedback", json=payload)
        assert response.status_code == 400

    def test_missing_response_returns_400(self, client, feedback_logger):
        payload = {"query": "q", "feedback": "like"}
        with patch("app.get_feedback_logger", return_value=feedback_logger):
            response = client.post("/feedback", json=payload)
        assert response.status_code == 400

    def test_empty_query_returns_400(self, client, feedback_logger):
        payload = {**self.VALID_PAYLOAD, "query": ""}
        with patch("app.get_feedback_logger", return_value=feedback_logger):
            response = client.post("/feedback", json=payload)
        assert response.status_code == 400

    def test_runtime_error_returns_503(self, client, feedback_logger):
        feedback_logger.append.side_effect = RuntimeError("Sheet unavailable")
        with patch("app.get_feedback_logger", return_value=feedback_logger):
            response = client.post("/feedback", json=self.VALID_PAYLOAD)
        assert response.status_code == 503

    def test_unexpected_exception_returns_502(self, client, feedback_logger):
        feedback_logger.append.side_effect = Exception("network timeout")
        with patch("app.get_feedback_logger", return_value=feedback_logger):
            response = client.post("/feedback", json=self.VALID_PAYLOAD)
        assert response.status_code == 502

    def test_logger_called_with_normalized_feedback(self, client, feedback_logger):
        payload = {**self.VALID_PAYLOAD, "feedback": "thumbs_up"}
        with patch("app.get_feedback_logger", return_value=feedback_logger):
            client.post("/feedback", json=payload)
        feedback_logger.append.assert_called_once_with(
            "I feel sad", "I hear you.", "Like"
        )


# ---------------------------------------------------------------------------
# public_error helper (tested directly — no HTTP)
# ---------------------------------------------------------------------------

class TestPublicError:
    def test_memory_error_returns_friendly_message(self):
        result = public_error(MemoryError("out of memory"))
        assert "memory" in result.lower()

    def test_paging_file_error_returns_friendly_message(self):
        result = public_error(RuntimeError("paging file is too small"))
        assert "memory" in result.lower()

    def test_network_error_returns_friendly_message(self):
        result = public_error(ConnectionError("network error occurred"))
        assert "network" in result.lower()

    def test_connection_error_returns_friendly_message(self):
        result = public_error(RuntimeError("connection refused"))
        assert "network" in result.lower()

    def test_generic_error_returns_original_message(self):
        result = public_error(ValueError("something went wrong"))
        assert result == "something went wrong"
