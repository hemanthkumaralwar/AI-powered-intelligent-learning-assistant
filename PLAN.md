# ArchintX AI-Powered Intelligent Learning Assistant — Build Plan (v2)

> Planning document for step-by-step execution with AI coding agents.
> One step = one focused session. Each step extends the existing codebase; none replaces earlier work.

## Project details

- **Project:** ArchintX AI-Powered Intelligent Learning Assistant (ArchintX Task 2, advanced level)
- **Purpose:** An AI learning assistant that answers student questions from course materials uploaded by admins, using Retrieval-Augmented Generation (RAG). Answers cite their sources, and the assistant says so plainly when the materials don't contain the answer. It keeps conversation context for follow-up questions. It also includes a coding assistant with a built-in code runner, quizzes, and personalized lesson recommendations.
- **Users:**
  - Admins upload and manage course materials (only admins can upload in v1).
  - Students learn, chat with the assistant, code, take quizzes and get recommendations.
  - Future: integration into the ArchintX learning platform.
- **Stack:**
  - Python and FastAPI
  - LLM: Google Gemini free tier by default, switchable to the OpenAI API via `LLM_PROVIDER`
  - Embeddings: Gemini by default; OpenAI or local Hugging Face sentence-transformers as options
  - LangChain, ChromaDB
  - PostgreSQL: Neon for development and tests, Supabase for production, plus Supabase Storage
  - Streamlit frontend
  - Code runner: Wandbox by default; Piston or Judge0 CE as options
- **Deployment:**
  - Development: local Python virtual environment, no Docker, no local PostgreSQL.
  - Production: online only, on free hosts: Render (backend), Streamlit Community Cloud (frontend), Supabase (database and storage).
- **Stage:** New build (empty repository).
- **Constraints:**
  - ₹0 budget: free tiers and open source only.
  - 10 days, one developer.
  - No Docker.
  - Must be a real RAG pipeline, not a chatbot that forwards every question to the LLM.
  - Handle security and privacy, API failures, timeouts and rate limits, and invalid uploads.
  - Setup must be reproducible.

### Grading weights

| Area | Marks |
|---|---|
| RAG implementation | 20 |
| Python and backend | 15 |
| LLM integration | 15 |
| Coding assistant | 15 |
| Vector database | 10 |
| Personalization | 10 |
| Testing and documentation | 10 |
| Final demonstration | 5 |

## Course content format (from `javascript-beginner.json`)

The course is a **course → module → lesson** tree with stable IDs: 8 modules × 8 lessons = 64 lessons. Each lesson contains:

- **Teaching content:** `lessonExplanation`, `concepts`, `syntax` and `parts`, `example[]`, `analogy`, `keyTakeaways`, `realWorldStory`, `useCaseCards`.
- **Practice:**
  - `quiz[]`: 10 multiple-choice questions per lesson. `correctAnswer` is a **string holding a 0-based index**; normalize it to an int.
  - `interactiveExercise`, `miniChallenge` (both with starter code), and `bugHunt` (buggy code, fixed code and hint).
- **UI-only content** (not embedded for RAG): Mermaid diagrams (`hooklineimage`, `flowchart`), `codereordering`, `dragandropp`, `cardmatching`.

What this means for the build:

- Topic = module and lesson = lesson. These come from the JSON, so JSON uploads need no manual tagging. TXT and PDF uploads are tagged manually.
- Lesson quizzes are a ready-made quiz source.
- The coding assistant must support **JavaScript**. The DOM and Events modules (6–7) need a browser sandbox.

## Assumptions and open questions

1. **Course structure.** Course JSON follows the ArchintX course schema (`course_schema.json` in the course-generator repo), and ingestion validates against it. Citations use **Course › Module › Lesson › section**. Recommendations point to `lessonId`s.
2. **Quizzes.** Behind one `QuizSource` interface:
   - (a) the external quiz platform API (primary)
   - (b) lesson-embedded quizzes
   - (c) LLM-generated quizzes (second option)

   Quiz scores are the main signal for weak topics. Bug-hunt and mini-challenge attempts are scored by the LLM and recorded the same way.
   - **OPEN (blocks Step 17 only):** the quiz platform JSON and its API details: base URL, authentication, endpoints, response format, and whether scores come back from the platform or students take quizzes in this app. Until then, a mock built from the example JSON is used.
3. **Code runner (free, open source).** Student code never runs on our server.
   - Console programs (C, C++, Java, Python, JavaScript/Node, SQL) are relayed by the backend to **Wandbox** (keyless public API).
   - "Open in Wandbox" creates a permalink so students can try code in the full compiler and paste the output back.
   - DOM and Events lessons run JavaScript in a sandboxed browser iframe.
   - Piston and Judge0 CE can be swapped in through configuration.
   - **Verify early (Step 7):** which language versions Wandbox offers (`list.json`, especially Java and SQL), and whether Piston's public API still works without a key.
4. **Formats.** JSON (main), TXT (secondary), PDF/DOCX (rare, stretch goal). Scanned PDFs give a "no extractable text" error.
5. **Databases.**
   - Neon free tier for development and tests (separate `dev` branch and a resettable `test` branch).
   - Supabase free tier for production.
   - No local PostgreSQL.
   - Unit tests use a fake LLM, embedder and code runner, so they use no quota. Only database tests touch the Neon `test` branch.
   - **[BUDGET]** Supabase pauses free projects after about a week of inactivity, and Neon sleeps when idle. Use a keep-alive ping and a pre-demo check.
6. **Embeddings.** Gemini by default; OpenAI switchable; **Hugging Face sentence-transformers as a local-only option** (`requirements-local.txt`, never deployed to Render's 512 MB instance). Each chunk records which model embedded it, so switching providers means re-indexing.
7. **One developer, 10 days [DEADLINE].** If time runs short, cut in this order:
   1. PDF/DOCX extraction
   2. LLM-generated quizzes
   3. the DOM sandbox (JavaScript still runs through Wandbox)
   4. merge level adaptation into prompts with no separate UI
8. **Other.** JWT authentication with admin and student roles; students register themselves; the admin is seeded from environment variables. English only. 10 MB upload limit. Recommendations are rule-based (no trained model).

## Why this order

- **Foundations first (Steps 1–5):** configuration, providers, database and authentication are shared by everything else.
- **Third-party risks next (Steps 6–7):** the free hosts and the Wandbox code runner are tested on Days 2–3.
- **RAG pipeline (Steps 8–13):** the evaluation dataset (Step 11) is built **before** RAG question answering (Step 12), so tuning is measured. RAG carries the most marks.
- **Remaining features, then the full UI, hardening and docs (Steps 14–22):** the UI comes last because it only connects to finished APIs.
- **Restart-safe persistence:** vectors are stored in Postgres, so the Chroma index is rebuilt after free-host restarts without spending embedding quota again.

Tags: **[SEC]** security/privacy · **[PERF]** performance/memory · **[BUDGET]** ₹0 / quotas · **[DEADLINE]** schedule

| # | Step | Day | Flags |
|---|---|---|---|
| 1 | Scaffold and configuration | 1 | SEC |
| 2 | LLM provider layer | 1 | BUDGET |
| 3 | Embedding providers | 1 | PERF, BUDGET |
| 4 | Database layer | 2 | BUDGET |
| 5 | Authentication and roles | 2 | SEC |
| 6 | Walking-skeleton deployment | 2 | DEADLINE, PERF, BUDGET |
| 7 | Code-runner service | 3 | SEC, BUDGET |
| 8 | Course ingestion | 3 | SEC |
| 9 | Structure-aware chunking | 4 | — |
| 10 | Embedding and vector store | 4 | PERF, BUDGET |
| 11 | Evaluation dataset | 5 | DEADLINE |
| 12 | Grounded RAG question answering | 5 | BUDGET |
| 13 | Conversation memory | 6 | SEC |
| 14 | Coding assistant | 6–7 | SEC |
| 15 | Compiler panel | 7 | SEC |
| 16 | Level adaptation | 7 | — |
| 17 | Quiz sources and grading | 8 | SEC, BUDGET, blocked on spec |
| 18 | Progress and recommendations | 8 | — |
| 19 | Full Streamlit frontend | 9 | — |
| 20 | Hardening | 9 | SEC, PERF, BUDGET |
| 21 | Production deployment and live evaluation | 10 | DEADLINE, BUDGET |
| 22 | Documentation and submission | 10 | — |

---

## Steps

### Step 1 — Scaffold and configuration (Day 1) [SEC]
- **Goal:** Repository layout (`backend/`, `frontend/`, `eval/`, `tests/`), settings via pydantic-settings, logging, `/health`, pytest, ruff, and GitHub Actions running unit tests only.
- **Files:** `backend/app/{main.py,core/config.py,core/logging.py}`, `requirements.txt`, `requirements-local.txt`, `.env.example`, `.gitignore`, `.github/workflows/ci.yml`.
- **Depends on:** nothing.
- **Done when:** `/health` returns 200; tests and lint pass locally and in CI; `.env` is git-ignored.

### Step 2 — LLM provider layer (Day 1) [BUDGET]
- **Goal:** `LLMProvider` interface (chat and structured JSON output) implemented for Gemini and OpenAI, plus a `FakeLLM`. Chosen by `LLM_PROVIDER`. Includes timeouts, backoff that respects retry-after, and typed errors (`RateLimited`, `Timeout`, `ProviderError`).
- **Files:** `app/llm/{base,gemini,openai,fake,factory}.py`, `tests/llm/`.
- **Depends on:** 1.
- **Done when:** tests pass with the fake; one real Gemini call works from a script; `LLM_PROVIDER=openai` selects the OpenAI class.

### Step 3 — Embedding providers (Day 1) [PERF] [BUDGET]
- **Goal:** `Embedder` interface implemented for Gemini (default), OpenAI, local Hugging Face (lazy import, local only) and a fake. Supports batching and rate limiting, and reports its model name and vector size.
- **Files:** `app/embeddings/{base,gemini,openai,huggingface,fake,factory}.py`, `tests/embeddings/`.
- **Depends on:** 1.
- **Done when:** tests pass; Hugging Face works offline after `pip install -r requirements-local.txt`; the production install has no torch.

### Step 4 — Database layer: Neon (dev/test), Supabase (prod) (Day 2) [BUDGET]
- **Goal:** SQLAlchemy models and Alembic migrations for:
  - `users`
  - `courses`, `modules`, `lessons` (keyed by the JSON IDs)
  - `documents` (with original-file reference and status)
  - `chunks` (with stored embedding and embedding model name)

  Original files go in Supabase Storage in production and in a database column in development.
- **Files:** `app/db/`, `alembic/`, `tests/db/`.
- **Depends on:** 1.
- **Done when:** `alembic upgrade head` succeeds on Neon `dev` and on Supabase; database tests pass on Neon `test`.

### Step 5 — Authentication and roles (Day 2) [SEC]
- **Goal:** Register and login, bcrypt hashing, JWT tokens, `require_admin` / `require_student` checks, admin seeded from environment variables, CORS restricted to the frontend's address.
- **Files:** `app/api/auth.py`, `app/core/security.py`, `app/api/deps.py`, `tests/api/test_auth.py`.
- **Depends on:** 4.
- **Done when:** a student calling an admin route gets 403; a bad or expired token gets 401; passwords never appear in responses or logs.

### Step 6 — Walking-skeleton deployment (Day 2) [DEADLINE] [PERF] [BUDGET]
- **Goal:** Backend on Render free tier (native Python, `render.yaml`, no Docker) connected to Supabase. Login-only Streamlit app on Streamlit Community Cloud. Secrets kept in platform settings. Keep-alive ping set up.
- **Files:** `render.yaml`, `frontend/streamlit_app.py`, `frontend/requirements.txt`, `docs/deployment.md`.
- **Depends on:** 5.
- **Done when:** the public Streamlit URL logs in against the public API; `/health` responds after a cold start; memory use is recorded and well under 512 MB.

### Step 7 — Code-runner service (Day 3) [SEC] [BUDGET]
- **Goal:** `CodeRunner` interface with three implementations:
  - `WandboxRunner` (default; languages mapped from `list.json`)
  - `PistonRunner` and `Judge0Runner` (switchable by configuration)
  - `FakeRunner` (tests)

  Endpoints: `POST /code/run` returns stdout, stderr, compile errors, exit status and time. `POST /code/share` returns a Wandbox link. Includes a code-size cap, timeout and per-user rate limit.
- **Files:** `app/runner/{base,wandbox,piston,judge0,fake}.py`, `app/api/code_run.py`.
- **Depends on:** 5.
- **Done when:**
  - hello-world and a compile error both run correctly for C, C++, Java, Python, JavaScript and SQL (gaps recorded)
  - an infinite loop returns a timeout cleanly
  - the share link opens in Wandbox
- **Note:** code runs on Wandbox's servers, never ours. Docs warn students not to paste personal data.

### Step 8 — Course ingestion: JSON first, then TXT, then PDF/DOCX (Day 3) [SEC]
- **Goal:** Admin-only upload and the student materials library.
  - Course JSON is validated against the course schema, then split into course, module and lesson records.
  - Lesson quizzes, `interactiveExercise`, `miniChallenge` and `bugHunt` are pulled out into their own tables.
  - TXT uploads are tagged by the admin with course, module and lesson.
  - PDF/DOCX extraction is a stretch goal.
  - Every upload is checked for type, size and well-formed JSON.
- **Files:** `app/ingestion/{validate,course_json,text,pdf_docx}.py`, `app/api/{admin_documents,materials}.py`, `tests/ingestion/fixtures/`.
- **Depends on:** 5.
- **Done when:** `javascript-beginner.json` loads as 8 modules, 64 lessons and 640 quiz items; invalid JSON, a schema mismatch, a file that is too large, or a student upload each return a clear 4xx error.

### Step 9 — Structure-aware chunking (Day 4)
- **Goal:** Each lesson is split into sections: explanation, concepts, syntax with parts, each example, analogy, bug hunt, takeaways and story. Mermaid diagrams and drag-and-drop/matching content are skipped. Long sections are split recursively. Metadata: course, module and lesson IDs and titles, and the section name. Chunk IDs are deterministic.
- **Files:** `app/ingestion/chunk.py`, `tests/ingestion/test_chunk.py`.
- **Depends on:** 8.
- **Done when:** about 600–900 chunks are produced for the JavaScript course; no chunk exceeds the size limit; re-running gives the same IDs.

### Step 10 — Embedding, vector store and restart-safe persistence (Day 4) [PERF] [BUDGET]
- **Goal:** ChromaDB vector store behind an interface. Ingestion runs as a background task:

  chunk → embed in batches → store vectors in Postgres → add to Chroma

  Document status moves through `pending → processing → ready / failed`. On startup the index is rebuilt from Postgres with **no new embedding calls**. Deleting a document removes its vectors. An admin `POST /admin/reindex` endpoint re-embeds everything after an embedding-provider change.
- **Files:** `app/vectorstore/{base,chroma}.py`, `app/ingestion/pipeline.py`, `app/startup.py`.
- **Depends on:** 3, 9.
- **Done when:** a similarity search for "difference between let and const" returns module 1, lesson 1; after deleting the Chroma folder and restarting, the index is rebuilt with **zero** embedder calls; failed documents show the reason.

### Step 11 — Evaluation dataset from the JavaScript course (Day 5) [DEADLINE]
- **Goal:** 40–60 questions with expected answers and the expected `lessonId` and section, written from the real course. Plus about 10 questions the course can't answer (e.g. React hooks, Python decorators) and about 8 multi-turn follow-up cases. A script measures retrieval quality (hit rate in the top k, MRR) and writes a report.
- **Files:** `eval/dataset.jsonl`, `eval/run_eval.py`, `eval/reports/`.
- **Depends on:** 10.
- **Done when:** the baseline report is committed, and chunk size and k are tuned against it.

### Step 12 — Grounded RAG question answering with citations (Day 5) [BUDGET]
- **Goal:** `POST /chat/ask`:
  - retrieves the top-k chunks, with a similarity score threshold
  - uses a grounding prompt
  - returns a **"not in the course materials"** answer when nothing supports one
  - cites Course › Module › Lesson › section with lesson links

  The evaluation script gains answer accuracy (LLM judge with cached results plus expected-keyword checks) and the correct-refusal rate.
- **Files:** `app/rag/{retriever,prompts,answer}.py`, `app/api/chat.py`.
- **Depends on:** 2, 11.
- **Done when:** retrieval hit rate in the top 5 ≥ 0.8; correct refusals ≥ 0.9; every answer that isn't a refusal has a valid citation.

### Step 13 — Conversation memory (Day 6) [SEC]
- **Goal:** Chat sessions and messages stored per user. Before retrieval, each follow-up is rewritten into a standalone question using a recent-history window. Endpoints list a user's sessions and their history.
- **Files:** `app/db/models/chat.py`, `app/rag/condense.py`, `tests/rag/test_followups.py`.
- **Depends on:** 12.
- **Done when:** the multi-turn evaluation cases pass (e.g. "What is an array?" → "How do I loop over it?" retrieves the array-iteration lesson); a student cannot read another student's sessions (403).

### Step 14 — Coding assistant, connected to the code runner (Days 6–7) [SEC]
- **Goal:** Explain, debug, example and practice endpoints for **JavaScript**, Python, C, C++, Java and SQL. Output is structured JSON: line-by-line explanation, issues with line numbers, corrected code, practice questions. The debug endpoint accepts the **actual run output and errors** from Step 7. Related course lessons are attached through the retriever. Includes a code-size cap.
- **Files:** `app/coding/{service,prompts,schemas}.py`, `app/api/coding.py`, `eval/code_cases.jsonl`.
- **Depends on:** 2, 7, 12.
- **Done when:** at least 80% of 18 known-bug snippets (3 per language) are identified, reusing the course's `bugHunt` items for JavaScript; every response passes JSON validation (retry once, then return a friendly error).

### Step 15 — Compiler panel (Day 7) [SEC]
- **Goal:** A reusable Streamlit compiler panel that appears when the student clicks a button. It has:
  - a code editor (streamlit-ace) and a language selector
  - **Run** (through Step 7) and **Open in Wandbox**
  - **Ask AI about this output** (sends the code and its output to the Step 14 debug endpoint)
  - a "paste output" box for code run elsewhere
  - starter code loaded automatically from the lesson's `interactiveExercise` / `miniChallenge` / `bugHunt`
  - a sandboxed iframe (`sandbox="allow-scripts"`) for DOM and Events exercises
- **Files:** `frontend/components/compiler.py`, `frontend/components/dom_sandbox.html`.
- **Depends on:** 7, 14.
- **Done when:** from a lesson, a student opens the panel with its starter code, runs it, sees the output and gets an AI explanation; a DOM exercise renders in the sandbox without access to the parent page.

### Step 16 — Level-adaptive explanations (Day 7)
- **Goal:** The user profile stores a level (beginner, intermediate or advanced), with a per-request override. Level-based prompt templates are shared by RAG answers and the coding assistant.
- **Files:** `app/llm/prompt_levels.py`, `app/rag/prompts.py`, `app/coding/prompts.py`, plus a migration.
- **Depends on:** 12, 14.
- **Done when:** tests confirm the right template is chosen for each level; a manual check shows a visibly different depth of explanation across levels.

### Step 17 — Quiz sources and grading (Day 8) [SEC] [BUDGET] — blocked on quiz platform spec
- **Goal:** `QuizSource` interface with three implementations:
  - `ExternalQuizPlatformSource` (API client built against the spec; uses a mock until it arrives)
  - `CourseJsonQuizSource` (embedded lesson quizzes)
  - `LLMQuizSource` (generated from chunks; second option; stored for reuse)

  Answer keys stay on the server until submission. Attempts are graded and stored per lesson and module; LLM-scored bug-hunt and challenge attempts are recorded the same way.
- **Files:** `app/learning/quiz_sources/`, `app/learning/grading.py`, `app/db/models/learning.py`, `app/api/quiz.py`.
- **Depends on:** 8, 16.
- **Done when:** a quiz from each source can be fetched, taken and graded; the external-API timeout falls back to lesson quizzes; the pre-submit response contains no answer key.

### Step 18 — Progress analysis and lesson recommendations (Day 8)
- **Goal:** Mastery per lesson and module, weighted toward recent attempts. Weak topics are those under a threshold. Recommendations give the next `lessonId`s plus their exercises, and extra practice is drawn from the weak topics. Endpoints: `/me/progress` and `/me/recommendations`.
- **Files:** `app/learning/{progress,recommend}.py`, `app/api/progress.py`.
- **Depends on:** 17.
- **Done when:** a seeded student who scores poorly on module 4 (Arrays) is recommended Arrays lessons and exercises; the scoring logic has unit tests.

### Step 19 — Full Streamlit frontend (Day 9)
- **Goal:**
  - Student pages: course browser (modules → lessons), chat with citations, compiler panel, coding helper, quizzes, progress and recommendations, level setting.
  - Admin pages: upload, document status, delete, re-index.
  - Friendly messages for rate limits and cold starts.
- **Files:** `frontend/streamlit_app.py`, `frontend/pages/*.py`, `frontend/api_client.py`.
- **Depends on:** 6, 13, 15, 18.
- **Done when:** the full demo script runs end to end: admin uploads the course → student asks a question → follows up → runs and debugs code → takes a quiz → sees recommendations; admin pages are hidden from students.

### Step 20 — Hardening (Day 9) [SEC] [PERF] [BUDGET]
- **Goal:** Per-user rate limits (API and code runner), response caching, clear 429/503/504 errors when the LLM, code runner or quiz platform fails, request size limits, logs without personal data, and privacy tests.
- **Files:** `app/core/{ratelimit,cache,errors}.py`, `tests/api/test_{failures,privacy}.py`.
- **Depends on:** 19.
- **Done when:** simulated provider failures return clean, documented errors; a student trying to read another student's data gets 403.

### Step 21 — Production deployment and live evaluation (Day 10) [DEADLINE] [BUDGET]
- **Goal:** Final deploy on Render, Supabase and Streamlit Cloud. Load the JavaScript course. Run the evaluation against the live API, warm up the servers, and record a backup demo.
- **Files:** `render.yaml`, `docs/deployment.md`, `eval/reports/production.md`.
- **Depends on:** 20.
- **Done when:** the public URLs work from a fresh browser; the production report is committed; a backup recording exists. Don't run the full evaluation right before the live demo, so the quota isn't used up.

### Step 22 — Documentation and submission (Day 10, written alongside earlier steps)
- **Goal:** README covering setup and provider switching (Gemini/OpenAI LLM; Gemini/OpenAI/local Hugging Face embeddings; Wandbox/Piston/Judge0 code runners). Swagger API docs. Technical documentation: architecture, design decisions, evaluation results, limitations, and how it integrates with ArchintX.
- **Files:** `README.md`, `docs/{architecture,api,evaluation,testing,deployment}.md`.
- **Depends on:** 21.
- **Done when:** a clean machine reaches a running app by following only the README; every deliverable maps to a file or link.

---

## Changes from the brief's suggested 10-day plan

- **Deployment moves from Day 10 to Day 2.** Production is online-only on free hosts, so their limits are tested from the start.
- **The code runner comes on Day 3.** It depends on a third-party service, so that risk is tested early.
- **The evaluation dataset arrives on Day 5, before RAG question answering,** and is built from the real JavaScript course.
- **Embeddings are stored in Postgres** so the vector index survives free-host restarts.

## Known technical debt

- ~~**Step 1 — test client warning.**~~ Resolved in Step 2. `httpx2` (github.com/pydantic/httpx2) is a dependency of both LLM SDKs and is now pinned in `requirements.txt`, so `httpx` was removed. Tests run with `-W error::DeprecationWarning` and pass.
- **Step 2 deviations from the plan.** `LLM_MAX_RETRIES` became `LLM_MAX_ATTEMPTS`, since the count includes the first try. The provider is not yet attached to the app; Step 12 wires `build_llm_client(settings)` into `create_app` as its first consumer.
- **Steps 2–3 — SDK client lifecycle (owner: maintainer, fix in Step 10 for embeddings and Step 12 for the LLM).** The Gemini and OpenAI SDK clients hold HTTP connection pools. They are meant to live for the whole app lifetime, so each must be created once at startup and closed in the FastAPI lifespan shutdown. Step 10 does this for `EmbeddingClient`, Step 12 for `LLMClient`. Today only the smoke scripts create them, and they exit right after.
- **Step 3 deviations from the plan.**
  - Retry, error types and Gemini/OpenAI SDK plumbing moved from `app/llm/` to a shared `app/providers/` package (embeddings and the Step 7 code runner use them too).
  - The errors were renamed to provider-neutral names: `ProviderCallError`, `ProviderTimeoutError`, `ProviderConfigurationError`, `ProviderRequestError`.
  - `gemini-embedding-001` is used at 768 dimensions, because `gemini-embedding-2` merges a batch into a single vector.
- **Step 1 deviations from the plan.** Tool config lives in `pyproject.toml` (not `pytest.ini`). `requirements-local.txt` is deferred to Step 3, which is its first real use.

- **Step 4 deviations from the plan.**
  - Supabase Storage was dropped: originals are stored as `bytea` in a separate `document_files` table, in every environment.
  - The first migration enables Row Level Security on every table, because Supabase's Data API exposes `public`.
  - Models live in a single `app/db/models.py` (not a `models/` folder); it is small enough.
- ~~**Step 4 — `Database` wiring.**~~ Resolved in Step 5: the FastAPI lifespan creates it, sessions are per request, and `dispose()` runs at shutdown. Previously: `build_database(settings)` is not yet attached to the app. Step 5 must create it in the FastAPI lifespan, provide sessions per request, and call `dispose()` at shutdown.
- ~~**Step 4 — Windows dev server.**~~ Resolved in Step 5: run uvicorn with `--loop asyncio:SelectorEventLoop` (README); checked live against Neon. Previously: psycopg's async mode cannot run on Windows' default `ProactorEventLoop`. Tests already use a `SelectorEventLoop`. Step 5 must make sure `uvicorn` uses a selector loop on Windows. Render (Linux) is unaffected.

- **Step 5 deviations from the plan.**
  - Argon2id instead of bcrypt (bcrypt drops everything after 72 bytes).
  - No CORS middleware: Streamlit calls the API from its own server, so the strictest option (none) works.
  - `require_student` became `require_user`: no route should block admins.
  - Validation errors never echo input or reveal password length.
- **Step 5 — brute-force protection (owner: maintainer, fix in Step 20).** Login and registration have no rate limit or lockout yet. Step 20's per-user/IP rate limiting must cover `POST /auth/login` and `POST /auth/register` first.

- **Step 6 deviations from the plan.**
  - No keep-alive (your decision). A GitHub cron would exceed the private-repo Actions quota (~3,100 of 2,000 free minutes), so cold starts are accepted and the demo warm-up is documented in `docs/deployment.md`.
  - Migrations run in Render's build command.
  - Render deploys only after CI passes (`autoDeployTrigger: checksPass`).
  - Memory was measured locally (~70 MB); the Render figure is to be read from its Metrics tab after the first deploy.

- **Step 7 deviations from the plan.**
  - Judge0 CE (default) and Compiler Explorer (fallback, share links) replace Wandbox and Piston: on 2026-11-18 Wandbox failed every run ("Failed to get uid") and Piston's public API became whitelist-only (2026-02-15).
  - Compiler Explorer cannot run JavaScript or SQL, so those depend on Judge0 alone.
  - The Java `public class Main` modifier is dropped for Compiler Explorer only.
  - Share links are public and permanent (Compiler Explorer's design) and come with a warning.
- **Step 7 — in-memory run quotas (owner: maintainer, revisit in Step 20).** Per-student and app-wide limits live in process memory: correct for the single Render instance, reset on restart, and not shared if the API ever runs more than one instance. Step 20 should move them to the shared rate limiter.
- **Step 7 — free runner dependence (owner: maintainer, watch before the demo).** Neither runner publishes terms or limits, and both are free community services with no SLA. Run `scripts/code_runner_smoke.py` before the demo; if Judge0 is down, C/C++/Java/Python still run via Compiler Explorer, but JavaScript and SQL do not.

- **Step 8 deviations from the plan.**
  - Students cannot download course JSON (it contains every answer); they get answer-free structured content through `/courses` and `/lessons`.
  - Re-uploading a course returns 409; delete it first.
  - The course language is chosen at upload.
  - A request-size middleware was added: 10 MB for uploads, 64 KB for everything else.
  - PDF/DOCX remain a stretch goal (415).
- **Step 8 — rendering rule (owner: maintainer, enforce in Step 19).** Course text is stored as uploaded. The Streamlit UI must never render it with `unsafe_allow_html=True`.
- **Step 8 — upload buffering (owner: maintainer, revisit in Step 20).** The size middleware buffers up to ~10 MB per upload request before authentication runs. Step 20's rate limiting should cover `POST /admin/documents`.
- **Data quality, for Step 17.** In `javascript-beginner.json` the correct quiz option is index 1 in 64% of questions. Shuffle options when serving quizzes.

## Pending inputs

- [ ] Quiz platform JSON and API details (needed by Day 8, Step 17)
- [ ] Step 6 cold-start check (postponed): leave the API idle 15+ minutes, then time `GET https://archintx-api-kday.onrender.com/health`; record the result in `docs/deployment.md`.
- [ ] Step 6 memory reading: Render → archintx-api → Metrics had no data right after the first deploy; record the peak once available (expected well under 512 MB; local ~70 MB).
