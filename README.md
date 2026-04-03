# CallCenter Compliance AI

Multilingual call center compliance analytics platform with AI-powered transcription, SOP scoring, payment categorization, and rejection analysis for Hindi and Tamil.

---

## Setup Instructions

**Prerequisites:** Python 3.11+, Redis, FFmpeg, Sarvam AI and Cerebras API keys.

```bash
# Clone and install
git clone https://github.com/Manthann-0/Call-center-compliance.git
cd Call-center-compliance
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Install FFmpeg
sudo apt install ffmpeg          # Linux
brew install ffmpeg              # Mac
# Windows: download from https://ffmpeg.org and add to PATH

# Start Redis
docker run -d -p 6379:6379 redis:alpine
```

Create a `.env` file:

```env
API_KEY=sk_track3_987654321
SARVAM_API_KEY=your_sarvam_api_key
LLM_API_KEY=your_cerebras_api_key
LLM_BASE_URL=https://api.cerebras.ai/v1
LLM_MODEL=llama-3.1-8b
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite:///./callcenter.db
```

```bash
# Start Celery worker
celery -A celery_worker.celery_app worker --loglevel=info --pool=solo

# Start server (new terminal)
python main.py
```

App runs at `http://localhost:8000` · API docs at `/docs`

---

## Architecture Overview

```
Client (Dashboard / API)
        │
        ▼
  FastAPI Application  (auth, routing, schemas)
        │
        ▼
   Service Layer
   ├── Audio Processor  (FFmpeg)
   ├── STT Transcriber  (Sarvam AI)
   ├── LLM Analyzer     (Cerebras)
   └── SOP Validator
        │
        ▼
   Data Layer
   ├── SQLite / PostgreSQL  (call records)
   ├── Redis                (Celery task queue)
   └── ChromaDB             (vector search)
```

**Processing pipeline:** Audio upload → FFmpeg preprocessing → Sarvam STT → Cerebras LLM analysis → SOP validation → DB storage → JSON response.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Uvicorn, Python 3.11+ |
| Task Queue | Celery + Redis |
| Database | SQLAlchemy, SQLite / PostgreSQL |
| Vector Search | ChromaDB |
| Audio | FFmpeg, Pydub |
| Frontend | Vanilla JS, Chart.js, HTML/CSS |
| Deployment | Railway / Render |

---

## AI Tools Used

- **Sarvam AI – Saaras v3:** Speech-to-text transcription and translation for Hindi and Tamil.
- **Cerebras – Llama 3.1-8B:** LLM for compliance scoring, sentiment analysis, payment categorization, and keyword extraction. Runs on Cerebras CS-2 hardware for fast inference.
- **ChromaDB:** Semantic search and indexing of call transcripts using vector embeddings.
- **Amazon Q Developer:** Used for code assistance during development.
- **Claude Sonnet4.6:** Used for code assistance during development.
---

## Known Limitations

- **Processing time:** Each call takes 20–30 seconds (STT batch processing is the main bottleneck). May exceed timeouts on some platforms.
- **Language support:** Only Hindi and Tamil. Code-mixed speech (Hinglish/Tanglish) may reduce accuracy.
- **Audio quality:** Heavy background noise affects transcription. Calls over 1 hour may timeout.
- **Rate limits:** Subject to Sarvam AI and Cerebras free-tier API caps.
- **Storage:** SQLite is not suitable for high-concurrency production — use PostgreSQL instead.
- **Security:** Transcripts are stored in plain text; no PII redaction or data retention policy by default.