from __future__ import annotations

import json
import logging
import uuid
from functools import lru_cache
from typing import Any

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

from feedback_service import FeedbackLogger, normalize_feedback
from mento_pipeline import MentoPipeline
from prompts import BLANK_MESSAGE_RESPONSE
from settings import load_settings

# ---------------------------------------------------------------------------
# Logging — use Python's standard logging module throughout
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("mento")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
settings = load_settings()

# CORS — allow requests from the Serenity frontend (GitHub Pages) and localhost
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False,
)

logger.info("Mento backend starting — host=%s port=%s", settings.flask_host, settings.flask_port)


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_pipeline() -> MentoPipeline:
    logger.info("Initialising MentoPipeline...")
    pipeline = MentoPipeline(settings)
    if settings.build_index_on_startup:
        logger.info("BUILD_INDEX_ON_STARTUP=true — building Qdrant index now")
        pipeline.rag.ensure_index()
    logger.info("MentoPipeline ready")
    return pipeline


@lru_cache(maxsize=1)
def get_feedback_logger() -> FeedbackLogger:
    logger.info("Initialising FeedbackLogger")
    return FeedbackLogger(settings)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def public_error(exc: Exception) -> str:
    """Return a safe, user-facing error message (no stack traces)."""
    message = str(exc).lower()
    if (
        isinstance(exc, MemoryError)
        or "paging file is too small" in message
        or "os error 1455" in message
    ):
        return (
            "Local memory is too low to complete that operation right now. "
            "Please close other apps or increase the Windows paging file, then try again."
        )
    if "network error" in message or "connection" in message:
        return (
            "A local or external network connection failed during this request. "
            "Please try again after confirming Flask, Groq, and Qdrant are reachable."
        )
    return str(exc)


# ---------------------------------------------------------------------------
# Routes — API information
# ---------------------------------------------------------------------------
@app.get("/")
def index() -> Any:
    logger.info("GET / — service information requested")
    return jsonify(
        {
            "system": "Mento",
            "status": "ok",
            "message": "Mento backend API is running.",
            "endpoints": {
                "health": "/health",
                "chat": "/chat",
                "feedback": "/feedback",
            },
        }
    )


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status=204)


# ---------------------------------------------------------------------------
# Routes — health
# ---------------------------------------------------------------------------
@app.get("/health")
@app.get("/api/health")
def health() -> Any:
    logger.info("GET /health — health check requested")
    pipeline = get_pipeline()
    return jsonify(
        {
            "system": "Mento",
            "status": "ok",
            "rag": pipeline.rag.metadata(),
            "local_models": {
                "emotion_model_enabled": settings.use_local_emotion_model,
                "min_available_pagefile_mb": settings.min_available_pagefile_mb,
                "min_embedding_pagefile_mb": settings.min_embedding_pagefile_mb,
            },
            "groq": {
                "intent_key_configured": bool(settings.intent_groq_api_key),
                "rag_key_configured": bool(settings.rag_groq_api_key),
                "intent_model": settings.intent_groq_model,
                "rag_model": settings.rag_groq_model,
            },
            "langsmith_project": settings.langsmith_project,
            "feedback": {
                "apps_script_configured": bool(settings.feedback_apps_script_url),
                "sheet_configured": bool(settings.feedback_google_sheet_id),
                "credentials_configured": bool(
                    settings.google_service_account_json
                    or settings.google_service_account_json_b64
                    or settings.google_service_account_file
                ),
            },
        }
    )


# ---------------------------------------------------------------------------
# Routes — index management
# ---------------------------------------------------------------------------
@app.post("/api/index/rebuild")
def rebuild_index() -> Any:
    logger.info("POST /api/index/rebuild — rebuilding Qdrant index")
    metadata = get_pipeline().rag.rebuild_index()
    logger.info("Qdrant index rebuilt: %s", metadata)
    return jsonify({"status": "rebuilt", "metadata": metadata})


# ---------------------------------------------------------------------------
# Routes — chat (rubric-required: POST /chat)
# ---------------------------------------------------------------------------
@app.post("/chat")
def chat() -> Any:
    """
    Simple JSON endpoint required by the MLOps rubric.
    Runs the full pipeline (crisis detection → language → intent → emotion →
    RAG → guardrails) and returns the complete response as a JSON object.
    Uses the same pipeline as /api/chat/stream — no capabilities removed.
    """
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message") or "").strip()
    session_id = str(payload.get("session_id") or uuid.uuid4())

    if not message:
        logger.info("POST /chat — blank message received, session=%s", session_id)
        return jsonify(
            {
                "response": BLANK_MESSAGE_RESPONSE,
                "session_id": session_id,
                "route": "blank_message",
                "emotion": None,
                "language": "en",
            }
        )

    logger.info("POST /chat — session=%s message_len=%d", session_id, len(message))

    # Collect all events from the streaming pipeline into a single response
    response_text = ""
    metadata: dict[str, Any] = {}

    try:
        for event in get_pipeline().stream(message, session_id):
            event_type = event.get("type")
            if event_type == "token":
                # pipeline yields {"type": "token", "text": "..."} (not "content")
                response_text += event.get("text", "")
            elif event_type == "metadata":
                # pipeline yields {"type": "metadata", "data": asdict(RouteResult)}
                route_data = event.get("data", {})
                if route_data.get("route"):   # top-level RouteResult event
                    metadata = route_data
            elif event_type == "error":
                error_msg = event.get("message", "An error occurred")
                logger.error(
                    "POST /chat — pipeline error session=%s error=%s",
                    session_id,
                    error_msg,
                )
                return jsonify({"status": "error", "message": error_msg}), 500

        # Extract emotion string from nested dict (RouteResult.emotion is a dict)
        emotion_raw = metadata.get("emotion")
        emotion_str = (
            emotion_raw.get("emotion") if isinstance(emotion_raw, dict) else emotion_raw
        )

        logger.info(
            "POST /chat — completed session=%s response_len=%d route=%s",
            session_id,
            len(response_text),
            metadata.get("route", "unknown"),
        )
        return jsonify(
            {
                "response": response_text,
                "session_id": session_id,
                "route": metadata.get("route"),
                "emotion": emotion_str,
                "language": metadata.get("language"),   # "language" = verified language
            }
        )

    except Exception as exc:
        logger.error(
            "POST /chat — unhandled exception session=%s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        return jsonify({"status": "error", "message": public_error(exc)}), 500


@app.post("/api/chat/stream")
def chat_stream() -> Response:
    """
    SSE streaming endpoint — tokens arrive in real time as they are generated.
    Used by the built-in Mento web UI.
    """
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message") or "")
    session_id = str(payload.get("session_id") or uuid.uuid4())
    last_mental_health_topic = str(
        payload.get("last_mental_health_topic") or ""
    ).strip()

    if last_mental_health_topic:
        get_pipeline().last_mental_health_topic[session_id] = last_mental_health_topic

    is_blank_message = not message.strip()

    logger.info(
        "POST /api/chat/stream — session=%s message_len=%d",
        session_id,
        len(message),
    )

    def generate() -> Any:
        yield sse({"type": "session", "session_id": session_id})
        if is_blank_message:
            yield sse(
                {
                    "type": "metadata",
                    "data": {
                        "route": "blank_message",
                        "intent": "blank_message",
                        "language": "en",
                    },
                }
            )
            yield sse({"type": "token", "text": BLANK_MESSAGE_RESPONSE})
            yield sse(
                {
                    "type": "done",
                    "data": {
                        "route": "blank_message",
                        "intent": "blank_message",
                        "response": BLANK_MESSAGE_RESPONSE,
                        "language": "en",
                    },
                }
            )
            return
        try:
            for event in get_pipeline().stream(message, session_id):
                yield sse(event)
            logger.info("POST /api/chat/stream — stream complete session=%s", session_id)
        except Exception as exc:
            logger.error(
                "POST /api/chat/stream — stream error session=%s: %s",
                session_id,
                exc,
                exc_info=True,
            )
            yield sse({"type": "error", "message": public_error(exc)})

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.post("/api/chat/clear")
def clear_chat() -> Any:
    payload = request.get_json(silent=True) or {}
    session_id = str(payload.get("session_id") or "")
    if session_id:
        get_pipeline().clear_history(session_id)
        logger.info("POST /api/chat/clear — cleared history session=%s", session_id)
    return jsonify({"status": "cleared"})


# ---------------------------------------------------------------------------
# Routes — feedback (rubric-required: POST /feedback)
# ---------------------------------------------------------------------------
@app.post("/feedback")
@app.post("/api/feedback")
def submit_feedback() -> Any:
    """Logs thumbs-up / thumbs-down feedback to Google Sheets or Apps Script."""
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query") or "").strip()
    response_text = str(payload.get("response") or "").strip()

    try:
        feedback = normalize_feedback(payload.get("feedback"))
    except ValueError as exc:
        logger.warning("POST /feedback — invalid feedback value: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 400

    if not query or not response_text:
        logger.warning("POST /feedback — missing query or response fields")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Query and response are required for feedback.",
                }
            ),
            400,
        )

    logger.info("POST /feedback — logging feedback=%s", feedback)

    try:
        get_feedback_logger().append(query, response_text, feedback)
        logger.info("POST /feedback — feedback logged successfully")
    except ValueError as exc:
        logger.warning("POST /feedback — validation error: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 400
    except RuntimeError as exc:
        logger.error("POST /feedback — runtime error: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 503
    except Exception as exc:
        logger.error("POST /feedback — unexpected error: %s", exc, exc_info=True)
        return jsonify({"status": "error", "message": public_error(exc)}), 502

    return jsonify({"status": "logged"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info(
        "Starting Flask — host=%s port=%s debug=%s",
        settings.flask_host,
        settings.flask_port,
        settings.flask_debug,
    )
    app.run(
        host=settings.flask_host,
        port=settings.flask_port,
        debug=settings.flask_debug,
        threaded=True,
        use_reloader=False,
    )
