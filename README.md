# Mento Backend - RAG-Based Mental Health Support API

Mento is the backend API for the Serenity mental health support chatbot. It grew
out of a modular NLP project that combined language detection, emotion
classification, intent routing, retrieval augmented generation, and safety
guardrails.

This repository is the production-style backend repo for the MLOps final project.
The frontend is separate, so this repo serves JSON/SSE API endpoints only.

> Slogan: Your Life Matters

## Safety Note

Mento is an educational NLP project. It is not a replacement for licensed mental
health care, medical advice, emergency support, or a crisis line.

If a user expresses direct or immediate self-harm or suicide intent, Mento returns
a deterministic crisis safety response before any generated support. Crisis
responses are localized for English, Arabic, Spanish, French, Hindi, and Chinese.
Other detected languages fall back to English for the crisis safety message.

## Project Background

The original project was built as a modular RAG-based mental health chatbot:

- Module 1: local language detection with TF-IDF and a saved sklearn classifier.
- Module 2: local transformer emotion classifier for sadness, joy, love, anger,
  fear, and surprise.
- Module 3: Groq-powered intent routing, language verification, translation, and
  typo cleanup.
- Module 4: Flask application, LangChain RAG, Qdrant retrieval, guardrails,
  feedback logging, and deployment wiring.

For the MLOps project, this repo keeps the backend pieces needed to power the
provided Serenity frontend through HTTP endpoints.

## Current Backend Updates

This backend repo now includes:

- Flask API endpoints required by the rubric: `POST /chat`, `POST /feedback`,
  and `GET /health`.
- Compatibility endpoints under `/api/...` for streaming, feedback, health, chat
  clearing, and index rebuilds.
- Frontend files removed from this repo. The frontend should live in its own repo.
- A backend info response at `GET /` instead of a rendered HTML page.
- Blank-message handling that returns a warm response instead of an error:

```text
I'm listening, and I'm here whenever you're ready to talk.
```

- Unit tests covering endpoints, core logic, error paths, feedback validation,
  and the blank-message behavior.
- An optimized multi-stage Dockerfile for deployment on port `7860`.
- A manual GitHub Actions workflow that verifies Docker build caching remotely,
  so Docker Desktop and WSL are not required on Windows.

## Architecture

```text
User message
  |
  v
Direct crisis guard
  |-- direct/immediate crisis -> deterministic safety response
  |                            -> crisis-aware support follow-up
  |
  v
Module 1 local language hint
  |
  v
Groq intent router
  - verify/correct language
  - classify intent
  - translate non-English text to English
  - clean English typos and grammar
  |
  |-- greeting/goodbye/gratitude/system identity/out of scope
  |      -> direct response
  |
  v
Module 2 emotion detection or heuristic fallback
  |
  v
Qdrant retrieval with LangChain
  |
  v
Groq RAG answer generation
  - retrieved chunks
  - detected emotion
  - distress flag
  - conversation memory
  - verified language
  |
  v
Heuristic + LLM guardrails
  |
  v
JSON or SSE response to frontend
```

If the local language detector and the Groq router disagree, Mento follows the
Groq verified language.

## Repository Structure

```text
mento-backend/
|-- .github/workflows/docker-cache-check.yml
|-- models/
|   |-- module1/
|   `-- module2/
|-- tests/
|   |-- test_core.py
|   `-- test_endpoints.py
|-- app.py
|-- components.py
|-- feedback_service.py
|-- mento_pipeline.py
|-- prompts.py
|-- rag_service.py
|-- settings.py
|-- validate_module4.py
|-- Dockerfile
|-- .dockerignore
|-- .env.example
|-- pyproject.toml
|-- requirements.txt
`-- README.md
```

## NLP Design Decisions

| Decision | Rationale |
|---|---|
| Local language detection | Fast offline hint with no API cost. |
| Groq language verification | Corrects short or ambiguous local language predictions. |
| One routing call | Intent, language verification, translation, and cleanup happen together to reduce latency. |
| RAG over direct prompting | Grounds answers in counseling-style context instead of relying only on generation. |
| Deterministic crisis response | Safety does not depend on LLM availability. |
| Dual guardrails | Heuristic checks catch obvious issues, while the LLM guardrail handles subtler unsafe responses. |
| Heuristic emotion fallback | Keeps the app usable when the local transformer is disabled or memory is limited. |

## Requirements

- Python 3.12
- Groq API key
- Qdrant Cloud or local Qdrant instance
- Optional LangSmith API key
- Optional Google Apps Script or Google service account for feedback logging

## Setup

Clone the backend repo:

```bash
git clone https://github.com/YOUR_USERNAME/mento-backend.git
cd mento-backend
```

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

With `uv`:

```bash
uv sync --extra dev
```

Copy the environment template:

```bash
copy .env.example .env
```

Fill in the required values:

```env
INTENT_GROQ_API_KEY=gsk_...
RAG_GROQ_API_KEY=gsk_...

QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_key
QDRANT_COLLECTION=Mental-Health
```

Optional fallback:

```env
GROQ_API_KEY=gsk_...
```

Optional memory setting for lighter local runs:

```env
USE_LOCAL_EMOTION_MODEL=false
```

## Run Locally

```bash
python app.py
```

Default local URL:

```text
http://127.0.0.1:5000
```

Health check:

```text
GET http://127.0.0.1:5000/health
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Backend API information |
| `GET` | `/health` | Service status, model config, Qdrant info, feedback config |
| `GET` | `/api/health` | Health alias |
| `POST` | `/chat` | Rubric-required JSON chat endpoint |
| `POST` | `/api/chat/stream` | SSE streaming chat endpoint |
| `POST` | `/api/chat/clear` | Clear server-side session memory |
| `POST` | `/feedback` | Rubric-required feedback endpoint |
| `POST` | `/api/feedback` | Feedback alias |
| `POST` | `/api/index/rebuild` | Rebuild Qdrant vector index |

### POST `/chat`

Request:

```json
{
  "message": "I feel anxious and cannot sleep",
  "session_id": "optional-session-id"
}
```

Response:

```json
{
  "response": "I hear you...",
  "session_id": "optional-session-id",
  "route": "rag_pipeline",
  "emotion": "fear",
  "language": "en"
}
```

Blank messages return a supportive response instead of a validation error:

```json
{
  "response": "I'm listening, and I'm here whenever you're ready to talk.",
  "route": "blank_message",
  "emotion": null,
  "language": "en"
}
```

### POST `/api/chat/stream`

Streams Server-Sent Events:

```json
{
  "message": "I feel anxious",
  "session_id": "demo-session",
  "last_mental_health_topic": ""
}
```

Common event types:

- `session`
- `metadata`
- `token`
- `new_assistant_message`
- `notice`
- `error`
- `done`

### POST `/feedback`

Request:

```json
{
  "query": "I feel anxious",
  "response": "I hear you...",
  "feedback": "like"
}
```

Accepted feedback values:

- `like`
- `thumbs_up`
- `up`
- `dislike`
- `thumbs_down`
- `down`

## Testing

Run the test suite:

```bash
pytest -q
```

With `uv`:

```bash
uv run --extra dev pytest -q
```

Latest local verification:

```text
163 passed
```

Run lint on touched files:

```bash
uv run --extra dev ruff check app.py mento_pipeline.py prompts.py tests/test_endpoints.py
```

## Docker

Build and run locally if Docker is available:

```bash
docker build -t mento-backend .
docker run -p 7860:7860 --env-file .env mento-backend
```

The container listens on:

```text
http://localhost:7860
```

### Docker Optimizations

The Dockerfile is optimized for the containerization rubric:

- Uses `python:3.12-slim`.
- Uses a multi-stage build.
- Installs dependencies before copying application source for better layer reuse.
- Uses a BuildKit pip cache mount.
- Copies only runtime backend files into the final image.
- Excludes frontend files, tests, virtual environments, caches, and heavy model
  weights from the build context.
- Runs as a non-root user.
- Disables the local emotion model by default in the container with
  `USE_LOCAL_EMOTION_MODEL=false`.

## Remote Docker Cache Verification

Docker Desktop and WSL are not required on Windows. This repo includes a manual
GitHub Actions workflow that builds the image twice on GitHub's hosted runner and
prints the cache-hit summary.

Workflow file:

```text
.github/workflows/docker-cache-check.yml
```

Steps:

1. Push this repo to GitHub.
2. Open the repo's **Actions** tab.
3. Select **Docker Cache Verification**.
4. Click **Run workflow**.
5. Open the completed run.
6. Check the **Second build with cache check** step.
7. Screenshot the printed summary for the deliverable.

Expected summary format:

```text
Cached layers: X
Total cacheable layers: Y
Cache hit percentage: Z%
```

The workflow also uploads these files as the `docker-cache-verification` artifact:

- `second-build.log`
- `cache-summary.txt`

## Deployment

The container is configured for platforms that expect the app to listen on
`0.0.0.0:7860`, such as Hugging Face Spaces. It can also be adapted for Railway,
Render, AWS, or another container platform.

Required deployment secrets:

- `INTENT_GROQ_API_KEY`
- `RAG_GROQ_API_KEY`
- `QDRANT_URL`
- `QDRANT_API_KEY`

Optional deployment secrets:

- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `FEEDBACK_APPS_SCRIPT_URL`
- `FEEDBACK_APPS_SCRIPT_SECRET`

Live API URL:

```text
TODO: add deployed backend URL
```

## Frontend Integration

The frontend is a separate Serenity static chat repo. This backend should be used
as the API target for that frontend.

Frontend integration checklist:

1. Fork or use the provided frontend repo.
2. Set the frontend backend URL to the deployed backend API URL.
3. Verify `POST /chat` or `/api/chat/stream`.
4. Verify feedback through `POST /feedback` or `/api/feedback`.
5. Deploy the frontend through GitHub Pages.

## Validation Script

Run local wiring checks:

```bash
python validate_module4.py --router-debug
```

Run optional end-to-end Groq and RAG checks:

```bash
python validate_module4.py --e2e
```

Expected behavior:

- "What is your name?" returns that the assistant is Mento.
- Direct crisis phrases return the deterministic crisis response.
- Negated or historical suicide references do not trigger the direct crisis route.
- Non-English mental health messages are translated to English for retrieval.
- Final responses are returned in the verified user language.
- Short follow-ups such as "yes" or "continue" can continue the previous topic.
- Blank messages return the warm listening response.

## Troubleshooting

### First RAG Query Is Slow

The first query may load the embedding model, connect to Qdrant, download dataset
metadata, or build the vector index. Later runs reuse the Qdrant collection.

### Windows Paging File Is Too Small

The local transformer models can require substantial virtual memory. Close
memory-heavy applications, increase Windows virtual memory, or use:

```env
USE_LOCAL_EMOTION_MODEL=false
```

### Feedback Is Not Saved

Check `/health` and confirm whether Apps Script, Google Sheet, and credential
settings are configured.

### Response Language Looks Wrong

Mento uses the Groq verified language, not only the local Module 1 hint. Use:

```bash
python validate_module4.py --router-debug
```

## Technologies

- Python
- Flask
- Gunicorn
- LangChain
- LangChain Groq
- LangChain Qdrant
- Qdrant
- Hugging Face Datasets
- Sentence Transformers
- Transformers
- PyTorch
- scikit-learn
- Google Apps Script or gspread
- LangSmith
- Docker
- GitHub Actions

## Deliverables Supported By This Repo

- Backend API source code
- Unit tests
- Dockerfile
- Docker cache verification workflow
- Docker cache verification log artifact
- README setup, API, testing, and containerization instructions
