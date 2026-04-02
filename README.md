# CallCenter Compliance AI

Multilingual call center compliance analytics — AI-powered transcription, SOP scoring, payment categorization, and rejection analysis.

## Quick Start (Local)

```bash
pip install -r requirements.txt
# Set API keys in .env
# Start Redis: docker run -d -p 6379:6379 redis:alpine
# Start Celery: celery -A celery_worker.celery_app worker --loglevel=info --pool=solo
# Start API: python main.py
# Open: http://localhost:8000
```

## Railway Deployment

1. Push to GitHub
2. Create new project on [Railway](https://railway.app)
3. Add **Redis** service (click + New → Redis)
4. Add **Web** service from your GitHub repo
5. Set environment variables:
   - `SARVAM_API_KEY` — your Sarvam AI key
   - `LLM_API_KEY` — your Cerebras key (free at https://cloud.cerebras.ai)
   - `LLM_BASE_URL` — `https://api.cerebras.ai/v1`
   - `LLM_MODEL` — `llama-3.1-8b`
   - `REDIS_URL` — auto-set by Railway Redis addon (use `${{Redis.REDIS_URL}}`)
   - `DATABASE_URL` — `sqlite:///./callcenter.db`
6. Set start command: `bash start.sh`
7. Deploy!

## LLM Provider

Uses **Cerebras** free tier (OpenAI-compatible API) with `llama-3.1-8b`. No credit card required.
Get your free key at: https://cloud.cerebras.ai
