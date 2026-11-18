# ArchintX AI-Powered Intelligent Learning Assistant

A RAG-based learning assistant for the ArchintX platform. It answers questions from uploaded course material with source citations, and includes a coding assistant, quizzes and personalized lesson recommendations.

See [PLAN.md](PLAN.md) for the build plan. This README grows with each step.

## Requirements

- Python 3.12
- Git

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

## Run the API

```bash
uvicorn app.main:app --app-dir backend --reload
```

- Health check: http://127.0.0.1:8000/health
- Interactive API docs: http://127.0.0.1:8000/docs

## Quality checks

```bash
ruff check .
ruff format --check .
pytest
pip-audit -r requirements.txt -r requirements-dev.txt
```

`pytest` fails if coverage drops below 80%. GitHub Actions runs all four checks on every push and pull request.

## Configuration

All settings come from environment variables or `.env`. `.env.example` lists every key. Never commit `.env`.

| Variable | Values | Default |
|---|---|---|
| `APP_NAME` | any string | `ArchintX Learning Assistant` |
| `ENVIRONMENT` | `development`, `test`, `production` | `development` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| `LLM_PROVIDER` | `gemini`, `openai`, `fake` (`fake` is refused in production) | `gemini` |
| `GEMINI_API_KEY` | key from https://aistudio.google.com | — (required for `gemini`) |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.5-flash` |
| `OPENAI_API_KEY` | OpenAI API key | — (required for `openai`) |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `LLM_TIMEOUT_SECONDS` | `0` < value ≤ `120` | `30` |
| `LLM_MAX_ATTEMPTS` | `1`–`5`, including the first try | `3` |

## LLM providers

Every LLM call goes through `LLMClient` ([backend/app/llm/client.py](backend/app/llm/client.py)), which checks the input, enforces the timeout, retries transient failures and logs metadata only. To switch providers, change `.env`; no code changes are needed:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

- **Retries:** timeouts, 5xx/connection errors and rate limits are retried with exponential backoff (1s, 2s, 4s…, up to 20s). If a provider asks you to wait longer than 20s (e.g. the free-tier daily quota is used up), the call fails at once with `RateLimitedError` instead of hanging.
- **No retries** for bad keys, invalid requests or malformed replies.
- **Development without a key:** `LLM_PROVIDER=fake` returns canned replies.

Check that a real provider works (this uses API quota):

```bash
python scripts/llm_smoke.py
```

**Privacy:** on Gemini's free tier, Google may use the content you send to improve its products. Prompts must never include personal details such as names, emails or user IDs. Prompt and response text are never written to the logs.

## Project layout

```
backend/app/        FastAPI application (package "app")
  main.py           entry point: create_app()
  api/              HTTP routers
  core/             configuration, logging, error handling
  llm/              LLM client, retry policy, Gemini/OpenAI/fake adapters
scripts/            manual tools (e.g. llm_smoke.py)
tests/              mirrors backend/app/
```
