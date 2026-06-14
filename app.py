from __future__ import annotations

import json
import uuid
from functools import lru_cache
from typing import Any

from flask import (Flask, Response, jsonify, render_template, request,
                   stream_with_context)

from feedback_service import FeedbackLogger, normalize_feedback
from mento_pipeline import MentoPipeline
from settings import load_settings

app = Flask(__name__)
settings = load_settings()


@lru_cache(maxsize=1)
def get_pipeline() -> MentoPipeline:
    pipeline = MentoPipeline(settings)
    if settings.build_index_on_startup:
        pipeline.rag.ensure_index()
    return pipeline


@lru_cache(maxsize=1)
def get_feedback_logger() -> FeedbackLogger:
    return FeedbackLogger(settings)


def sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def public_error(exc: Exception) -> str:
    message = str(exc).lower()
    if (
        isinstance(exc, MemoryError)
        or "paging file is too small" in message
        or "os error 1455" in message
    ):
        return "Local memory is too low to complete that operation right now. Please close other apps or increase the Windows paging file, then try again."
    if "network error" in message or "connection" in message:
        return "A local or external network connection failed during this request. Please try again after confirming Flask, Groq, and Qdrant are reachable."
    return str(exc)


@app.get("/")
def index() -> str:
    return render_template("index.html", system_name="Mento")


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status=204)


@app.get("/api/health")
def health() -> Any:
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


@app.post("/api/index/rebuild")
def rebuild_index() -> Any:
    metadata = get_pipeline().rag.rebuild_index()
    return jsonify({"status": "rebuilt", "metadata": metadata})


@app.post("/api/chat/clear")
def clear_chat() -> Any:
    payload = request.get_json(silent=True) or {}
    session_id = str(payload.get("session_id") or "")
    if session_id:
        get_pipeline().clear_history(session_id)
    return jsonify({"status": "cleared"})


@app.post("/api/feedback")
def submit_feedback() -> Any:
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query") or "").strip()
    response_text = str(payload.get("response") or "").strip()

    try:
        feedback = normalize_feedback(payload.get("feedback"))
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    if not query or not response_text:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Query and response are required for feedback.",
                }
            ),
            400,
        )

    try:
        get_feedback_logger().append(query, response_text, feedback)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 503
    except Exception as exc:
        app.logger.exception("Failed to log feedback")
        return jsonify({"status": "error", "message": public_error(exc)}), 502

    return jsonify({"status": "logged"})


@app.post("/api/chat/stream")
def chat_stream() -> Response:
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message") or "")
    session_id = str(payload.get("session_id") or uuid.uuid4())
    last_mental_health_topic = str(
        payload.get("last_mental_health_topic") or ""
    ).strip()
    if last_mental_health_topic:
        get_pipeline().last_mental_health_topic[session_id] = last_mental_health_topic

    def generate() -> Any:
        yield sse({"type": "session", "session_id": session_id})
        try:
            for event in get_pipeline().stream(message, session_id):
                yield sse(event)
        except Exception as exc:
            yield sse({"type": "error", "message": public_error(exc)})

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(
        host=settings.flask_host,
        port=settings.flask_port,
        debug=settings.flask_debug,
        threaded=True,
        use_reloader=False,
    )
