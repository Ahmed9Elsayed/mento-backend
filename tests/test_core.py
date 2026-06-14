"""
tests/test_core.py
------------------
Unit tests for pure Python logic — no HTTP, no mocking needed.
Tests the functions and classes from components.py, feedback_service.py,
and static methods on MentoPipeline that have no external dependencies.
All tests run offline with zero API calls or model loading.
"""

from __future__ import annotations

import pytest

from components import (
    CrisisDetector,
    heuristic_emotion,
    heuristic_guardrail,
    is_followup_affirmation,
    is_mental_health_concern,
    is_system_identity_question,
    regex_direct_intent,
)
from feedback_service import normalize_feedback
from mento_pipeline import MentoPipeline


# ---------------------------------------------------------------------------
# normalize_feedback
# ---------------------------------------------------------------------------

class TestNormalizeFeedback:
    @pytest.mark.parametrize("value", ["like", "thumbs_up", "up"])
    def test_positive_aliases_return_Like(self, value):
        assert normalize_feedback(value) == "Like"

    @pytest.mark.parametrize("value", ["dislike", "thumbs_down", "down"])
    def test_negative_aliases_return_Dislike(self, value):
        assert normalize_feedback(value) == "Dislike"

    @pytest.mark.parametrize("value", ["LIKE", "Like", "THUMBS_UP", "UP"])
    def test_case_insensitive(self, value):
        assert normalize_feedback(value) == "Like"

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_feedback("invalid")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_feedback("")

    def test_none_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_feedback(None)

    def test_returns_string_not_none(self):
        result = normalize_feedback("like")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# CrisisDetector
# ---------------------------------------------------------------------------

class TestCrisisDetector:
    def setup_method(self):
        self.detector = CrisisDetector()

    # --- direct crisis phrases ---
    def test_direct_crisis_phrase_is_detected(self):
        result = self.detector.assess("I want to kill myself")
        assert result.is_direct is True

    def test_end_my_life_is_detected(self):
        result = self.detector.assess("I am going to end my life")
        assert result.is_direct is True

    def test_commit_suicide_is_detected(self):
        result = self.detector.assess("I want to commit suicide")
        assert result.is_direct is True

    # --- safe messages ---
    def test_general_sadness_is_not_flagged(self):
        result = self.detector.assess("I feel very sad today")
        assert result.is_direct is False

    def test_empty_string_is_not_flagged(self):
        result = self.detector.assess("")
        assert result.is_direct is False

    def test_none_like_empty_is_not_flagged(self):
        result = self.detector.assess("   ")
        assert result.is_direct is False

    # --- negated references should NOT be flagged ---
    def test_historical_reference_is_not_flagged(self):
        result = self.detector.assess(
            "I never want to kill myself, I value my life"
        )
        assert result.is_direct is False

    def test_negated_suicidal_is_not_flagged(self):
        result = self.detector.assess("I am not suicidal at all")
        assert result.is_direct is False

    # --- multilingual crisis phrases ---
    def test_arabic_crisis_phrase_is_detected(self):
        # Use "هنتحر" (I will kill myself) — contains no alef variants
        # so the normalizer does not alter it, ensuring a phrase-list match.
        result = self.detector.assess("هنتحر")
        assert result.is_direct is True

    def test_spanish_crisis_phrase_is_detected(self):
        result = self.detector.assess("voy a matarme")
        assert result.is_direct is True

    def test_french_crisis_phrase_is_detected(self):
        result = self.detector.assess("je vais me tuer")
        assert result.is_direct is True

    # --- translated text is also checked ---
    def test_crisis_in_translated_text_is_detected(self):
        # assess(text, translated_text) — positional args only, no keyword "original"
        result = self.detector.assess(
            "أريد أن أنهي حياتي",
            "I want to end my life",
        )
        assert result.is_direct is True

    # --- crisis_response_language result field ---
    def test_is_crisis_convenience_method_true(self):
        assert self.detector.is_crisis("I want to kill myself") is True

    def test_is_crisis_convenience_method_false(self):
        assert self.detector.is_crisis("Good morning") is False

    def test_assess_returns_crisis_assessment_object(self):
        result = self.detector.assess("I feel okay")
        assert hasattr(result, "is_direct")
        assert hasattr(result, "reason")


# ---------------------------------------------------------------------------
# heuristic_emotion
# ---------------------------------------------------------------------------

class TestHeuristicEmotion:
    def test_sad_keyword_returns_sadness(self):
        result = heuristic_emotion("I feel so sad and empty")
        assert result.emotion == "sadness"

    def test_sadness_is_high_distress(self):
        result = heuristic_emotion("I feel lonely and hopeless")
        assert result.high_distress is True

    def test_anxious_keyword_returns_fear(self):
        result = heuristic_emotion("I am very anxious about everything")
        assert result.emotion == "fear"

    def test_fear_is_high_distress(self):
        result = heuristic_emotion("I have a lot of anxiety and panic")
        assert result.high_distress is True

    def test_angry_keyword_returns_anger(self):
        result = heuristic_emotion("I feel angry and furious")
        assert result.emotion == "anger"

    def test_anger_is_high_distress(self):
        result = heuristic_emotion("I am so mad and furious")
        assert result.high_distress is True

    def test_happy_keyword_returns_joy(self):
        result = heuristic_emotion("I feel happy today")
        assert result.emotion == "joy"

    def test_joy_is_not_high_distress(self):
        result = heuristic_emotion("I feel good and happy")
        assert result.high_distress is False

    def test_love_keyword_returns_love(self):
        result = heuristic_emotion("I love my family so much")
        assert result.emotion == "love"

    def test_love_is_not_high_distress(self):
        result = heuristic_emotion("I love them")
        assert result.high_distress is False

    def test_no_keyword_defaults_to_sadness_low_distress(self):
        result = heuristic_emotion("the weather is nice")
        assert result.emotion == "sadness"
        assert result.high_distress is False

    def test_arabic_sadness_keyword_detected(self):
        result = heuristic_emotion("أنا حزين جداً")
        assert result.emotion == "sadness"

    def test_arabic_anxiety_keyword_detected(self):
        result = heuristic_emotion("أنا قلق جداً")
        assert result.emotion == "fear"

    def test_source_field_is_heuristic(self):
        result = heuristic_emotion("I feel sad")
        assert result.source == "heuristic_memory_safe"

    def test_result_has_scores_dict(self):
        result = heuristic_emotion("I feel sad")
        assert isinstance(result.scores, dict)

    def test_detected_emotion_is_in_scores(self):
        result = heuristic_emotion("I feel sad")
        assert result.emotion in result.scores

    def test_confidence_is_float(self):
        result = heuristic_emotion("I feel anxious")
        assert isinstance(result.confidence, float)

    def test_confidence_is_positive(self):
        result = heuristic_emotion("I feel anxious")
        assert result.confidence > 0


# ---------------------------------------------------------------------------
# regex_direct_intent
# ---------------------------------------------------------------------------

class TestRegexDirectIntent:
    # --- greeting ---
    @pytest.mark.parametrize("text", ["hi", "hello", "hey", "good morning"])
    def test_greeting_phrases_detected(self, text):
        assert regex_direct_intent(text) == "greeting"

    # --- goodbye ---
    @pytest.mark.parametrize("text", ["bye", "goodbye", "farewell", "goodnight"])
    def test_goodbye_phrases_detected(self, text):
        assert regex_direct_intent(text) == "goodbye"

    # --- gratitude ---
    @pytest.mark.parametrize("text", ["thank you", "thanks", "thank u"])
    def test_gratitude_phrases_detected(self, text):
        assert regex_direct_intent(text) == "gratitude"

    # --- long messages return None (> 4 words) ---
    def test_long_message_returns_none(self):
        assert regex_direct_intent("I have been feeling very sad lately") is None

    def test_five_word_message_returns_none(self):
        assert regex_direct_intent("hi how are you doing") is None

    # --- unrelated short messages ---
    def test_unrelated_short_message_returns_none(self):
        assert regex_direct_intent("cats and dogs") is None

    def test_empty_string_returns_none(self):
        assert regex_direct_intent("") is None

    def test_case_insensitive_greeting(self):
        assert regex_direct_intent("HELLO") == "greeting"

    def test_case_insensitive_goodbye(self):
        assert regex_direct_intent("BYE") == "goodbye"


# ---------------------------------------------------------------------------
# is_system_identity_question
# ---------------------------------------------------------------------------

class TestIsSystemIdentityQuestion:
    @pytest.mark.parametrize("text", [
        "What is your name?",
        "What's your name",
        "who are you",
        "your name",
    ])
    def test_identity_questions_detected(self, text):
        assert is_system_identity_question(text) is True

    def test_arabic_identity_question_detected(self):
        assert is_system_identity_question("ما اسمك") is True

    def test_regular_message_not_detected(self):
        assert is_system_identity_question("I feel anxious about work") is False

    def test_empty_string_returns_false(self):
        assert is_system_identity_question("") is False

    def test_returns_bool(self):
        result = is_system_identity_question("hello")
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# is_followup_affirmation
# ---------------------------------------------------------------------------

class TestIsFollowupAffirmation:
    @pytest.mark.parametrize("text", ["yes", "yeah", "yep", "sure", "ok", "okay", "please"])
    def test_common_affirmations_detected(self, text):
        assert is_followup_affirmation(text) is True

    @pytest.mark.parametrize("text", ["نعم", "ايوا", "أيوه", "تمام"])
    def test_arabic_affirmations_detected(self, text):
        assert is_followup_affirmation(text) is True

    def test_long_message_not_affirmation(self):
        # > 5 words
        assert is_followup_affirmation("yes I would really like to continue this topic") is False

    def test_empty_string_returns_false(self):
        assert is_followup_affirmation("") is False

    def test_unrelated_word_returns_false(self):
        assert is_followup_affirmation("no") is False

    def test_returns_bool(self):
        result = is_followup_affirmation("yes")
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# is_mental_health_concern
# ---------------------------------------------------------------------------

class TestIsMentalHealthConcern:
    @pytest.mark.parametrize("text", [
        "I have severe anxiety",
        "I feel depressed",
        "I am so stressed",
        "I feel lonely and hopeless",
        "I need therapy",
        "I want to talk about my trauma",
        "I cannot cope with this anymore",
    ])
    def test_mental_health_topics_detected(self, text):
        assert is_mental_health_concern(text) is True

    def test_arabic_keyword_detected(self):
        assert is_mental_health_concern("أشعر بالحزن الشديد") is True

    def test_unrelated_topic_not_detected(self):
        assert is_mental_health_concern("What is the capital of France") is False

    def test_empty_string_not_detected(self):
        assert is_mental_health_concern("") is False

    def test_multiple_args_are_joined(self):
        # is_mental_health_concern accepts *texts
        assert is_mental_health_concern("I feel", "depressed") is True


# ---------------------------------------------------------------------------
# heuristic_guardrail
# ---------------------------------------------------------------------------

class TestHeuristicGuardrail:
    def test_clean_response_not_flagged(self):
        result = heuristic_guardrail(
            "I feel sad",
            "I hear you. It sounds like you are going through a hard time.",
        )
        assert result["is_hallucinated"] is False
        assert result["flags"] == []

    def test_false_attribution_is_flagged(self):
        # Response claims user is depressed, but user didn't mention depression
        result = heuristic_guardrail(
            "I am tired",
            "you are depressed and need help.",
        )
        assert result["is_hallucinated"] is True
        assert len(result["flags"]) > 0

    def test_suspicious_medical_claim_is_flagged(self):
        result = heuristic_guardrail(
            "I feel bad",
            "you are cured, everything will be fine.",
        )
        assert result["is_hallucinated"] is True

    def test_result_has_required_keys(self):
        result = heuristic_guardrail("message", "response")
        assert "is_hallucinated" in result
        assert "flags" in result

    def test_flags_is_a_list(self):
        result = heuristic_guardrail("message", "response")
        assert isinstance(result["flags"], list)


# ---------------------------------------------------------------------------
# MentoPipeline static methods (no __init__ needed — called directly)
# ---------------------------------------------------------------------------

class TestParsePipelineJSON:
    def test_valid_json_object_parsed(self):
        raw = '{"intent": "greeting", "confidence": 0.9}'
        result = MentoPipeline._parse_json(raw)
        assert result["intent"] == "greeting"
        assert result["confidence"] == 0.9

    def test_json_wrapped_in_markdown_code_fence_parsed(self):
        raw = '```json\n{"intent": "greeting"}\n```'
        result = MentoPipeline._parse_json(raw)
        assert result["intent"] == "greeting"

    def test_json_embedded_in_text_extracted(self):
        raw = 'Here is the result: {"intent": "goodbye", "language": "en"} done.'
        result = MentoPipeline._parse_json(raw)
        assert result["intent"] == "goodbye"

    def test_invalid_json_raises_value_error(self):
        with pytest.raises((ValueError, Exception)):
            MentoPipeline._parse_json("not json at all {broken")


class TestExtractStreamText:
    def test_extracts_from_string(self):
        assert MentoPipeline._extract_stream_text("hello") == "hello"

    def test_extracts_content_attribute(self):
        class FakeChunk:
            content = "world"
        assert MentoPipeline._extract_stream_text(FakeChunk()) == "world"

    def test_extracts_answer_from_dict(self):
        assert MentoPipeline._extract_stream_text({"answer": "test"}) == "test"

    def test_extracts_text_from_dict(self):
        assert MentoPipeline._extract_stream_text({"text": "test"}) == "test"

    def test_empty_dict_returns_empty_string(self):
        assert MentoPipeline._extract_stream_text({}) == ""

    def test_none_content_attribute_returns_empty_string(self):
        class FakeChunk:
            content = None
        assert MentoPipeline._extract_stream_text(FakeChunk()) == ""


class TestAddCrisisSupportPrefix:
    def test_english_prefix_prepended(self):
        result = MentoPipeline._add_crisis_support_prefix("I hear you.", "en")
        assert "I hear you." in result
        assert len(result) > len("I hear you.")

    def test_arabic_prefix_prepended(self):
        result = MentoPipeline._add_crisis_support_prefix("أنا هنا.", "ar")
        assert "أنا هنا." in result

    def test_empty_response_returns_just_prefix(self):
        result = MentoPipeline._add_crisis_support_prefix("", "en")
        assert len(result) > 0

    def test_response_not_duplicated_if_prefix_already_present(self):
        from components import crisis_support_prefix_for_language
        prefix = crisis_support_prefix_for_language("en")
        already_prefixed = f"{prefix} I hear you."
        result = MentoPipeline._add_crisis_support_prefix(already_prefixed, "en")
        assert result.count(prefix) == 1


class TestChunkTraceSummary:
    def test_empty_list_returns_empty_list(self):
        assert MentoPipeline._chunk_trace_summary([]) == []

    def test_rank_starts_at_one(self):
        chunks = [{"content": "hello", "source": "s1", "score": 0.9, "metadata": {}}]
        result = MentoPipeline._chunk_trace_summary(chunks)
        assert result[0]["rank"] == 1

    def test_content_preview_is_truncated_to_500(self):
        long_content = "x" * 1000
        chunks = [{"content": long_content, "source": "s", "score": 0.5, "metadata": {}}]
        result = MentoPipeline._chunk_trace_summary(chunks)
        assert len(result[0]["content_preview"]) <= 500

    def test_multiple_chunks_ranked_sequentially(self):
        chunks = [
            {"content": "a", "source": "s1", "score": 0.9, "metadata": {}},
            {"content": "b", "source": "s2", "score": 0.8, "metadata": {}},
        ]
        result = MentoPipeline._chunk_trace_summary(chunks)
        assert result[0]["rank"] == 1
        assert result[1]["rank"] == 2

    def test_result_contains_required_keys(self):
        chunks = [{"content": "text", "source": "src", "score": 0.7, "metadata": {}}]
        result = MentoPipeline._chunk_trace_summary(chunks)
        for key in ("rank", "source", "score", "content_preview", "content_length"):
            assert key in result[0], f"Missing key: {key}"
