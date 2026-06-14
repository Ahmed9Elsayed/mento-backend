# Mento — Mental Health Support Backend

> **"Your Life Matters"** — A RAG-based multilingual mental health support chatbot.

Mento is the backend API powering the **Serenity** chat interface. It combines local ML models, a fine-tuned emotion classifier, and a Retrieval-Augmented Generation (RAG) pipeline to deliver empathetic, grounded, and safe responses in 20 languages.

---

## Architecture Overview

Every user message passes through a layered pipeline:

```
User Message
    │
    ▼
[Layer 0] Crisis Detection      — Regex/phrase match in 6 languages. Hardcoded safety response. Zero API cost.
    │
    ▼
[Module 1] Language Detection   — TF-IDF + sklearn classifier. Local, offline, milliseconds.
    │
    ▼
[Module 3] Intent Router        — Single Groq LLM call (Llama 3.3 70B): verify language,
                                  classify intent, translate to English, clean typos.
    │
    ├── Direct Route ──────────► greeting / goodbye / gratitude / identity / out-of-scope
    │
    └── RAG Pipeline ──────────► [Module 2] Emotion Detection (local transformer)
                                      │
                                      ▼
                                 Qdrant vector retrieval (top-k counseling chunks)
                                      │
                                      ▼
                                 Groq RAG answer generation
                                      │
                                      ▼
                                 Dual Guardrails (heuristic + LLM post-check)
                                      │
                                      ▼
                                 SSE streamed response → user
```

---

## NLP Design Decisions

| Decision | Rationale |
|---|---|
| **TF-IDF for language detection** | Milliseconds, zero GPU, no API cost. Language patterns are distinctive at character n-gram level. |
| **Fine-tuned transformer for emotion** | General LLMs are unreliable on mental health vocabulary. Fine-tuning on counseling data captures distress signals. Runs locally — no user data sent externally. |
| **Single 4-in-1 Groq call for intent** | One prompt handles: language verify + intent classify + English translate + typo clean. Minimises latency and cost. |
| **RAG over direct prompting** | Grounds responses in real counselor conversations from the Amod/mental_health_counseling_conversations dataset. Reduces hallucination. |
| **Dual guardrails** | Heuristic regex catches obvious unsafe patterns cheaply. LLM post-check handles subtle hallucinations. Both must pass before response reaches the user. |
| **Module 1 output = hint only** | Short ambiguous words (e.g. "Hi") are misclassified. The intent LLM always has final authority on language. |
| **Hardcoded crisis response** | Safety cannot depend on LLM availability or correctness. Crisis phrases trigger an immediate, deterministic response with real helpline links. |

---

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- A [Groq API key](https://console.groq.com)
- A [Qdrant](https://qdrant.tech) cluster (cloud free tier works)

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/mento-backend.git
cd mento-backend
```

> **Note:** Model files are stored with Git LFS. Make sure `git lfs install` has been run before cloning, or run `git lfs pull` after cloning.

### 2. Install dependencies

```bash
# With uv (recommended)
uv sync

# Or with pip
pip install -r requirements.txt
```

### 3. Configure environment

Copy the example and fill in your keys:

```bash
cp .env.example .env
```

Required variables:

```env
# Groq (can use same key for both, or separate for different rate-limit pools)
INTENT_GROQ_API_KEY=gsk_...
RAG_GROQ_API_KEY=gsk_...

# Qdrant
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_key
QDRANT_COLLECTION=Mental-Health
```

Optional:

```env
# LangSmith tracing
LANGSMITH_API_KEY=ls__...
LANGSMITH_PROJECT=Mento

# Google Sheets feedback logging
FEEDBACK_APPS_SCRIPT_URL=https://script.google.com/macros/s/.../exec

# Force a fresh Qdrant index build on startup
BUILD_INDEX_ON_STARTUP=true
```

### 4. Run

```bash
python app.py
```

The API starts on `http://0.0.0.0:5000`.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Chat web interface (HTML) |
| `GET` | `/api/health` | Service status, model config, Qdrant info, feedback config |
| `POST` | `/api/chat/stream` | Main chat — returns SSE stream of tokens |
| `POST` | `/api/chat/clear` | Clears conversation memory for a session |
| `POST` | `/api/feedback` | Logs thumbs up/down to Google Sheets or Apps Script |
| `POST` | `/api/index/rebuild` | Rebuilds the Qdrant vector index |

### POST `/api/chat/stream`

```json
{ "message": "I feel very anxious", "session_id": "optional-uuid" }
```

Returns an SSE stream of events: `session` → `metadata` → `token` × N → `done`

### POST `/api/feedback`

```json
{ "query": "user message", "response": "mento response", "feedback": "like" }
```

Accepted feedback values: `like`, `thumbs_up`, `up`, `dislike`, `thumbs_down`, `down`

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Docker

```bash
docker build -t mento-backend .
docker run -p 5000:5000 --env-file .env mento-backend
```

---

## Monitoring Metrics

Mento is instrumented with OpenTelemetry and exports metrics to Axiom:

| Metric | Category | Rationale |
|---|---|---|
| `mento.intent.distribution` | NLP/Model | Tracks which intents are most common — detects drift if mental_health questions drop |
| `mento.feedback.vote_ratio` | Data | Like/dislike ratio over time — direct signal of response quality |
| `mento.request.count` + `mento.request.error_rate` | Server | Standard health indicators for uptime and reliability monitoring |

---

## Deployment

Live API: **[TODO: add your deployed URL]**

Deployed on [Railway / Hugging Face Spaces / Render — TODO].
