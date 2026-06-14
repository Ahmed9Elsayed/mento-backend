from __future__ import annotations

import argparse
import traceback

from app import get_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Mento Module 4 wiring.")
    parser.add_argument(
        "--e2e", action="store_true", help="Run one Groq end-to-end query."
    )
    parser.add_argument(
        "--router-debug", action="store_true", help="Print the raw router result."
    )
    args = parser.parse_args()

    pipeline = get_pipeline()
    print(f"Intent Groq key configured: {bool(pipeline.settings.intent_groq_api_key)}")
    print(f"RAG Groq key configured: {bool(pipeline.settings.rag_groq_api_key)}")

    language = pipeline.language_detector.detect("Hello, I feel anxious today")
    print(f"Module 1 language: {language.language} ({language.confidence:.2%})")

    emotion = pipeline.emotion_detector.detect("I feel anxious and cannot sleep")
    print(f"Module 2 emotion: {emotion.emotion} ({emotion.confidence:.2%})")

    rag_meta = pipeline.rag.metadata()
    print(f"Qdrant collection: {rag_meta['collection']} | points: {rag_meta['points']}")

    chunks = pipeline.rag.retrieve_chunks("I feel anxious and cannot sleep", 2)
    print(f"RAG retrieval: {len(chunks)} chunks")

    if args.router_debug:
        result = pipeline.analyze_message(
            "I feel anxious and cannot sleep. What can I do?", "en"
        )
        print(f"Router: {result}")

    if args.e2e:
        text = ""
        final = None
        for event in pipeline.stream(
            "I feel anxious and cannot sleep. What can I do?", "validation-session"
        ):
            if event.get("type") == "token":
                text += event.get("text", "")
            elif event.get("type") == "done":
                final = event.get("data")
        print(f"E2E route: {final.get('route') if final else None}")
        print(f"E2E intent: {final.get('intent') if final else None}")
        print(f"E2E language: {final.get('language') if final else None}")
        print(
            f"E2E emotion: {(final.get('emotion') or {}).get('emotion') if final else None}"
        )
        print(f"E2E chunks: {len(final.get('chunks') or []) if final else 0}")
        print(f"E2E response: {text[:300].replace(chr(10), ' ')}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
