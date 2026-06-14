from __future__ import annotations

import re
import sys
import warnings
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np

from settings import Settings

LANGUAGE_MAP = {
    0: "ar",
    1: "bg",
    2: "de",
    3: "el",
    4: "en",
    5: "es",
    6: "fr",
    7: "hi",
    8: "it",
    9: "ja",
    10: "nl",
    11: "pl",
    12: "pt",
    13: "ru",
    14: "sw",
    15: "th",
    16: "tr",
    17: "ur",
    18: "vi",
    19: "zh",
}

ID2EMOTION = {
    0: "sadness",
    1: "joy",
    2: "love",
    3: "anger",
    4: "fear",
    5: "surprise",
}

CRISIS_RESPONSE = (
    "Your safety matters right now. If you might harm yourself or feel unable to stay safe, "
    "please call local emergency services now or contact a crisis line immediately. In the US "
    "or Canada, call or text 988. If you are elsewhere, contact your local emergency number "
    "or use https://www.iasp.info/resources/Crisis_Centres/ to find support. Please move away "
    "from anything you could use to hurt yourself and tell someone near you what is happening now."
)

CRISIS_RESPONSES = {
    "ar": (
        "سلامتك مهمة الآن. إذا كنت قد تؤذي نفسك أو لا تستطيع البقاء آمناً، فاتصل بخدمات "
        "الطوارئ المحلية الآن أو بخط مساعدة الأزمات فوراً. إذا كنت في الولايات المتحدة أو "
        "كندا فاتصل أو أرسل رسالة إلى 988، وإذا كنت في مكان آخر فاتصل برقم الطوارئ المحلي "
        "أو استخدم https://www.iasp.info/resources/Crisis_Centres/. ابتعد عن أي شيء قد تستخدمه "
        "لإيذاء نفسك وأخبر شخصاً قريباً منك بما يحدث الآن."
    ),
    "es": (
        "Tu seguridad importa ahora. Si podrías hacerte daño o no puedes mantenerte a salvo, "
        "llama ahora a los servicios de emergencia locales o contacta una línea de crisis de "
        "inmediato. En EE. UU. o Canadá, llama o envía un mensaje al 988. Si estás en otro lugar, "
        "contacta tu número local de emergencia o usa https://www.iasp.info/resources/Crisis_Centres/. "
        "Aléjate de cualquier cosa que puedas usar para hacerte daño y cuéntale a alguien cercano "
        "lo que está pasando ahora."
    ),
    "fr": (
        "Votre sécurité compte maintenant. Si vous risquez de vous faire du mal ou si vous ne "
        "vous sentez pas capable de rester en sécurité, contactez immédiatement les services "
        "d'urgence locaux ou une ligne d'aide en cas de crise. Aux États-Unis ou au Canada, "
        "appelez ou envoyez un SMS au 988. Ailleurs, contactez le numéro d'urgence local ou "
        "utilisez https://www.iasp.info/resources/Crisis_Centres/. Éloignez-vous de tout ce qui "
        "pourrait servir à vous blesser et dites à quelqu'un près de vous ce qui se passe."
    ),
    "hi": (
        "आपकी सुरक्षा अभी सबसे ज़रूरी है। अगर आप खुद को नुकसान पहुँचा सकते हैं या सुरक्षित "
        "नहीं रह पा रहे हैं, तो कृपया अभी स्थानीय आपातकालीन सेवाओं या किसी संकट हेल्पलाइन से "
        "संपर्क करें। अमेरिका या कनाडा में 988 पर कॉल या टेक्स्ट करें। अगर आप कहीं और हैं, तो "
        "अपने स्थानीय आपातकालीन नंबर या https://www.iasp.info/resources/Crisis_Centres/ का उपयोग "
        "करें। खुद को नुकसान पहुँचाने वाली चीज़ों से दूर जाएँ और अपने पास मौजूद किसी व्यक्ति "
        "को अभी बताएं कि क्या हो रहा है।"
    ),
    "zh": (
        "你现在的安全最重要。如果你可能伤害自己，或觉得无法保持安全，请立即联系当地紧急服务或危机热线。"
        "如果你在美国或加拿大，请拨打或短信联系 988。如果你在其他地方，请联系当地紧急电话，或使用 "
        "https://www.iasp.info/resources/Crisis_Centres/。请远离任何可能用来伤害自己的东西，并告诉身边的人现在发生了什么。"
    ),
}

SUPPORTED_CRISIS_RESPONSE_LANGUAGES = {"en", "ar", "es", "fr", "zh", "hi"}


def crisis_response_language(language: str) -> str:
    code = (language or "en").lower().split("-")[0]
    return code if code in SUPPORTED_CRISIS_RESPONSE_LANGUAGES else "en"


def crisis_response_for_language(language: str) -> str:
    code = crisis_response_language(language)
    return CRISIS_RESPONSES.get(code, CRISIS_RESPONSE)


CRISIS_SUPPORT_PREFIXES = {
    "ar": "وبينما تطلب مساعدة فورية، دعنا نركز على عبور الدقائق القليلة القادمة بأمان.",
    "en": "While you reach out for immediate help, let's focus on getting through the next few minutes safely.",
    "es": "Mientras buscas ayuda inmediata, enfoquémonos en pasar los próximos minutos con seguridad.",
    "fr": "Pendant que vous cherchez une aide immédiate, concentrons-nous sur les prochaines minutes en sécurité.",
    "hi": "जब तक आप तुरंत मदद के लिए संपर्क कर रहे हैं, आइए अगले कुछ मिनट सुरक्षित रूप से निकालने पर ध्यान दें।",
    "zh": "在你联系紧急帮助的同时，我们先专注于安全度过接下来的几分钟。",
}


def crisis_support_prefix_for_language(language: str) -> str:
    code = crisis_response_language(language)
    return CRISIS_SUPPORT_PREFIXES.get(code, CRISIS_SUPPORT_PREFIXES["en"])


@dataclass
class CrisisAssessment:
    is_direct: bool
    reason: str
    matched_text: str | None = None
    source: str | None = None
    language: str | None = None


@dataclass
class LanguageResult:
    language: str
    confidence: float


@dataclass
class EmotionResult:
    emotion: str
    confidence: float
    scores: dict[str, float]
    high_distress: bool
    source: str = "local_model"


class CrisisDetector:
    _DIRECT_PATTERNS = [
        r"\b(?:i\s+)?(?:will|shall)\s+(?:kill myself|end my life|take my life|commit suicide|die by suicide|hurt myself|harm myself|overdose|hang myself|jump off|cut my wrists)\b",
        r"\b(?:i\s+)?(?:am|i'm|im)\s+(?:going|planning)\s+to\s+(?:kill myself|end my life|take my life|commit suicide|die by suicide|hurt myself|harm myself|overdose|hang myself|jump off|cut my wrists)\b",
        r"\b(?:i\s+)?(?:am|i'm|im)\s+about\s+to\s+(?:kill myself|end my life|take my life|commit suicide|die by suicide|hurt myself|harm myself|overdose|hang myself|jump off|cut my wrists)\b",
        r"\b(?:i\s+)?(?:want|need)\s+to\s+(?:kill myself|end my life|take my life|commit suicide|die by suicide|hurt myself|harm myself|die|overdose|hang myself|jump off|cut my wrists)\b",
        r"\b(?:i\s+)?(?:might|may)\s+(?:kill myself|end my life|take my life|commit suicide|die by suicide|hurt myself|harm myself)\b",
        r"\b(?:i\s+)?(?:can't|cannot|can not)\s+(?:keep|stay)\s+(?:myself\s+)?safe\b",
        r"\b(?:i\s+)?have\s+(?:a\s+)?plan\s+to\s+(?:kill myself|end my life|take my life|commit suicide|die by suicide|hurt myself|harm myself)\b",
        r"\b(?:kill myself|end my life|take my life|commit suicide|die by suicide|hurt myself|harm myself)\s+(?:now|tonight|today|soon|right now)\b",
        r"\b(?:i\s+)?(?:just\s+)?(?:took|have taken)\s+(?:an\s+)?overdose\b",
        r"\b(?:i\s+)?(?:am|i'm|im)\s+going\s+to\s+(?:kms|k\s*m\s*s)\b",
    ]
    _DIRECT_PHRASES = {
        "ar": [
            "سأقتل نفسي",
            "هقتل نفسي",
            "سوف أقتل نفسي",
            "أريد أن أقتل نفسي",
            "عايز أقتل نفسي",
            "سأنهي حياتي",
            "سوف أنهي حياتي",
            "هأنهي حياتي",
            "سأنتحر",
            "هنتحر",
            "عايز أموت دلوقتي",
            "هموت نفسي عليك",
            "هصفي نفسي دلوقتي",
        ],
        "es": [
            "voy a matarme",
            "quiero matarme",
            "voy a suicidarme",
            "voy a quitarme la vida",
            "quiero morir ahora",
        ],
        "fr": [
            "je vais me tuer",
            "je veux me tuer",
            "je vais me suicider",
            "je vais mettre fin à ma vie",
            "je veux mourir maintenant",
        ],
        "hi": [
            "मैं खुद को मार दूंगा",
            "मैं खुद को मारना चाहता हूँ",
            "मैं अपनी जान लेने वाला हूँ",
        ],
        "zh": [
            "我要自杀",
            "我要杀了自己",
            "我今晚要结束生命",
        ],
    }
    _NEGATED_REFERENCE_PATTERNS = [
        r"\b(?:i\s+)?(?:do not|don't|dont|did not|didn't|never|not)\s+(?:want|plan|intend|think|feel|contemplate|consider|attempt|try|tried)\b.{0,90}\b(?:suicide|kill myself|die|end my life|hurt myself|harm myself|self harm|self-harm)\b",
        r"\b(?:i've|ive|i have)\s+never\b.{0,90}\b(?:suicide|kill myself|end my life|hurt myself|harm myself|self harm|self-harm)\b",
        r"\bnot\s+(?:suicidal|going to kill myself|planning to kill myself|trying to kill myself)\b",
        r"\b(?:no|not)\s+(?:suicidal|suicide|self-harm|self harm)\s+(?:thoughts|ideation|plans|intent)\b",
    ]
    _DIRECT_LANGUAGE_PATTERNS = {
        "ar": [
            r"(?:انا\s+)?ه[موة]+ت\s+نفسي(?:\s+(?:حالا|دلوقتي|الان|الآن|الليلة|النهارده|اليوم))?",
            r"(?:انا\s+)?هقتل\s+نفسي(?:\s+(?:حالا|دلوقتي|الان|الآن|الليلة|النهارده|اليوم))?",
            r"(?:انا\s+)?هنتحر(?:\s+(?:حالا|دلوقتي|الان|الآن|الليلة|النهارده|اليوم))?",
            r"(?:انا\s+)?عاي[ززة]\s+(?:اموت|اقتل\s+نفسي|انتحر)(?:\s+(?:حالا|دلوقتي|الان|الآن|الليلة|النهارده|اليوم))?",
            r"(?:انا\s+)?اريد\s+(?:ان\s+)?(?:اموت|اقتل\s+نفسي|انتحر)(?:\s+(?:الان|الآن|الليلة|اليوم))?",
        ],
        "es": [
            r"(?:voy|quiero)\s+a\s+(?:matarme|suicidarme)(?:\s+(?:ahora|hoy|esta\s+noche))?",
            r"voy\s+a\s+quitarme\s+la\s+vida(?:\s+(?:ahora|hoy|esta\s+noche))?",
        ],
        "fr": [
            r"je\s+(?:vais|veux)\s+me\s+(?:tuer|suicider)(?:\s+(?:maintenant|ce\s+soir|aujourd'hui))?",
            r"je\s+vais\s+mettre\s+fin\s+a\s+ma\s+vie(?:\s+(?:maintenant|ce\s+soir|aujourd'hui))?",
        ],
        "hi": [
            r"मैं\s+खुद\s+को\s+मार(?:ना\s+चाहता\s+हूँ|ना\s+चाहती\s+हूँ|दूंगा|दूंगी)",
            r"मैं\s+अपनी\s+जान\s+लेने\s+वाला\s+हूँ",
        ],
        "zh": [
            r"我要自杀",
            r"我要杀了自己",
            r"我今晚要结束生命",
        ],
    }

    def assess(
        self, text: str, translated_text: str | None = None
    ) -> CrisisAssessment:
        candidates = [
            ("translated", translated_text),
            ("original", text),
        ]
        for source, candidate in candidates:
            normalized = self._normalize(candidate)
            if not normalized:
                continue
            if self._has_negated_reference(normalized):
                return CrisisAssessment(
                    is_direct=False,
                    reason="negated_or_historical_crisis_reference",
                    source=source,
                )
            matched_text, matched_language = self._direct_match(normalized)
            if matched_text:
                return CrisisAssessment(
                    is_direct=True,
                    reason="direct_or_immediate_self_harm_intent",
                    matched_text=matched_text,
                    source=source,
                    language=matched_language,
                )
        return CrisisAssessment(is_direct=False, reason="no_direct_crisis_intent")

    def is_crisis(self, text: str) -> bool:
        return self.assess(text).is_direct

    @staticmethod
    def _normalize(text: str | None) -> str:
        if not text or not isinstance(text, str):
            return ""
        normalized = text.replace("’", "'").replace("`", "'")
        normalized = re.sub("[\u064b-\u065f\u0670\u0640]", "", normalized)
        normalized = normalized.translate(
            str.maketrans(
                {
                    "أ": "ا",
                    "إ": "ا",
                    "آ": "ا",
                    "ٱ": "ا",
                    "ى": "ي",
                }
            )
        )
        normalized = re.sub(r"\s+", " ", normalized.strip().lower())
        return normalized

    def _has_negated_reference(self, normalized: str) -> bool:
        return any(
            re.search(pattern, normalized, flags=re.IGNORECASE)
            for pattern in self._NEGATED_REFERENCE_PATTERNS
        )

    def _direct_match(self, normalized: str) -> tuple[str | None, str | None]:
        for pattern in self._DIRECT_PATTERNS:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                return match.group(0), "en"
        for language, patterns in self._DIRECT_LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, normalized, flags=re.IGNORECASE)
                if match:
                    return match.group(0), language
        for language, phrases in self._DIRECT_PHRASES.items():
            for phrase in phrases:
                if phrase in normalized:
                    return phrase, language
        return None, None


class LanguageDetector:
    def __init__(self, settings: Settings):
        self.settings = settings

    @cached_property
    def vectorizer(self) -> Any:
        import joblib
        from sklearn.exceptions import InconsistentVersionWarning

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
            return joblib.load(
                self._first_existing(["tfidf_vectorizer.pkl", "ang_vectorizer.pkl"])
            )

    @cached_property
    def classifier(self) -> Any:
        import joblib
        from sklearn.exceptions import InconsistentVersionWarning

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
            return joblib.load(
                self._first_existing(["language_classifier.pkl", "ml_lang_model.pkl"])
            )

    def _first_existing(self, names: list[str]) -> Path:
        for name in names:
            path = self.settings.module1_models_dir_local / name
            if path.exists():
                return path
            path = self.settings.module1_models_dir_space / name
            if path.exists():
                return path
        choices = ", ".join(names)
        raise FileNotFoundError(f"Could not find Module 1 model file. Tried: {choices}")

    def detect(self, text: str) -> LanguageResult:
        if not text or not isinstance(text, str):
            return LanguageResult("en", 0.0)

        features = self.vectorizer.transform(
            [re.sub(r"\s+", " ", (text or "").strip().lower())]
        )
        prediction = self.classifier.predict(features)[0]
        language = prediction

        confidence = 0.0
        if hasattr(self.classifier, "predict_proba"):
            probabilities = self.classifier.predict_proba(features)[0]
            confidence = float(np.max(probabilities))

        return LanguageResult(language=language, confidence=confidence)


class EmotionDetector:
    def __init__(self, settings: Settings):
        self.settings = settings

    @cached_property
    def tokenizer(self) -> Any:
        from transformers import AutoTokenizer

        return AutoTokenizer.from_pretrained(str(self.settings.module2_model_dir))

    @cached_property
    def model(self) -> Any:
        import torch
        from transformers import AutoModelForSequenceClassification

        model = AutoModelForSequenceClassification.from_pretrained(
            str(self.settings.module2_model_dir)
        )
        model.to(self.device)
        model.eval()
        return model

    @cached_property
    def device(self) -> Any:
        import torch

        return torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def detect(self, text: str, max_len: int = 128) -> EmotionResult:
        if not text or not isinstance(text, str):
            return EmotionResult("neutral", 0.0, {}, False, "empty")

        if not self.settings.use_local_emotion_model or not has_available_pagefile(
            self.settings.min_available_pagefile_mb
        ):
            return heuristic_emotion(text)

        import torch

        text = re.sub(r"\s+", " ", (text or "").strip().lower())
        encoded = self.tokenizer(
            text,
            max_length=max_len,
            truncation=True,
            padding=True,
            return_tensors="pt",
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}

        with torch.no_grad():
            outputs = self.model(**encoded)
            probabilities = (
                torch.softmax(outputs.logits, dim=1)[0].detach().cpu().numpy()
            )

        emotion_id = int(np.argmax(probabilities))
        emotion = ID2EMOTION.get(emotion_id, "unknown")
        confidence = float(probabilities[emotion_id])
        scores = {
            ID2EMOTION.get(i, f"label_{i}"): float(score)
            for i, score in enumerate(probabilities)
        }
        high_distress = emotion in {"sadness", "anger", "fear"} and confidence > 0.6

        return EmotionResult(
            emotion=emotion,
            confidence=confidence,
            scores=scores,
            high_distress=high_distress,
            source="local_model",
        )


def available_pagefile_mb() -> int | None:
    if sys.platform != "win32":
        return None

    try:
        import ctypes

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(MemoryStatusEx)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullAvailPageFile / (1024 * 1024))
    except Exception:
        return None


def has_available_pagefile(min_mb: int) -> bool:
    available = available_pagefile_mb()
    if available is None:
        return True
    return available >= min_mb


def heuristic_emotion(text: str) -> EmotionResult:
    lowered = re.sub(r"\s+", " ", (text or "").strip().lower())
    buckets = {
        "sadness": [
            "sad",
            "lonely",
            "alone",
            "cry",
            "hopeless",
            "grief",
            "empty",
            "وحدة",
            "وحيد",
            "حزين",
            "حزن",
            "ببكي",
        ],
        "fear": [
            "anxious",
            "anxiety",
            "afraid",
            "fear",
            "panic",
            "worried",
            "قلق",
            "خائف",
            "خوف",
            "هلع",
        ],
        "anger": [
            "angry",
            "mad",
            "furious",
            "rage",
            "غاضب",
            "غضب",
            "متضايق",
        ],
        "joy": ["happy", "good", "better", "فرح", "سعيد"],
        "love": ["love", "loved", "care", "حب"],
        "surprise": ["surprised", "shocked", "مندهش"],
    }

    for emotion, keywords in buckets.items():
        if any(keyword in lowered for keyword in keywords):
            confidence = 0.72
            scores = {label: 0.05 for label in ID2EMOTION.values()}
            scores[emotion] = confidence
            return EmotionResult(
                emotion=emotion,
                confidence=confidence,
                scores=scores,
                high_distress=emotion in {"sadness", "anger", "fear"},
                source="heuristic_memory_safe",
            )

    # Team Note: These are values we picked from our mind
    return EmotionResult(
        emotion="sadness",
        confidence=0.45,
        scores={"sadness": 0.45},
        high_distress=False,
        source="heuristic_memory_safe",
    )


def regex_direct_intent(text: str) -> str | None:
    stripped = re.sub(r"\s+", " ", (text or "").strip().lower())
    if len(stripped.split()) > 4:
        return None

    patterns = {
        "greeting": [
            r"\bhi\b",
            r"\bhello\b",
            r"\bhey\b",
            r"\bgood morning\b",
            r"\bgood evening\b",
            r"\bgood afternoon\b",
            r"\bhowdy\b",
            r"\bgreetings\b",
        ],
        "goodbye": [
            r"\bbye\b",
            r"\bgoodbye\b",
            r"\bfarewell\b",
            r"\bsee you\b",
            r"\btake care\b",
            r"\bgoodnight\b",
        ],
        "gratitude": [
            r"\bthank you\b",
            r"\bthanks\b",
            r"\bthank u\b",
            r"\bgrateful\b",
            r"\bmany thanks\b",
        ],
    }

    for intent, intent_patterns in patterns.items():
        if any(
            re.search(pattern, stripped, flags=re.IGNORECASE)
            for pattern in intent_patterns
        ):
            return intent
    return None


def is_system_identity_question(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not normalized:
        return False

    identity_patterns = [
        r"\bwhat'?s your name\b",
        r"\bwhat is your name\b",
        r"\bwho are you\b",
        r"\byour name\b",
        r"\bsystem name\b",
        r"\bاسمك\b",
        r"\bما اسمك\b",
        r"\bمين انت\b",
        r"\bمن أنت\b",
    ]
    return any(
        re.search(pattern, normalized, flags=re.IGNORECASE)
        for pattern in identity_patterns
    )


def is_followup_affirmation(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not normalized:
        return False

    if len(normalized.split()) > 5:
        return False

    affirmative_patterns = [
        r"^yes$",
        r"^yeah$",
        r"^yep$",
        r"^sure$",
        r"^please$",
        r"^ok(?:ay)?$",
        r"^continue$",
        r"^yes please$",
        r"^i want$",
        r"^i want to$",
        r"^نعم$",
        r"^نعم اريد$",
        r"^نعم أريد$",
        r"^اريد$",
        r"^أريد$",
        r"^ايوا$",
        r"^أيوه$",
        r"^ايوه$",
        r"^اجل$",
        r"^أجل$",
        r"^تمام$",
        r"^اه$",
        r"^آه$",
    ]
    return any(
        re.search(pattern, normalized, flags=re.IGNORECASE)
        for pattern in affirmative_patterns
    )


def is_mental_health_concern(*texts: str) -> bool:
    joined = " ".join(text for text in texts if text)
    normalized = re.sub(r"\s+", " ", joined.strip().lower())
    if not normalized:
        return False

    patterns = [
        r"\bmental health\b",
        r"\bfeel(?:ing|ings)?\b",
        r"\bemotion(?:al|s)?\b",
        r"\bworthless\b",
        r"\bshouldn'?t be here\b",
        r"\bnot want to be here\b",
        r"\bsleep\b",
        r"\binsomnia\b",
        r"\banxious\b",
        r"\banxiety\b",
        r"\bpanic\b",
        r"\bstress(?:ed)?\b",
        r"\bsad(?:ness)?\b",
        r"\bdepress(?:ed|ion)?\b",
        r"\blonely\b",
        r"\bhopeless\b",
        r"\bgrief\b",
        r"\btrauma\b",
        r"\btherapy\b",
        r"\bcounsel(?:ing|ling|or)?\b",
        r"\bcope\b",
        r"\bcoping\b",
        r"\bself[- ]?esteem\b",
        r"\bsuicide\b",
        r"\bsuicidal\b",
        r"\bself[- ]?harm\b",
        r"\bأشعر\b",
        r"\bمشاعر\b",
        r"\bقلق\b",
        r"\bحزين\b",
        r"\bحزن\b",
        r"\bاكتئاب\b",
        r"\bوحيد\b",
        r"\bبلا قيمة\b",
    ]
    return any(re.search(pattern, normalized) for pattern in patterns)


def heuristic_guardrail(user_text: str, generated_response: str) -> dict[str, Any]:
    flags: list[str] = []
    false_attributions = [
        ("you are depressed", "depression"),
        ("you have anxiety", "anxiety"),
        ("you are suicidal", "suicide"),
    ]
    lower_user = re.sub(r"\s+", " ", (user_text or "").strip().lower())
    lower_response = (generated_response or "").lower()

    for phrase, condition in false_attributions:
        if phrase in lower_response and condition not in lower_user:
            flags.append(f"Potential false attribution: {phrase}")

    for claim in ("you are cured", "you will be fine in", "this will definitely solve"):
        if claim in lower_response:
            flags.append(f"Suspicious medical claim: {claim}")

    return {"is_hallucinated": bool(flags), "flags": flags}
