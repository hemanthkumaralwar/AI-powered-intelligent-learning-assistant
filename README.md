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
pip install -r requirements.txt -r requirements-dev.txt -r frontend/requirements.txt
cp .env.example .env
```

## Run the API

```bash
uvicorn app.main:app --app-dir backend --reload --loop asyncio:SelectorEventLoop
```

`--loop asyncio:SelectorEventLoop` is required on Windows: uvicorn otherwise uses the ProactorEventLoop, which psycopg's async driver cannot use. It is harmless on Linux. The API refuses to start without `DATABASE_URL` and `JWT_SECRET_KEY`.

- Health check: http://127.0.0.1:8000/health
- Interactive API docs: http://127.0.0.1:8000/docs

## Run the frontend

```bash
API_BASE_URL=http://127.0.0.1:8000 streamlit run frontend/streamlit_app.py
```

Or copy `frontend/.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`. The frontend only needs `API_BASE_URL`; it must be `https://` except for localhost. The access token stays in Streamlit's server-side session state, never in browser storage. `.streamlit/config.toml` turns off Streamlit's usage statistics.

After login, **Practice** lets a student pick a course, lesson and exercise, and opens the **compiler panel** (`frontend/components/compiler.py`) with that exercise's starter code:

- **Run** on the remote sandbox (Step 7), with stdin; **Open in Compiler Explorer** (C, C++, Java, Python) creates a *public* link.
- **Ask AI about this output** sends the code and its last run (or output pasted from a run elsewhere) to `/coding/debug`. Course exercises get hints, not the answer.
- **Page sandbox** for JavaScript that uses `document`/`window`: runs in the student's browser in an iframe with `sandbox="allow-scripts"` only (no access to this site's page, cookies or storage) and a CSP that blocks all network requests. Elements the code looks up (`.output`, `#save`...) are created automatically; optional "Page HTML" adds markup.

The editor is a plain text area: `streamlit-ace` was last released in 2021, and a plain widget adds no third-party JavaScript. Full lesson pages arrive in Step 19.

## Deployment

Render (API), Supabase (database) and Streamlit Community Cloud (frontend), all free, no Docker: see **[docs/deployment.md](docs/deployment.md)**.

## Quality checks

```bash
ruff check .
ruff format --check .
pytest
pip-audit -r requirements.txt -r requirements-dev.txt -r frontend/requirements.txt
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
| `PLATFORM_LESSON_URL` | `https://` link template to a lesson on the learning platform, containing `{lesson_id}`; makes practice pointers clickable | — (no links) |
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
| `CODE_RUNS_PER_USER_PER_MINUTE` / `_PER_DAY` | per-student quota | `10` / `200` |
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
- **Batching and quota:** it splits work into batches and spaces them so that **texts** per minute stay under budget. Gemini's free tier counts every text in a batch as one request: about 100 a minute and about 1,000 a day per project. Indexing and student questions have separate budgets (80 + 20 a minute), so a question never waits behind an indexing batch. It retries like the LLM client.
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

## Database

PostgreSQL through SQLAlchemy 2 (async, psycopg 3), with migrations managed by Alembic.

| Environment | Database | URL to use |
|---|---|---|
| Development | Neon branch `dev` | **direct** connection string (not `-pooler`), `?sslmode=require` |
| Tests / CI | Neon branch `test` | direct; each test run creates and drops its own `test_<random>` schema |
| Production | Supabase | **session pooler** (port 5432 on `pooler.supabase.com`; works over IPv4 from Render) |

Avoid transaction poolers (Neon `-pooler`, Supabase port 6543): migrations and per-session settings need a real session.

```bash
alembic upgrade head          # migrate the database in DATABASE_URL
alembic upgrade head --sql    # print the SQL without connecting, for review
alembic downgrade -1          # undo the last migration
```

Migrate production once, from your own terminal, with the Supabase URL set only for that command:

```bash
DATABASE_URL='postgresql://...pooler.supabase.com:5432/postgres?sslmode=require' alembic upgrade head
```

**Supabase security:** Supabase publishes tables in `public` through its REST Data API. The first migration enables Row Level Security on every table with no policies, so the public `anon` key can read nothing. Turning the Data API off as well (Supabase → Settings → Data API) is recommended, since the app never uses it.

**CI:** database tests run in GitHub Actions only once the `TEST_DATABASE_URL` repository secret exists:

```bash
gh secret set TEST_DATABASE_URL
```

Uploaded originals are stored in Postgres (`document_files`, `bytea`, at most 10 MB each), separately from `documents`, so listing documents never loads file contents.

## Authentication

| Endpoint | Who | What |
|---|---|---|
| `POST /auth/register` | anyone | creates a **student** account (`username`: 3–50 chars of `a-z 0-9 . _ -`, case-insensitive; `password`: 8–128 chars) |
| `POST /auth/login` | anyone | returns `{"access_token", "token_type": "bearer", "expires_in"}` |
| `GET /auth/me` | logged in | the current account (`id`, `username`, `role`, `level`) |
| `PATCH /auth/me` | logged in | `{"level": "beginner" \| "intermediate" \| "advanced"}` sets your explanation level; any other field is a 422 |

Send the token as `Authorization: Bearer <token>`. In Swagger (`/docs`), use **Authorize**.

- **Passwords** are hashed with Argon2id and are never logged or echoed. Validation errors return only where and why, never the submitted value or its length.
- **Tokens** are HS256 JWTs carrying only the user id, valid for `ACCESS_TOKEN_MINUTES`. The role is read from the database on every request, so role changes and deleted accounts take effect immediately.
- **Login failures** return the same `401 Invalid username or password` whether the username or the password was wrong.
- **Admins:** the API cannot create admins; only `ADMIN_USERNAME` / `ADMIN_PASSWORD` can, at startup. Seeding never changes an existing account. After the first production deploy you can remove `ADMIN_PASSWORD` from Render.
- **Route protection:** `CurrentUser` (any logged-in user) and `AdminUser` (admins only) in `app/api/deps.py`.
- **Explanation level:** every account starts as `beginner`. Chat answers and the coding assistant adapt depth, vocabulary and length to it; each request can override it with its own `level`. The level never relaxes a rule (grounding, citations, refusals, hints-only for exercises): its guidance is added after the rules and says so. Shared wording: `app/llm/prompt_levels.py`.
- **CORS** is deliberately off: the Streamlit frontend calls the API from its own server, so browsers never need cross-origin access.

## Course materials

Courses are uploaded as **course JSON only**, by admins. Other material (DOCX, PDF, TXT) is converted to course JSON outside this app, e.g. next to the course generator, so every course follows the same schema.

| Endpoint | Who | What |
|---|---|---|
| `POST /admin/documents` | admin | multipart `file` (`.json`) + form field `language` (`c`, `cpp`, `java`, `python`, `javascript`, `sql`) |
| `GET /admin/documents?course_id=` | admin | uploaded course files, newest first |
| `GET /admin/documents/{id}/download` | admin | the original file (includes all answers) |
| `DELETE /admin/documents/{id}` | admin | delete one uploaded file |
| `DELETE /admin/courses/{id}` | admin | delete a course **and everything attached to it** |
| `GET /courses`, `GET /courses/{id}` | logged in | course list; module/lesson outline |
| `GET /lessons/{id}` | logged in | teaching content and exercises (starter code, hints), no solutions |

- **What an upload creates:** the course with its modules, lessons, 10 quiz questions per lesson and 3 exercises per lesson, all in one transaction.
- **Checks:** the file is validated against `backend/app/ingestion/course_schema.json` (the course generator's schema) plus stricter rules: id format `a-z 0-9 -`, unique ids, and every quiz answer must point at one of its options.
- **Re-uploading** an existing course returns **409**. Delete the course first.
- **Limits:** **10 MB** per file (413), enforced before the body is parsed. Every other endpoint accepts at most 64 KB. Any other file type → 415 "Convert other material to course JSON first".

**Answers stay hidden:** students never receive quiz answers, bug-hunt fixes or exercise solutions. The original course JSON is admin-only, and the student response models have no fields for answers. **Rendering rule:** course text is stored as uploaded, so any UI must render it as plain text or Markdown (Streamlit's default) and **never** with `unsafe_allow_html=True`.

### Chunks for RAG

`chunk_course()` in [backend/app/ingestion/chunking.py](backend/app/ingestion/chunking.py) turns a stored course into searchable chunks: **424** for `javascript-beginner.json`. Sections are deliberately coarse (examples packed together; analogy, story and use cases combined; a lesson's exercise prompts in one chunk), so a whole course fits inside one day of the free embedding quota, with room left for questions.

- **Included:** module overviews; each lesson's explanation, key concepts, every example, analogy, **flowchart** (Mermaid), use cases, real-world story and takeaways; and the **prompt part** of each exercise (`interactiveExercise`, `miniChallenge`, `bugHunt`): instructions, starter or buggy code, expected result, hints.
- **Never included:** quiz questions and answers, bug-hunt fixes and explanations, and drag-and-drop / card-matching / code-reordering. Those are served and graded through the API (Step 17). Tests plant sentinel values in every answer field and check none reaches a chunk.
- **Format:** each chunk starts with a context header, e.g. `JavaScript Fundamentals › Variables and Data Types › Declaring Variables — Example 2`. The body is at most 1,500 characters (150 overlap when a section is split), at most 1,750 with the header.
- **IDs** are a SHA-256 of document + section + piece, so re-chunking gives identical IDs.
- **Exercise tagging:** exercise chunks are tagged `type: exercise`, so the tutor (Steps 12/14) gives hints, not solutions. That's a prompt rule, so best effort; the hard guarantee is that solutions are never retrievable.

### Indexing and search (FAISS)

Uploading a course starts indexing in the background: chunk → embed → save vectors in Postgres → add to the in-memory **FAISS** index (one per course). Check progress with `GET /admin/documents`:

| `status` | Meaning |
|---|---|
| `pending` | queued, or **paused for the embedding quota**: `error_message` says so, and it resumes by itself (about a minute later, or hourly checks while the daily quota is used up) |
| `processing` | being indexed now |
| `ready` | searchable |
| `failed` | `error_message` gives a short, safe reason; fix it, then `POST /admin/reindex` |

- **Resumable:** vectors are saved batch by batch, so a quota pause loses nothing and the next run embeds only what's missing. A document becomes searchable only when complete.
- **Restart-safe:** at startup the index is rebuilt from Postgres with **no embedding calls** (Render's disk is wiped on restart, so nothing is kept on disk). Documents interrupted by a restart resume automatically.
- **`POST /admin/reindex`** (admin): re-queues every document. Unchanged content with vectors in the current embedding space costs **no** quota; after changing the embedding provider or model, everything is re-embedded.
- **`POST /admin/search`** (admin) `{query, course_id?, k}`: what retrieval would return. Use it to check retrieval quality.
- **FAISS, not ChromaDB:** ChromaDB would add 34 packages (onnxruntime, kubernetes, grpcio…) to a 512 MB server whose disk is wiped on restart. FAISS adds one, and the index is rebuilt from Postgres anyway.

### Asking questions (`POST /chat/ask`)

Any logged-in user: `{"question": "...", "course_id": "javascript-beginner-v1", "session_id": "..."}` (`course_id`, `session_id` and `level` are optional; questions are up to 1,000 characters). Without `session_id` a new chat starts; the response returns its `session_id`, which you send back to ask follow-ups.

0. **Follow-ups** (a chat with earlier messages): the question is first rewritten into a standalone one from the last 3 exchanges ("How do I loop over it?" → "How do I loop over an array in JavaScript?"). That is one extra LLM call; if it fails, the question is used as asked.
1. The (standalone) question is embedded and the top `RAG_TOP_K` chunks are retrieved. Chunks below `RAG_MIN_SCORE` are dropped; if none are left, the reply says the course doesn't cover it, **without an LLM call**.
2. The model gets numbered sources and the question in separate blocks, with rules: use only the sources, cite them as `[1]`, reply `NOT_IN_COURSE` when they don't answer it, treat sources and question as data, and **give hints, never solutions, for practice exercises**.
3. The server keeps only markers that match a retrieved source (code like `arr[1]` is ignored) and builds the citations itself: Course › Module › Lesson › section, plus `link` (`/lessons/{lesson_id}`). A reply that cites nothing real is replaced by the "not covered" message.

```json
{"answer": "`let` is block-scoped [1].", "grounded": true,
 "citations": [{"number": 1, "course_title": "JavaScript for Beginners", "module_title": "…",
   "lesson_id": "javascript-beginner-mod-1-lesson-1", "lesson_title": "…", "section": "Explanation",
   "link": "/lessons/javascript-beginner-mod-1-lesson-1"}]}
```

`grounded: false` means the course doesn't cover the question; `answer` says so. Errors: 404 unknown course or chat, 403 someone else's chat, 409 chat full (100 messages; start a new one), 429 over the question quota (with `Retry-After`), 503 when the AI provider is unavailable. Questions and answers are stored in your chat history but never logged; logs hold only the outcome and counts. A failed answer stores nothing.

**Chat history** (only your own; anyone else's chat is **403**, admins included):

| Endpoint | Does |
|---|---|
| `GET /chat/sessions?limit=20&offset=0` | your chats, most recently active first (`limit` 1–50) |
| `GET /chat/sessions/{id}` | one chat with all its messages (answers include `grounded` and `citations`) |
| `DELETE /chat/sessions/{id}` | delete a chat and its messages (204) |

### Retrieval evaluation

`eval/dataset.jsonl` holds 84 hand-written cases from the JavaScript course: 58 answerable questions (each with the acceptable `lessonId`s and an expected answer), 12 out-of-course questions, 8 follow-ups (with history and a rewritten standalone question), and 6 requests for an exercise's solution (which must get hints only).

```bash
python eval/run_eval.py                                          # live: Neon dev index + Gemini, ~86 query embeddings
python eval/run_eval.py --offline --max-body 1000 --overlap 150  # local Hugging Face, no quota (needs requirements-local.txt)
python eval/run_eval.py --answers                                # + app-rewritten follow-ups, grounded answers, LLM judge (~140 LLM calls, paced)
```

Live mode rebuilds the index from `DATABASE_URL` (the course must already be indexed there), so it embeds only the questions. Offline mode chunks `eval/materials/javascript-beginner.json` with the given size and embeds everything locally, which makes it the way to compare chunk sizes. Reports go to `eval/reports/retrieval-<date>-<label>.{md,json}`: hit@1/3/5/10, MRR, hit@5 by module, the per-question ranks, and the **answer-or-refuse similarity threshold** that Step 12 uses. With `--answers`, `eval/reports/answers-<date>-<label>.{md,json}` adds: answered and judged-correct rates, expected-keyword coverage, citations on the expected lesson, correct refusals, hints-only replies to solution requests, and every failure quoted for review. Judge verdicts are cached in `eval/cache/` (gitignored), so re-runs only judge answers that changed. The judge is the same free model, so it may be lenient; read the quoted failures.

## Running code

Student code **never runs on our server**. It is sent to free, open-source remote sandboxes:

| Runner | Languages | Notes |
|---|---|---|
| **Judge0 CE** (`ce.judge0.com`, default) | C, C++, Java, Python, JavaScript, SQL (SQLite) | public instance, no key, per-IP throttling, no SLA |
| **Compiler Explorer** (`godbolt.org`, fallback) | C, C++, Java, Python | used automatically when Judge0 is unreachable, slow or rate-limited |

| Endpoint | Who | What |
|---|---|---|
| `POST /code/run` | logged in | `{language, code, stdin?}` → `{outcome, stdout, stderr, compile_output, exit_code, time_ms, provider, truncated}` |
| `POST /code/share` | logged in | `{language, code}` → `{url, warning}`: a **public, permanent** Compiler Explorer link (C, C++, Java, Python) |

- **`language`** is one of `c`, `cpp`, `java`, `python`, `javascript`, `sql`. **Java:** name the class `Main`.
- **Outcomes:** `ok`, `compile_error`, `runtime_error`, `timeout` and `output_limit` describe the *program* and come back as `200`. `429` means a quota was hit (it includes `Retry-After`); `503` means no runner is reachable.
- **Limits:** code at most 20 KB, input at most 8 KB, 5 s CPU / 10 s wall per program, and output cut at 64 KB per stream (`truncated: true`).
- **Privacy:** code and input go to the runner services. They are never logged by this app; logs record only runner, language, outcome and timing. Share links are public and permanent, created only when asked, and the response carries a warning.
- **Wandbox and Piston,** in the original plan, are not used: on 2026-11-18 Wandbox failed every run, and Piston's public API is whitelist-only.

Check the real runners (sends ~30 small programs; `--share` creates one public link):

```bash
python scripts/code_runner_smoke.py
```

## Coding assistant

Any logged-in user, for `javascript`, `python`, `c`, `cpp`, `java` and `sql`. Code is up to 8 KB and 200 lines; topics up to 200 characters. An optional `level` overrides the profile's explanation level for one request. Every response is validated JSON and lists up to 3 `related_lessons` (with `link`) found from the concepts involved.

| Endpoint | Body | Returns |
|---|---|---|
| `POST /coding/explain` | `language`, `code` | `summary`, `lines: [{line, explanation}]` |
| `POST /coding/debug` | `language`, `code`, optional `run` (the `/code/run` result) | `summary`, `issues: [{line, problem, fix_hint}]`, `corrected_code`, `exercise` |
| `POST /coding/example` | `language`, `topic` | `title`, `code`, `explanation` |
| `POST /coding/practice` | `language`, `topic` | `questions: [{question, hints, expected_output}]`, never solutions |

- **Course exercises get hints only:** if the code is (nearly) a course bug hunt or mini challenge in that language, `/debug` answers with hints, `corrected_code: null` and `exercise: true`. Matching is by text similarity (≥ 0.8), so a heavily rewritten copy is not caught; the prompt's hints-only rule is the fallback.
- **Line numbers are checked:** issues or explanations pointing outside the code are dropped.
- **Errors:** 422 invalid input, 429 over the shared AI quota (chat and coding share `CHAT_QUESTIONS_*`), 502 when the model's reply is still not valid JSON after one retry, 503 when the provider is unavailable. Code and model output are never logged.

Evaluate bug finding on 18 known-bug snippets (3 per language; the JavaScript ones are course bug hunts), about 18 LLM calls and no embeddings:

```bash
python eval/run_code_eval.py   # writes eval/reports/coding-<date>.{md,json}
```

## Practice

Quizzes, drag and drop, card matching and code reordering run on the **learning platform**, not here, so their answers never pass through the assistant.

- **Pointers:** at upload, each lesson stores its activities as names and sizes only (`lessons.content["practice"]`). Chat answers and `/coding/*` responses include `practice`: the cited or related lessons' activities, with a `url` when `PLATFORM_LESSON_URL` is set (an `https://` template containing `{lesson_id}`).
- **"Quiz me" requests** in the chat get a pointer to those activities, not questions written by the model.
- **Exercise attempts:** `POST /exercises/{id}/attempts {"code"}` grades a bug hunt, mini challenge or interactive exercise with the AI: `passed` and hint-style `feedback`. The reference solution is shown only to the model, and feedback that quotes it or contains code is replaced by a generic hint. Only the result is stored, not the code. `GET /exercises/{id}/attempts` lists your own attempts. In the frontend: **Submit for grading** in the compiler panel. Uses the shared AI quota.
- **Courses uploaded before this feature:** run once against that database:

```bash
python scripts/backfill_practice.py
```

## Project layout

```
backend/app/        FastAPI application (package "app")
  main.py           entry point: create_app()
  api/              HTTP routers, request dependencies (deps.py), schemas/
  auth/             password hashing, tokens, auth service, admin seeding
  runner/           code runners (Judge0, Compiler Explorer, fake), quota, fallback service
  ingestion/        upload checks, course JSON parsing (+ vendored course_schema.json), chunking
  indexing/         indexing pipeline, worker and startup rebuild (quota-aware)
  vectorstore/      in-memory FAISS index, one per course
  rag/              grounded answers: follow-up rewriting, retriever, prompt, citation checks
  chat/             chat sessions: ownership, history window, saving exchanges (ChatService)
  coding/           coding assistant: prompts, output schemas, exercise matching, CodingService
  learning/         practice pointers to the platform's activities, AI grading of exercise attempts
  evaluation/       evaluation dataset, retrieval and answer metrics, LLM judge, reports
  core/             configuration, logging, error handling
  providers/        shared plumbing: errors, retry, rate limiting, SDK clients
  llm/              LLM client and Gemini/OpenAI/fake chat adapters
  embeddings/       embedding client and Gemini/OpenAI/Hugging Face/fake adapters
  db/               models, Database (engine/sessions), repositories
  migrations/       Alembic migrations (config: alembic.ini at the repo root)
frontend/           Streamlit app (streamlit_app.py) and its API client (api_client.py)
  components/       compiler panel, DOM sandbox (dom_sandbox.html), practice view
eval/               dataset.jsonl + run_eval.py (RAG), code_cases.jsonl + run_code_eval.py (coding),
                    run_level_demo.py (levels), reports/
  materials/        course files used by tests and evaluation (javascript-beginner.json)
docs/               deployment guide
scripts/            manual smoke tests (llm, embedding, code runner)
tests/              mirrors backend/app/
```
