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
| `GEMINI_MODEL` | Gemini model name | `gemini-3.8-flash` |
| `GEMINI_THINKING_BUDGET` | `0`–`8192`; tokens Gemini may spend thinking, on top of the answer limit | `0` (off) |
| `OPENAI_API_KEY` | OpenAI API key | — (required for `openai`) |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `LLM_TIMEOUT_SECONDS` | `0` < value ≤ `120` | `30` |
| `LLM_MAX_ATTEMPTS` | `1`–`5`, including the first try | `3` |
| `EMBEDDING_PROVIDER` | `gemini`, `openai`, `huggingface` (local only), `fake` (`fake` is refused in production) | `gemini` |
| `GEMINI_EMBEDDING_MODEL` | Gemini embedding model | `gemini-embedding-001` |
| `OPENAI_EMBEDDING_MODEL` | OpenAI embedding model | `text-embedding-3-small` |
| `HF_EMBEDDING_MODEL` | Hugging Face model id | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_DIMENSIONS` | `8`–`3072` (Gemini and OpenAI; Hugging Face uses its model's size) | `768` |
| `EMBEDDING_BATCH_SIZE` | `1`–`2048` texts per request (capped per provider) | `100` |
| `EMBEDDING_REQUESTS_PER_MINUTE` | client-side request spacing | `60` |
| `EMBEDDING_TIMEOUT_SECONDS` | `0` < value ≤ `120` | `30` |
| `EMBEDDING_MAX_ATTEMPTS` | `1`–`5`, including the first try | `3` |

## LLM providers

Every LLM call goes through `LLMClient` ([backend/app/llm/client.py](backend/app/llm/client.py)), which checks the input, enforces the timeout, retries transient failures and logs metadata only. To switch providers, change `.env`; no code changes are needed:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

- **Retries:** timeouts, 5xx/connection errors and rate limits are retried with exponential backoff (1s, 2s, 4s…, up to 20s). If a provider asks you to wait longer than 20s (e.g. the free-tier daily quota is used up), the call fails at once with `RateLimitedError` instead of hanging.
- **No retries** for bad keys, invalid requests or malformed replies.
- **Cut-off replies:** if a reply hits `max_output_tokens`, `LLMResponse.truncated` is `True`, and `generate_json` raises a clear "cut off" error.
- **Development without a key:** `LLM_PROVIDER=fake` returns canned replies.

Check that a real provider works (this uses API quota):

```bash
python scripts/llm_smoke.py
```

**Privacy:** on Gemini's free tier, Google may use the content you send to improve its products. Prompts and texts sent for embedding must never include personal details such as names, emails or user IDs. Prompt, response and embedded text are never written to the logs.

## Embeddings

`EmbeddingClient` ([backend/app/embeddings/client.py](backend/app/embeddings/client.py)) turns text into vectors.

- `embed_documents(texts)` embeds course chunks and `embed_query(text)` embeds student questions.
- **Batching and quota:** it splits work into batches, spaces requests to stay under `EMBEDDING_REQUESTS_PER_MINUTE`, and retries like the LLM client.
- **Checks:** every reply must have one vector per text, each of the expected size.
- **Normalisation:** vectors are scaled to unit length, so the dot product equals cosine similarity for every provider.

`client.embedding_id` (e.g. `gemini:gemini-embedding-001:768`) names the vector space. Vectors from different spaces must never be mixed: changing the provider, model or dimensions means re-indexing.

Check that a provider works (Gemini/OpenAI use API quota):

```bash
python scripts/embedding_smoke.py
```

### Local Hugging Face embeddings (optional, offline)

These run entirely on your machine. They need about 1 GB for torch and are never installed in production.

```bash
pip install -r requirements-local.txt
EMBEDDING_PROVIDER=huggingface python scripts/embedding_smoke.py   # first run downloads the model
```

After the first run the model is cached, so it works offline (`HF_HUB_OFFLINE=1`). Hugging Face vectors are 384-dimensional, a different vector space from Gemini/OpenAI, so switching to or from Hugging Face needs a re-index.

## Project layout

```
backend/app/        FastAPI application (package "app")
  main.py           entry point: create_app()
  api/              HTTP routers
  core/             configuration, logging, error handling
  providers/        shared plumbing: errors, retry, rate limiting, SDK clients
  llm/              LLM client and Gemini/OpenAI/fake chat adapters
  embeddings/       embedding client and Gemini/OpenAI/Hugging Face/fake adapters
scripts/            manual smoke tests (llm_smoke.py, embedding_smoke.py)
tests/              mirrors backend/app/
```
