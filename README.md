# ArchintX AI-Powered Intelligent Learning Assistant

A learning assistant for the ArchintX platform. **LearnX** shows the courses with staged lessons, open to everyone for reading. Signed-in students also get **Nexus**, which answers questions from the uploaded course material using retrieval-augmented generation (RAG), with source citations, follow-up questions, and a plain "the course doesn't cover this" when it doesn't; a coding assistant with a remote code runner; AI-graded exercises; and personalised recommendations. Quizzes and other activities stay on the ArchintX platform; the assistant points to them.

| | |
|---|---|
| Live app (Streamlit) | https://ai-powered-intelligent-learning-assistant.streamlit.app/ |
| Live API (FastAPI) | https://archintx-api-kday.onrender.com (Swagger at `/docs`; the first request after idle takes up to a minute) |
| Build plan and decisions | [PLAN.md](PLAN.md) |

## Documentation

| Document | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | components, the RAG pipeline, data, security and privacy, design decisions, limitations, ArchintX integration |
| [docs/api.md](docs/api.md) | every endpoint, who may call it, errors and quotas (Swagger at `/docs` has every field) |
| [docs/evaluation.md](docs/evaluation.md) | datasets, measured results, how to re-run |
| [docs/testing.md](docs/testing.md) | quality checks, test layout, fakes, CI |
| [docs/deployment.md](docs/deployment.md) | Render, Supabase and Streamlit Cloud setup, production launch, demo script |

## Quick start (local)

You need **Python 3.12**, **Git**, and two free accounts:

- **Neon** (https://neon.tech): a free PostgreSQL database. Create a project and copy its **direct** connection string (not the `-pooler` one).
- **Google AI Studio** (https://aistudio.google.com): a free Gemini API key.

**1. Get the code and install:**

```bash
git clone https://github.com/hemanthkumaralwar/AI-powered-intelligent-learning-assistant.git
cd AI-powered-intelligent-learning-assistant
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt -r requirements-dev.txt -r frontend/requirements.txt
```

The first install downloads several hundred MB and can take 10 minutes or more. **Windows:** clone into a short path (e.g. `C:\dev`): some packages have very long file paths, and pip fails with "No such file or directory" past Windows' 260-character limit unless long paths are enabled.

**2. Configure.** Copy `.env.example` to `.env` (`copy` on Windows, `cp` elsewhere), then fill in:

| Key | Value |
|---|---|
| `DATABASE_URL` | the Neon direct connection string, ending in `?sslmode=require` |
| `JWT_SECRET_KEY` | a new random key: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `GEMINI_API_KEY` | your AI Studio key |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | your first admin (password 12+ characters), created when the API starts |

Never commit `.env` (it is gitignored). Every other setting has a working default: see [Configuration](#configuration).

**3. Create the tables:**

```bash
alembic upgrade head
```

**4. Start the API** (leave it running):

```bash
uvicorn app.main:app --app-dir backend --loop asyncio:SelectorEventLoop
```

`--loop asyncio:SelectorEventLoop` is required on Windows (psycopg's async driver cannot use the default loop) and harmless elsewhere. Check http://127.0.0.1:8000/health shows `{"status":"ok"}`; Swagger is at http://127.0.0.1:8000/docs.

**5. Start the frontend** in a second terminal (venv activated): copy `frontend/.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` (it points at the local API), then:

```bash
streamlit run frontend/streamlit_app.py
```

**6. Load the course.** Open http://localhost:8501, log in as your admin, open **Settings** (in the page links at the top), upload `eval/materials/javascript-beginner.json` as JavaScript, and press **Refresh** until it is `ready` (about 5 minutes: 424 chunks embedded at the free tier's pace).

**7. Make a student.** The app has no sign-up form: in Swagger (http://127.0.0.1:8000/docs) use `POST /auth/register` → **Try it out** with a username and password (8+ characters). Log in with it, open a lesson in **LearnX**, ask **Nexus** in its **Ask Nexus** tab ("What is an array in JavaScript?") and run its bug hunt in **Practice**. Without signing in you can still browse the courses and read the lessons.

Without a Gemini key you can still click through with `LLM_PROVIDER=fake`, `EMBEDDING_PROVIDER=fake` and `CODE_RUNNERS=fake` (canned replies; refused in production).

## Switching providers

Every provider is chosen in `.env`; no code changes.

| What | Setting | Options |
|---|---|---|
| Chat model | `LLM_PROVIDER` | `gemini` (default, `GEMINI_MODEL=gemini-3.5-flash-lite`), `openai` (`OPENAI_API_KEY`, `OPENAI_MODEL=gpt-4o-mini`), `fake` |
| Embeddings | `EMBEDDING_PROVIDER` | `gemini` (default, `gemini-embedding-001`), `openai` (`text-embedding-3-small`), `huggingface` (local, offline), `fake` |
| Code runners | `CODE_RUNNERS` | `judge0,godbolt` (default: Judge0 CE, then Compiler Explorer as fallback), `fake` |

- **Changing the embedding provider, model or dimensions** creates a new vector space: re-index with `POST /admin/reindex` (or **Re-index** in Settings). Vectors from different spaces are never mixed.
- **Local Hugging Face embeddings** (about 1 GB for torch; never installed in production):

  ```bash
  pip install -r requirements-local.txt
  ```

  then set `EMBEDDING_PROVIDER=huggingface`. The first run downloads `BAAI/bge-small-en-v1.5` (384 dimensions); after that it works offline (`HF_HUB_OFFLINE=1`).
- **Check a provider works** (uses quota): `python scripts/llm_smoke.py`, `python scripts/embedding_smoke.py`, `python scripts/code_runner_smoke.py`.
- **Retries and limits:** timeouts, 5xx and rate limits are retried with backoff (1, 2, 4… s, up to 20 s); bad keys and invalid requests are not. Embeddings are paced to the free tier (80 indexing + 20 question texts a minute, separate budgets).
- **Privacy:** on Gemini's free tier, Google may use what you send to improve its products. Prompts never include personal details; prompts, answers and code are never logged.

## Database

| Environment | Database | URL to use |
|---|---|---|
| Development | Neon branch `dev` | **direct** connection string (not `-pooler`), `?sslmode=require` |
| Tests / CI | Neon branch `test` (`TEST_DATABASE_URL`) | direct; each test run creates and drops its own `test_<random>` schema |
| Production | Supabase | **session pooler** (port 5432 on `pooler.supabase.com`; works over IPv4 from Render) |

Avoid transaction poolers (Neon `-pooler`, Supabase port 6543): migrations and per-session settings need a real session.

```bash
alembic upgrade head          # migrate the database in DATABASE_URL
alembic upgrade head --sql    # print the SQL without connecting, for review
alembic downgrade -1          # undo the last migration
```

Render runs `alembic upgrade head` on every deploy. Every table has Row Level Security enabled with no policies, so Supabase's public `anon` key reads nothing; turning off Supabase's Data API as well is recommended.

## Deployment

Render (API), Supabase (database) and Streamlit Community Cloud (frontend), all free, no Docker: see **[docs/deployment.md](docs/deployment.md)**.

## Quality checks

```bash
ruff check .
ruff format --check .
pytest
pip-audit -r requirements.txt -r requirements-dev.txt -r frontend/requirements.txt
```

`pytest` fails if coverage drops below 80%; database tests are skipped without `TEST_DATABASE_URL`. GitHub Actions runs all four on every push. Details: [docs/testing.md](docs/testing.md).

## Using the app

The frontend follows the LearnX platform's look: page links at the top, a top bar with the page title and a profile menu (explanation level, log out), an open lesson's course outline in a sidebar you can hide (its module's lessons, marked done or started), previous/next arrows beside the lesson title, and LearnX colours in light and dark (switch at the top of Streamlit's ⋮ menu).

| Page | For | What it does |
|---|---|---|
| **LearnX** | everyone; no account needed to read | courses → a course's modules → a lesson with **Reading** (numbered stages: mission, brief, concepts, analogy, syntax, examples, flow, real world, recap) and **Quiz & activities** (links to the platform), open to all. Signed in, you also get **Ask Nexus** (the course assistant: answers with citations, follow-ups, a **Past chats** panel you can hide and, where an admin turned it on, **Open in Practice**), **Practice** (the lesson's exercises in a code editor: run, ask the AI about the output, submit for grading), **Code** (explain code, show an example, practice questions), and on the course page your mastery, lessons **due for review** and **what to do next** |
| **Sign in** | guests | the login form (accounts are created through the API for now) |
| **Settings** (`<app URL>/admin`) | admins only | upload course JSON, indexing status, per-course feature switches (Open in Practice, spaced review; off by default), delete a course, re-index |

- **Code runs remotely,** never on the server: Judge0 CE, with Compiler Explorer as fallback (and **Open in Compiler Explorer** for a public share link). JavaScript that uses the page (`document`, `window`) runs in a locked-down iframe in your browser.
- **Answers stay on the platform:** students never receive quiz answers or exercise solutions; the assistant gives hints for exercises.
- **Reloading the browser signs you out:** the token lives only in Streamlit's server-side session, never in the browser.

## Configuration

All settings come from environment variables or `.env`. `.env.example` lists every key. Never commit `.env`.

| Variable | Values | Default |
|---|---|---|
| `APP_NAME` | any string | `ArchintX Learning Assistant` |
| `ENVIRONMENT` | `development`, `test`, `production` | `development` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| `LLM_PROVIDER` | `gemini`, `openai`, `fake` (`fake` is refused in production) | `gemini` |
| `GEMINI_API_KEY` | key from https://aistudio.google.com | — (required for `gemini`) |
| `GEMINI_MODEL` | Gemini model name | `gemini-3.5-flash-lite` |
| `GEMINI_THINKING_BUDGET` | `default` sends no thinking setting (required by `-lite` models). `0`–`8192`: tokens a thinking model (e.g. `gemini-3.8-flash`) may spend thinking, on top of the answer limit; `0` turns thinking off | `default` |
| `OPENAI_API_KEY` | OpenAI API key | — (required for `openai`) |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `LLM_TIMEOUT_SECONDS` | `0` < value ≤ `120` | `30` |
| `LLM_MAX_ATTEMPTS` | `1`–`5`, including the first try | `3` |
| `RAG_TOP_K` | `1`–`20`; course chunks given to the model per question | `5` |
| `RAG_MIN_SCORE` | `0`–`1`; below this similarity the assistant says the course does not cover it (measured for `gemini-embedding-001`; re-measure after changing the embedding model) | `0.63` |
| `CHAT_QUESTIONS_PER_USER_PER_MINUTE` | per-student question quota | `5` |
| `CHAT_QUESTIONS_GLOBAL_PER_MINUTE` | whole-app question quota (protects the shared free tier) | `20` |
| `WEAK_MASTERY_THRESHOLD` | `0` < value ≤ `1`; lessons below it are recommended for review | `0.6` |
| `LOGIN_FAILURES_PER_USERNAME` | wrong passwords per username in 15 minutes before that account's sign-in is paused | `5` |
| `LOGINS_PER_MINUTE` | whole-app sign-in attempts per minute | `60` |
| `REGISTRATIONS_PER_MINUTE` | whole-app new accounts per minute | `20` |
| `GUEST_REQUESTS_PER_MINUTE` | requests per minute to the public course endpoints from all visitors without a valid token, together (they all come through the Streamlit server) | `120` |
| `CHAT_RETENTION_DAYS` | chats untouched this long are deleted (when their owner next lists chats) | `90` |
| `CONTENT_CACHE_SECONDS` | how long course and lesson responses are cached; `0` turns caching off. Admin uploads and deletes clear the cache | `600` |
| `PLATFORM_LESSON_URL` | `https://` link template to a lesson on the learning platform, containing `{lesson_id}`; adds the link to the `practice` pointers in API responses (the app itself lists a lesson's activities only in its Quiz & activities tab) | — (no links) |
| `DATABASE_URL` | PostgreSQL URL: Neon direct (dev) or Supabase session pooler (prod) | — (required by the API from Step 5) |
| `TEST_DATABASE_URL` | Neon `test` branch URL, read only by the test suite | — (database tests skip without it) |
| `DB_POOL_SIZE` | `1`–`20` | `5` |
| `DB_CONNECT_TIMEOUT_SECONDS` | `1`–`60` | `10` |
| `JWT_SECRET_KEY` | 32+ random characters; signs access tokens | — (required by the API) |
| `ACCESS_TOKEN_MINUTES` | `5`–`1440` | `60` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | first admin, created at startup if absent (password 12+ chars); set both or neither | — |
| `CODE_RUNNERS` | comma-separated, tried in order: `judge0`, `godbolt`, `fake` (refused in production) | `judge0,godbolt` |
| `JUDGE0_BASE_URL` / `GODBOLT_BASE_URL` | runner service URLs | `https://ce.judge0.com` / `https://godbolt.org` |
| `CODE_RUNNER_TIMEOUT_SECONDS` | wait for the runner service | `30` |
| `CODE_CPU_SECONDS` / `CODE_WALL_SECONDS` | per-program limits (Judge0) | `5` / `10` |
| `CODE_RUNS_PER_USER_PER_MINUTE` / `CODE_RUNS_PER_USER_PER_DAY` | per-student quota | `10` / `200` |
| `CODE_RUNS_GLOBAL_PER_MINUTE` | whole-app quota (protects the shared free allowance) | `30` |
| `EMBEDDING_PROVIDER` | `gemini`, `openai`, `huggingface` (local only), `fake` (`fake` is refused in production) | `gemini` |
| `GEMINI_EMBEDDING_MODEL` | Gemini embedding model | `gemini-embedding-001` |
| `OPENAI_EMBEDDING_MODEL` | OpenAI embedding model | `text-embedding-3-small` |
| `HF_EMBEDDING_MODEL` | Hugging Face model id | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_DIMENSIONS` | `8`–`3072` (Gemini and OpenAI; Hugging Face uses its model's size) | `768` |
| `EMBEDDING_BATCH_SIZE` | texts per request; must not exceed the document budget | `40` |
| `EMBEDDING_DOCUMENT_TEXTS_PER_MINUTE` | texts per minute for indexing | `80` |
| `EMBEDDING_QUERY_TEXTS_PER_MINUTE` | texts per minute for student questions (own budget) | `20` |
| `EMBEDDING_TIMEOUT_SECONDS` | `0` < value ≤ `120` | `30` |
| `EMBEDDING_MAX_ATTEMPTS` | `1`–`5`, including the first try | `3` |

## Deliverables

| Grading area | Where |
|---|---|
| RAG implementation (20) | [architecture.md › Asking a question](docs/architecture.md#asking-a-question), [› Course ingestion](docs/architecture.md#course-ingestion); `backend/app/{rag,ingestion,indexing}/`; results in [evaluation.md](docs/evaluation.md) |
| Python and backend (15) | `backend/app/`; [docs/api.md](docs/api.md); Swagger at `/docs` (live: https://archintx-api-kday.onrender.com/docs) |
| LLM integration (15) | `backend/app/{llm,providers}/`; [Switching providers](#switching-providers); grounding and citation rules in [architecture.md](docs/architecture.md#asking-a-question) |
| Coding assistant (15) | `backend/app/{coding,runner}/`, `frontend/components/compiler.py`; [api.md › Coding assistant](docs/api.md#coding-assistant); 18/18 bugs found ([evaluation.md](docs/evaluation.md#coding-assistant)) |
| Vector database (10) | `backend/app/vectorstore/` (FAISS) + vectors in Postgres (`chunks`); why FAISS: [architecture.md › Design decisions](docs/architecture.md#design-decisions-changes-from-the-brief) |
| Personalization (10) | `backend/app/learning/` (mastery, recommendations, AI grading), explanation levels (`backend/app/llm/prompt_levels.py`); [architecture.md › Progress](docs/architecture.md#progress-and-recommendations) |
| Testing and documentation (10) | `tests/` (98% coverage), [docs/testing.md](docs/testing.md), CI in `.github/workflows/ci.yml`; this README and `docs/` |
| Final demonstration (5) | live app (above); demo script in [deployment.md › Backup recording](docs/deployment.md#backup-recording); **backup recording: pending (maintainer)** |
| Evaluation results | [docs/evaluation.md](docs/evaluation.md), reports in `eval/reports/`; **production report (`eval/reports/production.md`): pending (maintainer)** |

## Project layout

```
backend/app/        FastAPI application (package "app"); entry point main.py: create_app()
  api/              HTTP routers, request dependencies (deps.py), schemas/
  auth/             password hashing, tokens, accounts, admin seeding, sign-in limits
  ingestion/        upload checks, course JSON parsing (+ the generator's course_schema.json), chunking
  indexing/         background indexing worker and startup rebuild (quota-aware)
  vectorstore/      in-memory FAISS index, one per course
  rag/              grounded answers: follow-up rewriting, retriever, prompt, citation checks
  chat/             chat sessions: ownership, history window, retention
  coding/           coding assistant: prompts, output schemas, exercise matching
  learning/         practice pointers, AI grading of exercise attempts, progress, recommendations
  runner/           code runners (Judge0, Compiler Explorer, fake), fallback, quotas
  llm/, embeddings/ provider-neutral clients and Gemini / OpenAI / Hugging Face / fake adapters
  providers/        shared plumbing: errors, retries, rate limiting
  core/             settings, logging, error handling, body-size limit, quotas, cache
  db/               models, engine and sessions, repositories
  evaluation/       evaluation datasets, metrics and reports (used by eval/)
backend/migrations/ Alembic migrations (config: alembic.ini at the repository root)
frontend/           Streamlit app (streamlit_app.py) and its API client (api_client.py)
  views/            pages in the top navigation: learnx, sign_in, admin_courses (Settings)
  components/       shell (top bar), account, course outline, lesson reading stages, compiler panel,
                    coding helper, progress, practice, DOM sandbox
  menu.py           which pages each role sees; session.py: client, token and user for pages
eval/               evaluation datasets, scripts (run_eval, run_code_eval, run_level_demo,
                    run_live_eval) and reports/; materials/: the JavaScript course
docs/               architecture, API, evaluation, testing, deployment
scripts/            manual smoke tests (LLM, embeddings, code runner), practice backfill
tests/              mirrors backend/app/, plus frontend/ and docs/
render.yaml         Render blueprint for the API
.streamlit/         Streamlit config (theme, no usage statistics)
```
