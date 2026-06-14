from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Generator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from components import (CrisisDetector, EmotionDetector, LanguageDetector,
                        crisis_response_for_language, crisis_response_language,
                        crisis_support_prefix_for_language, heuristic_guardrail,
                        is_followup_affirmation, is_mental_health_concern,
                        is_system_identity_question)
from prompts import (DIRECT_RESPONSE_SYSTEM_PROMPT, GUARDRAIL_SYSTEM_PROMPT,
                     INTENT_SYSTEM_PROMPT, INTENTS)
from rag_service import RAGService
from settings import Settings

FOLLOWUP_TRANSLATED_PREFIX = (
    "The user wants to continue discussing this mental health topic:"
)


@dataclass
class RouteResult:
    route: str
    intent: str
    translated: str
    language: str
    confidence: float
    layer_used: str
    language_hint: str
    language_hint_confidence: float
    response: str | None = None
    emotion: dict[str, Any] | None = None
    chunks: list[dict[str, Any]] = field(default_factory=list)
    guardrails: dict[str, Any] | None = None
    mental_health_topic: str | None = None
    crisis: dict[str, Any] | None = None


class MentoPipeline:
    def __init__(self, settings: Settings):
        from langchain_groq import ChatGroq

        if not settings.intent_groq_api_key:
            raise RuntimeError("INTENT_GROQ_API_KEY is missing in Module 4/.env")
        if not settings.rag_groq_api_key:
            raise RuntimeError("RAG_GROQ_API_KEY is missing in Module 4/.env")

        self.settings = settings
        self.intent_llm = ChatGroq(
            api_key=settings.intent_groq_api_key,
            model=settings.intent_groq_model,
            temperature=0,
            max_tokens=220,
        )
        self.direct_llm = ChatGroq(
            api_key=settings.intent_groq_api_key,
            model=settings.intent_groq_model,
            temperature=settings.groq_temperature,
            max_tokens=settings.groq_max_tokens,
            streaming=True,
        )
        self.rag_llm = ChatGroq(
            api_key=settings.rag_groq_api_key,
            model=settings.rag_groq_model,
            temperature=settings.groq_temperature,
            max_tokens=settings.groq_max_tokens,
            streaming=True,
        )
        self.guardrail_llm = ChatGroq(
            api_key=settings.rag_groq_api_key,
            model=settings.rag_groq_model,
            temperature=0,
            max_tokens=220,
        )
        self.crisis_detector = CrisisDetector()
        self.language_detector = LanguageDetector(settings)
        self.emotion_detector = EmotionDetector(settings)
        self.rag = RAGService(settings, self.rag_llm)
        self._state_lock = threading.Lock()
        self.histories: dict[str, list[HumanMessage | AIMessage]] = {}
        self.last_mental_health_topic: dict[str, str] = {}

    def get_history(self, session_id: str) -> list[HumanMessage | AIMessage]:
        with self._state_lock:
            return self.histories.setdefault(session_id, [])

    def _history_snapshot(self, session_id: str) -> list[HumanMessage | AIMessage]:
        with self._state_lock:
            return list(self.histories.get(session_id, []))

    def _get_mental_health_topic(self, session_id: str) -> str:
        with self._state_lock:
            return self.last_mental_health_topic.get(session_id, "")

    def _update_mental_health_topic(self, session_id: str, route: RouteResult) -> None:
        if route.translated.startswith(FOLLOWUP_TRANSLATED_PREFIX):
            return
        with self._state_lock:
            self.last_mental_health_topic[session_id] = route.translated

    def clear_history(self, session_id: str) -> None:
        with self._state_lock:
            self.histories.pop(session_id, None)
            self.last_mental_health_topic.pop(session_id, None)

    def analyze_message(self, text: str, language_hint: str) -> dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=INTENT_SYSTEM_PROMPT),
                ("human", 'Message: "{message}" | hint: "{hint}"'),
            ]
        )
        chain = prompt | self.intent_llm

        last_error: Exception | None = None
        for _ in range(3):
            try:
                raw = chain.invoke({"message": text, "hint": language_hint}).content
                parsed = self._parse_json(raw)
                intent = parsed.get("intent")
                if intent not in INTENTS:
                    raise ValueError(f"Invalid intent: {intent}")
                return {
                    "intent": intent,
                    "translated": str(parsed.get("translated") or text),
                    "language": str(parsed.get("language") or language_hint),
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "layer_used": "Layer 2 (LangChain Groq - Intent, Language, Translation)",
                }
            except Exception as exc:
                last_error = exc

        return {
            "intent": "out_of_scope",
            "translated": text,
            "language": language_hint,
            "confidence": 0.0,
            "layer_used": f"Layer 2 fallback ({type(last_error).__name__ if last_error else 'unknown'})",
        }

    def classify(self, user_text: str, session_id: str | None = None) -> RouteResult:
        quick_crisis = self.crisis_detector.assess(user_text)
        if quick_crisis.is_direct:
            lang = (
                None
                if quick_crisis.language
                else self.language_detector.detect(user_text)
            )
            crisis_language = crisis_response_language(
                quick_crisis.language or (lang.language if lang else "en")
            )
            crisis_response = crisis_response_for_language(crisis_language)
            return RouteResult(
                route="direct_crisis",
                intent="asking_mental_health_question",
                translated=self._direct_crisis_retrieval_query(user_text),
                language=crisis_language,
                confidence=1.0,
                layer_used="Layer 1 (Direct crisis guard + predefined language)",
                language_hint=quick_crisis.language or (lang.language if lang else "en"),
                language_hint_confidence=1.0 if quick_crisis.language else (lang.confidence if lang else 0.0),
                response=crisis_response,
                crisis=asdict(quick_crisis),
            )

        lang = self.language_detector.detect(user_text)

        # Module 1 provides only a fast language hint. The intent Groq call must
        # always verify/correct that language before downstream routing.
        llm_result = self.analyze_message(user_text, lang.language)
        crisis = self.crisis_detector.assess(user_text, llm_result["translated"])
        if crisis.is_direct:
            crisis_language = crisis_response_language(
                crisis.language if crisis.source == "original" else lang.language
            )
            translated = self._direct_crisis_retrieval_query(
                str(llm_result.get("translated") or user_text)
            )
            return RouteResult(
                route="direct_crisis",
                intent="asking_mental_health_question",
                translated=translated,
                language=crisis_language,
                confidence=max(float(llm_result.get("confidence", 0.0)), 0.99),
                layer_used=f"{llm_result['layer_used']} + Direct crisis guard",
                language_hint=lang.language,
                language_hint_confidence=lang.confidence,
                response=crisis_response_for_language(crisis_language),
                crisis=asdict(crisis),
            )

        if is_system_identity_question(user_text) or is_system_identity_question(
            llm_result["translated"]
        ):
            llm_result["intent"] = "system_identity"
            llm_result["confidence"] = max(
                float(llm_result.get("confidence", 0.0)), 0.99
            )
        elif self._is_contextual_mental_health_followup(
            user_text, llm_result, session_id
        ):
            previous_topic = self._get_mental_health_topic(session_id)
            llm_result["intent"] = "asking_mental_health_question"
            llm_result["translated"] = f"{FOLLOWUP_TRANSLATED_PREFIX} {previous_topic}"
            llm_result["confidence"] = max(
                float(llm_result.get("confidence", 0.0)), 0.95
            )
            llm_result["layer_used"] = (
                f"{llm_result['layer_used']} + Conversation follow-up"
            )
        elif llm_result.get("intent") == "out_of_scope" and is_mental_health_concern(
            user_text, llm_result["translated"]
        ):
            llm_result["intent"] = "asking_mental_health_question"
            llm_result["confidence"] = max(
                float(llm_result.get("confidence", 0.0)), 0.9
            )
            llm_result["layer_used"] = (
                f"{llm_result['layer_used']} + Mental-health topic guard"
            )

        intent = llm_result["intent"]
        route = "rag_pipeline" if intent == "asking_mental_health_question" else intent
        if intent in {"greeting", "goodbye", "gratitude", "system_identity"}:
            route = "direct"
        elif intent == "out_of_scope":
            route = "out_of_scope"

        return RouteResult(
            route=route,
            intent=intent,
            translated=llm_result["translated"],
            language=llm_result["language"],
            confidence=llm_result["confidence"],
            layer_used=llm_result["layer_used"],
            language_hint=lang.language,
            language_hint_confidence=lang.confidence,
        )

    def stream(
        self, user_text: str, session_id: str
    ) -> Generator[dict[str, Any], None, None]:
        user_text = (user_text or "").strip()
        if not user_text:
            yield {"type": "error", "message": "Please enter a message."}
            return

        route = self.classify(user_text, session_id)
        yield {"type": "metadata", "data": asdict(route)}

        if route.route == "direct_crisis":
            response = route.response or crisis_response_for_language(route.language)
            yield from self._emit_answer(response)

            support_route = RouteResult(
                route="rag_pipeline",
                intent="asking_mental_health_question",
                translated=route.translated,
                language=route.language,
                confidence=route.confidence,
                layer_used=f"{route.layer_used} + Crisis-aware RAG follow-up",
                language_hint=route.language_hint,
                language_hint_confidence=route.language_hint_confidence,
                crisis=route.crisis,
            )
            support_response = yield from self._prepare_rag(
                support_route, user_text, session_id
            )
            support_response = self._add_crisis_support_prefix(
                support_response, route.language
            )
            support_response, support_route.guardrails = self._finalize_response(
                user_text,
                support_response,
                route.language,
                support_route.chunks,
            )
            support_route.response = support_response
            self._update_mental_health_topic(session_id, support_route)
            support_route.mental_health_topic = (
                self._get_mental_health_topic(session_id) or None
            )

            route.response = f"{response}\n\n{support_response}".strip()
            route.emotion = support_route.emotion
            route.chunks = support_route.chunks
            route.guardrails = support_route.guardrails
            route.mental_health_topic = support_route.mental_health_topic

            yield {"type": "new_assistant_message"}
            yield from self._emit_answer(support_response)
            self._remember(session_id, user_text, route.response)
            yield {"type": "done", "data": asdict(route)}
            return

        if route.route == "crisis":
            response = route.response or crisis_response_for_language(route.language)
            route.response = response
            yield from self._emit_answer(response)
            self._remember(session_id, user_text, response)
            yield {"type": "done", "data": asdict(route)}
            return

        if route.confidence < 0.5:
            response = "I want to make sure I understand you correctly. Could you rephrase that?"
            route.route = "clarification"
            route.response = response
            yield from self._emit_answer(response)
            self._remember(session_id, user_text, response)
            yield {"type": "done", "data": asdict(route)}
            return

        if route.route in {"direct", "out_of_scope"}:
            response = self._generate_direct_response(route, user_text)
            response, route.guardrails = self._finalize_response(
                user_text, response, route.language
            )
            route.response = response
            yield from self._emit_answer(response)
            self._remember(session_id, user_text, response)
            yield {"type": "done", "data": asdict(route)}
            return

        if route.route == "rag_pipeline":
            response = yield from self._prepare_rag(route, user_text, session_id)
            response, route.guardrails = self._finalize_response(
                user_text, response, route.language, route.chunks
            )
            route.response = response
            self._update_mental_health_topic(session_id, route)
            route.mental_health_topic = (
                self._get_mental_health_topic(session_id) or None
            )
            yield from self._emit_answer(response)
            self._remember(session_id, user_text, response)
            yield {"type": "done", "data": asdict(route)}
            return

        response = "I'm specialized in mental health support. Is there anything related to your emotional wellbeing I can help with?"
        route.response = response
        yield from self._emit_answer(response)
        self._remember(session_id, user_text, response)
        yield {"type": "done", "data": asdict(route)}

    def _prepare_rag(
        self, route: RouteResult, user_text: str, session_id: str
    ) -> Generator[dict[str, Any], None, str]:
        try:
            emotion = self.emotion_detector.detect(route.translated)
        except Exception as exc:
            emotion = None
            route.emotion = {
                "emotion": "unknown",
                "confidence": 0.0,
                "scores": {},
                "high_distress": False,
                "error": self._public_runtime_issue(exc),
            }
            yield {"type": "metadata", "data": {"emotion": route.emotion}}
            yield {"type": "notice", "message": route.emotion["error"]}

        if emotion is None:
            return self._generate_resource_fallback(route, user_text, session_id)

        route.emotion = asdict(emotion)
        yield {"type": "metadata", "data": {"emotion": route.emotion}}

        try:
            chunks = self.rag.retrieve_chunks(
                route.translated, self.settings.retriever_k
            )
        except Exception as exc:
            route.chunks = []
            issue = self._public_runtime_issue(exc)
            yield {
                "type": "metadata",
                "data": {"chunks": route.chunks, "rag_error": issue},
            }
            yield {"type": "notice", "message": issue}
            return self._generate_resource_fallback(route, user_text, session_id)

        route.chunks = [
            {
                "content": chunk.content,
                "source": chunk.source,
                "score": chunk.score,
                "metadata": chunk.metadata or {},
            }
            for chunk in chunks
        ]
        yield {"type": "metadata", "data": {"chunks": route.chunks}}
        retrieved_chunks = self._chunk_trace_summary(route.chunks)

        chain_input = {
            "input": route.translated,
            "emotion": emotion.emotion,
            "distress_level": "HIGH" if emotion.high_distress else "NORMAL",
            "verified_language": route.language,
            "retrieved_chunks": retrieved_chunks,
            "chat_history": self._history_snapshot(session_id),
        }

        answer = ""
        try:
            for chunk in self.rag.chain.stream(
                chain_input,
                config={
                    "run_name": "Mento.RAG.answer_from_retrieved_chunks",
                    "tags": ["mento", "rag", "retrieved-chunks"],
                    "metadata": {
                        "session_id": session_id,
                        "system": "Mento",
                        "route": route.route,
                        "retrieval_query": route.translated,
                        "retrieved_chunk_count": len(retrieved_chunks),
                        "retrieved_chunks": retrieved_chunks,
                    },
                },
            ):
                token = self._extract_stream_text(chunk)
                if token:
                    answer += token
        except Exception as exc:
            issue = self._public_runtime_issue(exc)
            yield {"type": "notice", "message": issue}
            return self._generate_resource_fallback(route, user_text, session_id)

        if not answer.strip():
            answer = (
                "I hear you, and I am glad you reached out. Try one small grounding step now, such as slowing "
                "your breathing, and consider speaking with someone you trust or a mental health professional for support."
            )

        return answer.strip()

    def _generate_resource_fallback(
        self, route: RouteResult, user_text: str, session_id: str
    ) -> str:
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content=(
                        "You are Mento, a compassionate mental health support assistant. "
                        "The local RAG/emotion resources are temporarily unavailable, so answer without retrieved context. "
                        "Do not mention internal errors. Respond in the verified language. Keep it supportive and concise."
                    )
                ),
                (
                    "human",
                    "Verified language: {language}\nCleaned English message: {translated}\nOriginal message: {original}",
                ),
            ]
        )
        chain = prompt | self.rag_llm
        answer = ""
        try:
            for chunk in chain.stream(
                {
                    "language": route.language,
                    "translated": route.translated,
                    "original": user_text,
                },
                config={
                    "metadata": {
                        "session_id": session_id,
                        "route": "resource_fallback",
                        "system": "Mento",
                    }
                },
            ):
                token = self._extract_stream_text(chunk)
                if token:
                    answer += token
        except Exception:
            answer = self._localized_support_fallback(route.language)
        return answer.strip()

    def _generate_direct_response(self, route: RouteResult, user_text: str) -> str:
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=DIRECT_RESPONSE_SYSTEM_PROMPT),
                (
                    "human",
                    "Intent: {intent}\nVerified language: {language}\nUser message: {message}",
                ),
            ]
        )
        chain = prompt | self.direct_llm
        answer = ""
        try:
            for chunk in chain.stream(
                {
                    "intent": route.intent,
                    "language": route.language,
                    "message": user_text,
                },
                config={"metadata": {"route": route.route, "system": "Mento"}},
            ):
                token = self._extract_stream_text(chunk)
                if token:
                    answer += token
        except Exception:
            return self._direct_fallback(route)
        if not answer.strip():
            return self._direct_fallback(route)
        return answer.strip()

    def _finalize_response(
        self,
        user_text: str,
        response: str,
        language: str,
        retrieved_chunks: list[dict[str, Any]] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        guarded = self.apply_guardrails(
            user_text, response, language, retrieved_chunks
        )
        if guarded.get("is_hallucinated"):
            return (
                str(
                    guarded.get("revised_response")
                    or self._localized_support_fallback(language)
                ).strip(),
                guarded,
            )
        return response.strip(), guarded

    def apply_guardrails(
        self,
        user_text: str,
        response: str,
        language: str,
        retrieved_chunks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        heuristic = heuristic_guardrail(user_text, response)
        chunk_summary = self._chunk_trace_summary(retrieved_chunks or [])
        llm_result: dict[str, Any] = {
            "is_hallucinated": False,
            "flags": [],
            "revised_response": None,
        }

        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=GUARDRAIL_SYSTEM_PROMPT),
                (
                    "human",
                    "Language: {language}\nUser text: {user_text}\nGenerated response: {response}",
                ),
            ]
        )
        try:
            guardrail_input = {
                "language": language,
                "user_text": user_text,
                "response": response,
                "retrieved_chunks": chunk_summary,
            }
            raw = (
                (prompt | self.guardrail_llm)
                .invoke(
                    guardrail_input,
                    config={
                        "run_name": "Mento.guardrail.check_response_with_chunks",
                        "tags": ["mento", "guardrail", "retrieved-chunks"],
                        "metadata": {
                            "system": "Mento",
                            "retrieved_chunk_count": len(chunk_summary),
                            "retrieved_chunks": chunk_summary,
                        },
                    },
                )
                .content
            )
            parsed = self._parse_json(raw)
            safe = bool(parsed.get("safe", True))
            llm_result = {
                "is_hallucinated": not safe,
                "flags": (
                    []
                    if safe
                    else [str(parsed.get("reason", "LLM guardrail flagged response"))]
                ),
                "revised_response": (
                    parsed.get("revised_response") if not safe else None
                ),
            }
        except Exception:
            pass

        is_hallucinated = bool(heuristic.get("is_hallucinated")) or bool(
            llm_result.get("is_hallucinated")
        )
        flags = list(heuristic.get("flags", [])) + list(llm_result.get("flags", []))
        revised_response = llm_result.get("revised_response")
        if is_hallucinated and not revised_response:
            revised_response = self._localized_support_fallback(language)

        return {
            "is_hallucinated": is_hallucinated,
            "flags": flags,
            "revised_response": revised_response if is_hallucinated else None,
            "retrieved_chunk_count": len(chunk_summary),
        }

    def _remember(self, session_id: str, user_text: str, response: str) -> None:
        with self._state_lock:
            history = self.histories.setdefault(session_id, [])
            history.append(HumanMessage(content=user_text))
            history.append(AIMessage(content=response))
            if len(history) > 12:
                del history[: len(history) - 12]

    def _direct_fallback(self, route: RouteResult) -> str:
        if route.route == "out_of_scope":
            return "I'm specialized in mental health support. Is there anything related to your emotional wellbeing I can help with?"
        if route.intent == "system_identity":
            return "My name is Mento. I'm here to support your emotional wellbeing."
        if route.intent == "gratitude":
            return "You're very welcome. I'm here whenever you need support."
        if route.intent == "goodbye":
            return "Take care of yourself. Support is here whenever you need it."
        return "Hello, I'm Mento. I'm here to support your emotional wellbeing."

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        cleaned = re.sub(r"```json|```", "", raw or "").strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        if start == -1:
            raise ValueError("No JSON object found in model output")

        parsed, _ = json.JSONDecoder().raw_decode(cleaned, start)
        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object in model output")
        return parsed

    @staticmethod
    def _extract_stream_text(chunk: Any) -> str:
        if isinstance(chunk, str):
            return chunk
        if isinstance(chunk, dict):
            if "answer" in chunk:
                value = chunk["answer"]
                return value if isinstance(value, str) else ""
            if "text" in chunk:
                return str(chunk["text"])
            return ""
        content = getattr(chunk, "content", None)
        return content if isinstance(content, str) else ""

    @staticmethod
    def _public_runtime_issue(exc: Exception) -> str:
        message = str(exc).lower()
        if (
            isinstance(exc, MemoryError)
            or "paging file is too small" in message
            or "os error 1455" in message
        ):
            return "Local memory is too low to load the RAG resources right now, so I am using a safe fallback response."
        if "network error" in message or "connection" in message:
            return "A RAG network call was unavailable, so I am using a safe fallback response."
        return "A local RAG resource was unavailable, so I am using a safe fallback response."

    @staticmethod
    def _chunk_trace_summary(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        summary = []
        for index, chunk in enumerate(chunks or [], start=1):
            content = str(chunk.get("content") or chunk.get("content_preview") or "")
            summary.append(
                {
                    "rank": index,
                    "source": chunk.get("source"),
                    "score": chunk.get("score"),
                    "metadata": chunk.get("metadata") or {},
                    "content_preview": content[:500],
                    "content_length": len(content),
                }
            )
        return summary

    @staticmethod
    def _localized_support_fallback(language: str) -> str:
        if language == "ar":
            return "أفهم ما تشعر به، وأنا هنا لدعمك. جرّب أخذ نفس بطيء الآن، وإذا كان الشعور شديداً فتحدث مع شخص تثق به أو مختص في الصحة النفسية."
        return "I hear you, and I am here with you. Try one small grounding step now, like slowing your breathing, and consider talking with someone you trust or a mental health professional."

    @staticmethod
    def _add_crisis_support_prefix(response: str, language: str) -> str:
        prefix = crisis_support_prefix_for_language(language)
        response = (response or "").strip()
        if not response:
            return prefix
        if response.startswith(prefix):
            return response
        return f"{prefix} {response}".strip()

    @staticmethod
    def _direct_crisis_retrieval_query(translated_text: str) -> str:
        translated_text = (translated_text or "").strip()
        lowered = translated_text.lower()
        english_markers = (
            "kill myself",
            "end my life",
            "take my life",
            "commit suicide",
            "die by suicide",
            "hurt myself",
            "harm myself",
            "overdose",
            "can't stay safe",
            "cannot stay safe",
            "want to die",
        )
        if any(marker in lowered for marker in english_markers):
            return translated_text
        return (
            "The user says they may harm themselves now or end their life soon. "
            "They need immediate crisis support, grounding, and help staying safe."
        )

    def _is_contextual_mental_health_followup(
        self,
        user_text: str,
        llm_result: dict[str, Any],
        session_id: str | None,
    ) -> bool:
        if not session_id or not self._get_mental_health_topic(session_id):
            return False
        if llm_result.get("intent") == "asking_mental_health_question":
            return False
        return is_followup_affirmation(user_text)

    @staticmethod
    def _emit_answer(text: str) -> Generator[dict[str, Any], None, None]:
        words = text.split(" ")
        for index, word in enumerate(words):
            suffix = " " if index < len(words) - 1 else ""
            yield {"type": "token", "text": word + suffix}
