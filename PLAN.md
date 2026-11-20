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
- **Goal:** README covering setup and provider switching (Gemini/OpenAI LLM; Gemini/OpenAI/local Hugging Face embeddings; Judge0 CE and Compiler Explorer code runners, which replaced Wandbox/Piston in Step 7). Swagger API docs. Technical documentation: architecture, design decisions, evaluation results, limitations, and how it integrates with ArchintX.
- **Files:** `README.md`, `docs/{architecture,api,evaluation,testing,deployment}.md`.
- **Depends on:** 21.
- **Done when:** a clean machine reaches a running app by following only the README; every deliverable maps to a file or link.

### Step 23 — Additional features (after submission) [PERF] [BUDGET]
Built after Step 22 is submitted, in order: 23a, then 23b, then 23c (23c reuses 23b's schedule). Each part ships on its own, and each is turned on per course by an admin (all default off).

**23a — Practice from Arc (about a day; first)**
- **Goal:** close the loop from an answer to practice. Built in two pieces, in this order:
  1. **"Open in Practice"**: an answer that cites a lesson gets a button that opens that lesson's Practice tab in LearnX (the tab already says when a lesson has no exercises, so no extra request is made to check).
  2. **"Run this example"** (decided after piece 1 ships): a code block in the **latest** answer gets an expander with the compiler panel pre-filled. Whether it also belongs on the Reading tab's examples is decided then.
- **Admin switch (your decision, 2026-11-20):** the feature is turned on or off **per course**, by admins only.
  - Stored on the course (migration: `courses.arc_practice_enabled`, default **off**, so an admin opts each course in).
  - `PATCH /admin/courses/{course_id}` `{"arc_practice_enabled": true|false}`: admin only (403 for students), audited in the log as metadata (who, which course, on/off).
  - **Coding courses only:** the switch is refused (422) for a course whose language is not one the code runner supports. Today every course has one (a database constraint), so this guards future non-coding courses.
  - Settings shows the switch per course; Arc shows the buttons only for answers whose cited course has it on.
  - **What the switch is not:** a security boundary. It controls the shortcut, not access: students can open Practice and run code from LearnX either way, and `/code/run` keeps its own per-student quota.
- **Backend change needed:** citations gain `course_id` (search results already carry it), because LearnX needs the course to open a lesson, and Arc needs it to read the course's switch.
- **Rules:** no AI calls; runs count against the existing run quota; nothing is pre-filled from an exercise's solution. For "Run this example": the language comes from the code block's tag, falling back to the course's language; no button for languages the runner cannot run (e.g. HTML).
- **Files:** `app/db/models.py` + migration `0007`, `app/api/admin_documents.py` (switch), `app/rag/answer.py` + `app/api/schemas/chat.py` (`course_id`), `frontend/views/arc.py`, `frontend/views/admin_courses.py`, `frontend/views/learnx.py` (open a lesson's Practice tab directly), `docs/api.md`, README, tests mirroring each.
- **Done when:** with the switch on, an answer citing a lesson opens that lesson's Practice tab in one click; with it off (or for another course) no button appears; a student gets 403 on the switch endpoint; the switch is refused for a non-coding course.

**23b — Spaced review (about a day; second)**
- **Goal:** tell students *when* to revisit a lesson, not only what is weak.
- **Decisions (yours, 2026-11-20):**
  - **Per lesson:** a lesson becomes due; reviewing it means re-submitting any of its exercises.
  - **Ladder:** the lesson's attempts are replayed in time order. Each pass moves the next review out 1 → 3 → 7 → 14 → 30 days; any failed attempt resets it to 1 day. A pass at the 30-day review marks the lesson **mastered**, and it stops coming up.
  - **Placement:** a separate **"Due for review"** list above "What to do next" on the LearnX course page. A lesson shown as due is left out of the review part of "What to do next", so nothing appears twice.
  - **Admin switch per course,** like 23a: `courses.spaced_review_enabled`, default **off**, set with the same admin-only `PATCH /admin/courses/{course_id}`, shown in Settings. With it off, the course has no due list and `/me/reviews` returns nothing for it.
- **Rules:**
  - Derived from stored exercise attempts on every request: no new data collected, no schedule table.
  - "Due" counts **24-hour periods** from the last attempt (the app does not know students' time zones, so no "calendar day").
  - Only lessons the student has attempted can be due; not-started lessons stay with "What to do next".
  - No AI calls to compute it. Each review is an exercise submission, so it costs one AI grading call, from the existing shared quota.
  - No reminders (no email or push on the free tier): due reviews show when the student visits.
- **Known limit:** about 3 exercises per lesson, so reviews re-use exercises the student has seen and can drift towards remembering answers. Fresh questions come with 23c, or with quiz scores if the platform shares them.
- **Files:** `app/learning/review.py` (pure scheduling, injected clock), `GET /me/reviews?course_id=` (owner only), migration `0008` (the switch), `app/api/admin_documents.py` (switch), `frontend/components/progress.py`, `frontend/views/admin_courses.py`, `docs/api.md`, README, tests mirroring each.
- **Done when (tests with a fixed clock):** a failed attempt makes the lesson due 24 hours later; two passes in a row push it to 3 days; a pass at the 30-day step marks it mastered and it never shows again; a due lesson is not repeated in "What to do next"; with the course's switch off nothing is due; a student gets 403 on the switch and only ever sees their own reviews.

**23c — Tutor mode, an experiment (largest; last, after 23b)**
- **Goal:** the adaptive part of your tutor prompt that a static lesson cannot do: one question at a time, a mastery gate, a fresh demo when stuck, and earlier concepts mixed back in. Built on the course schema and server-side state, not a free-form prompt.
- **Decisions (yours, 2026-11-20):**
  - **An experiment behind a switch:** admin-only per course (`courses.tutor_enabled`, default **off**, same `PATCH /admin/courses/{course_id}` as 23a/23b). Measure calls per concept on about 3 lessons before turning it on more widely.
  - **Started from a lesson:** a "Practice with Arc" button on the LearnX lesson page tutors that lesson's concepts, so it is always in-course.
  - **Its own daily cap:** `TUTOR_LESSONS_PER_STUDENT_PER_DAY` (default 2, about 80 calls) and an app-wide `TUTOR_CALLS_PER_DAY`, separate from Arc's quota, so tutoring never blocks normal answers. 429 with `Retry-After` when reached.
  - **Stop rule:** after 2 wrong in a row, a new demo with a different analogy and mastery reset to 0; after 3 practice rounds plus that one re-demo, move to the next concept and mark it for spaced review (23b). Cost stays bounded.
- **The cycle per concept (server-driven):**
  1. **Demo** from the course: the lesson's `example` and `analogy` (no AI call).
  2. **Practice,** at most 3 rounds, one question per turn. Each round changes one thing (domain, audience, constraint or format). The lesson's `interactiveExercise` / `miniChallenge` are used where they fit, but a lesson has 2–3 exercises for about 8 concepts, so most questions are AI-written from the lesson's chunks.
  3. **Mastery gate:** 2 correct in a row to advance (or the stop rule above).
  4. **Interleave:** after every 2 concepts, one question on an earlier concept in a new context.
  5. **Recall:** at the end, "close the notes" questions turned from `keyTakeaways` (statements, so the AI phrases them as questions).
  6. **Spacing:** a session opens with one recall question on a lesson that 23b says is due, if any.
- **Feedback on every answer:** correct or incorrect, the right answer, and one sentence why. Showing the answer is fine for AI-written questions; **course exercises stay hints-only** (never their solution).
- **One AI call per turn:** it grades the answer and writes the next question together, as JSON (the coding helper's pattern, one retry then 502). About 5 calls per concept, about 40 per lesson. The demo costs nothing.
- **Framing:** the student's explanation level (beginner = simple words, one-sentence definitions of every term, a real analogy), reusing `prompt_levels.py`.
- **State and privacy:** the server keeps the lesson, concept, cycle step, round and mastery in a `tutor_sessions` table (migration). No model-written state header and no pasted RESUME block, which a student could edit. Instead the page shows "Concept 3 of 8 · mastery 1/2". State survives a page reload. Student answers are **not stored** (only correct or incorrect); sessions follow the 90-day chat retention.
- **Security:** student answers go into the grading prompt as data, neutralised like chat questions (`defuse`); owner-only access (403 otherwise); the reference solution is never in a reply (leak test).
- **Files:** `app/tutor/{service,schemas,prompts}.py`, migration `0009`, `/tutor/*` endpoints, settings for the caps, `frontend/components/tutor.py` + the LearnX lesson page, `eval/tutor_cases.jsonl` + a runner, `docs/api.md`, README, tests mirroring each.
- **Done when:**
  - Mechanics (tests with a fake model): a student completes one concept's cycle; state survives a reload; the mastery gate and stop rule hold; interleave and due-review questions appear; a student hits the daily cap with 429; course exercises never reveal their solution; another student's session is 403.
  - Quality (live, on about 3 lessons): practice questions stay in-course and are graded correctly on ≥ 90% of a 20-answer evaluation set.
  - Cost (live): measured AI calls per concept and per lesson recorded in PLAN.md, and the switch is turned on more widely only if they fit the free tier.

---

## Changes from the brief's suggested 10-day plan

- **Deployment moves from Day 10 to Day 2.** Production is online-only on free hosts, so their limits are tested from the start.
- **The code runner comes on Day 3.** It depends on a third-party service, so that risk is tested early.
- **The evaluation dataset arrives on Day 5, before RAG question answering,** and is built from the real JavaScript course.
- **Embeddings are stored in Postgres** so the vector index survives free-host restarts.

## Known technical debt

- ~~**Step 1 — test client warning.**~~ Resolved in Step 2. `httpx2` (github.com/pydantic/httpx2) is a dependency of both LLM SDKs and is now pinned in `requirements.txt`, so `httpx` was removed. Tests run with `-W error::DeprecationWarning` and pass.
- **Step 2 deviations from the plan.** `LLM_MAX_RETRIES` became `LLM_MAX_ATTEMPTS`, since the count includes the first try. The provider is not yet attached to the app; Step 12 wires `build_llm_client(settings)` into `create_app` as its first consumer.
- **Steps 2–3 — SDK client lifecycle (owner: maintainer, fix in Step 10 for embeddings and Step 12 for the LLM).** The Gemini and OpenAI SDK clients hold HTTP connection pools. They are meant to live for the whole app lifetime, so each must be created once at startup and closed in the FastAPI lifespan shutdown. Step 10 does this for `EmbeddingClient`, Step 12 for `LLMClient`. **Resolved in Step 12:** `create_app` builds the `AnswerService` (and its `LLMClient`) once and closes it at shutdown.
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
- **Step 5 — brute-force protection (owner: maintainer, fix in Step 20).** Login and registration have no rate limit or lockout yet. Step 20's per-user/IP rate limiting must cover `POST /auth/login` and `POST /auth/register` first. **Resolved in Step 20:** per-username lockout plus app-wide sign-in and registration caps.

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
- **Step 7 — in-memory run quotas (owner: maintainer, revisit in Step 20).** Per-student and app-wide limits live in process memory: correct for the single Render instance, reset on restart, and not shared if the API ever runs more than one instance. Step 20 should move them to the shared rate limiter. **Kept in Step 20:** a shared store needs Redis (not free); revisit only if the API runs more than one instance.
- **Step 7 — free runner dependence (owner: maintainer, watch before the demo).** Neither runner publishes terms or limits, and both are free community services with no SLA. Run `scripts/code_runner_smoke.py` before the demo; if Judge0 is down, C/C++/Java/Python still run via Compiler Explorer, but JavaScript and SQL do not.

- **Step 8 deviations from the plan.**
  - Students cannot download course JSON (it contains every answer); they get answer-free structured content through `/courses` and `/lessons`.
  - Re-uploading a course returns 409; delete it first.
  - The course language is chosen at upload.
  - A request-size middleware was added: 10 MB for uploads, 64 KB for everything else.
  - PDF/DOCX remain a stretch goal (415).
- **Step 8 — rendering rule (owner: maintainer, enforce in Step 19).** Course text is stored as uploaded. The Streamlit UI must never render it with `unsafe_allow_html=True`.
- **Step 8 — upload buffering (owner: maintainer, revisit in Step 20).** The size middleware buffers up to ~10 MB per upload request before authentication runs. Step 20's rate limiting should cover `POST /admin/documents`. **Resolved in Step 20:** requests without a bearer token are refused before the body is read; a logged-in student can still send one ≤ 10 MB body before the 403.
- **Data quality, for Step 17.** In `javascript-beginner.json` the correct quiz option is index 1 in 64% of questions. Shuffle options when serving quizzes.

- **Step 9 deviations from the plan (your decisions, 2026-11-19).**
  - **Course JSON only:** the TXT notes path from Step 8 was removed (upload, `/materials` endpoints, `documents.module_id/lesson_id` via migration `0003`, which refuses to run while notes exist). DOCX/PDF/TXT → course JSON conversion is a **separate project** next to the course generator.
  - **Chunks include exercise prompts and flowcharts,** never answers. The real course gives 1,225 chunks (planned ~600–900; exercises and flowcharts add 256, and long sections split with overlap).
  - **Chunking is pure** (`chunk_course`); storing and embedding chunks is Step 10's pipeline.
- **Steps 12 & 14 — hints, not solutions (owner: maintainer).** When a retrieved chunk has `type: exercise`, the prompt must tell the model to give hints and guiding questions, never full solution code. That's a prompt rule, so best effort. **Step 12:** the rule is in the grounding prompt, and `eval/dataset.jsonl` has 6 `solution_request` cases that the answer evaluation checks with the LLM judge. Step 14 must reuse the rule.
- **Step 17 — widened scope.** Serve **quizzes, drag-and-drop, card matching and code reordering** through the API, with answers kept and checked **server-side**. Extract the activities from the stored course JSON (`document_files`), and shuffle quiz options.
- **Course-content note (for the course generator).** In 3 lessons (mod-2 lesson 7, mod-7 lesson 3, mod-8 lesson 6) the bug-hunt fix appears verbatim as a lesson example, so the bug hunt can be solved by reading the examples.

- **Step 10 deviations from the plan.**
  - **FAISS instead of ChromaDB:** 1 package vs 34, no telemetry, and Render's disk is wiped anyway.
  - **Quota-aware, resumable indexing:** a live run hit Gemini's free tier, which counts *every text in a batch* (about 100/minute, about 1,000/day). Indexing now uses per-text budgets (80/minute; 20/minute reserved for questions) and batches of 40, saves vectors batch by batch, pauses as `pending` on a quota hit, and resumes on its own. Search loads only `ready` documents, so a half-indexed course is never searchable.
  - **Coarser chunks (changes Step 9):** 1,225 → 424 for the JavaScript course (1,500-character bodies; grouped examples; analogy + story + use cases; takeaways + flowchart; one practice chunk per lesson), so a course fits in one day's quota.
  - **New endpoints:** admin `POST /admin/search` and `POST /admin/reindex`.
- **Step 10 — `GEMINI_API_KEY` required on Render (owner: you, before this deploy).** The API builds the embedding client at startup. Without the key, Render rejects the new version and keeps the previous one running.
- **Step 10 — free-tier embedding budget (owner: maintainer, watch).** About 1,000 texts a day are shared by indexing (424 per course) and student questions (1 each). A second course, or a re-index after changing the embedding model, may take two days. Each document's `error_message` shows when it is waiting.
- **Step 11 results (2026-11-19; reports in `eval/reports/`).**
  - **Baseline (Gemini `gemini-embedding-001`, 424 chunks, 78 cases):** answerable hit@1 98%, hit@3/5/10 100%, MRR 0.989. Follow-ups as asked: hit@5 62%, hit@10 88%; rewritten into standalone questions: 100%.
  - **Chunk size: kept at 1,500 / 150** after an offline comparison with the local Hugging Face model (no quota). 1,000 / 150 found one more question (hit@5 98% vs 97%) but did worse on follow-ups (38% vs 50%) and on telling answerable from out-of-course questions (91% vs 94%), with twice the chunks (865 vs 424), so twice the daily quota. 2,000 / 200 scored the same as 1,500. **No Gemini re-index.**
  - **For Step 12:** `k = 5` (hit@3 is already 100%; 5 leaves headroom). Similarity threshold **0.63**: every answerable question scored ≥ 0.640 and every out-of-course one ≤ 0.624. The margin is thin (0.016), so Step 12 re-measures refusals with the LLM in the loop.
  - **For Step 13:** follow-ups must be rewritten into standalone questions before retrieval (62% → 100% hit@5).
  - **Caveat:** the questions were written from the course text, so these scores are optimistic. Real student questions will score lower; add misses from Step 21's live evaluation to the dataset.
  - **Threshold depends on the embedding model.** It is measured for `gemini-embedding-001` at 768 dimensions; re-run `eval/run_eval.py` after any change of embedding provider or model (the Hugging Face model's best threshold is about 0.70).
- **Step 12 decisions (2026-11-19).**
  - **`POST /chat/ask`:** any logged-in user; optional `course_id` (404 if unknown); questions up to 1,000 characters. Retrieval uses `RAG_TOP_K=5` and `RAG_MIN_SCORE=0.63` from Step 11; below the threshold the reply is the fixed "not in your course materials" message **without an LLM call**.
  - **Citations are built by the server:** the model marks sources as `[n]`; markers that match no retrieved source are dropped (code such as `arr[1]` is ignored), and a reply that cites nothing real becomes the refusal. The link is the API path `/lessons/{lesson_id}`; Step 19 maps it to a page.
  - **Prompt injection:** sources and the question sit in separate tagged blocks marked as data; tags inside them are defused. The hints-not-solutions rule for `type: exercise` chunks is in the prompt.
  - **Question quota:** 5 per student per minute and 20 per minute app-wide (in memory, like code runs). The sliding-window quota moved from `runner/` to `core/quota.py` so both use it.
  - **Database connection:** `/chat/ask` commits (releasing its pooled connection) before the slow provider calls. **Debt (owner: maintainer, Step 20):** `/code/run` still holds a connection for up to 30 s through `CurrentUser`; apply the same early commit there. **Resolved in Step 20.**
  - **Default model is now `gemini-3.5-flash-lite`** (was `gemini-3.8-flash`, which timed out on 2026-11-19), with `GEMINI_THINKING_BUDGET` defaulting to `default` (no thinking setting): lite models answer 400 INVALID_ARGUMENT even to a budget of 0. Switching back to a thinking model needs `GEMINI_THINKING_BUDGET=0` as well.
  - **Evaluation:** `--answers` adds answer accuracy (LLM judge, cached in `eval/cache/`, gitignored), correct refusals, citation checks and 6 `solution_request` cases. The question embeddings are reused across phases, and a provider failure is recorded per case instead of aborting the run.
- **Steps 12 and 13 Done-when results (2026-11-19, `gemini-3.5-flash-lite`, Neon dev, 84 cases).**
  - **Step 12:** retrieval hit@5 100% (target >= 0.8), MRR 0.989; out-of-course questions correctly refused 12/12 (100%, target >= 0.9); grounded answers with a valid citation 100%, citing an expected lesson 100%; answers judged correct 97% of 58 (the 2 misses were Gemini briefly unavailable, not wrong answers; all 56 answered were judged correct); exercise-solution requests answered with hints only 6/6.
  - **Step 13:** follow-ups rewritten by the app hit@5 8/8 (100%, target >= 7/8), the same as the hand-written rewrites; as asked they score 62%. Every rewrite kept the student's meaning (listed in the retrieval report).
- **Step 13 decisions (2026-11-19).**
  - **Files:** the plan's `app/db/models/chat.py` became two classes in the existing single `app/db/models.py` (`ChatSession`, `ChatMessage`), with `db/repositories/chats.py`, migration `0004` (row-level security on) and `app/chat/service.py`.
  - **API:** `POST /chat/ask` takes an optional `session_id` (none: a new chat, titled from the question) and returns it; `GET /chat/sessions`, `GET /chat/sessions/{id}`, `DELETE /chat/sessions/{id}`. Only the owner may read, continue or delete a chat; anyone else, admins included, gets 403.
  - **Follow-ups:** `app/rag/condense.py` rewrites the question from the last 3 exchanges (each cut to 500 characters, temperature 0) before retrieval, and only when the chat has history. The answer prompt sees only the rewritten question, not the history, so answers stay grounded. A failed or unusable rewrite falls back to the question as asked.
  - **Storage:** the question, its rewrite, the answer, `grounded` and citations. `ask` loads in one short transaction and saves in another, so no connection is held during the provider calls; a failed answer saves nothing. 100 messages per chat (409). A concurrent write to the same chat is a 409 via the (session, position) unique constraint.
  - **Evaluation:** `--answers` also scores follow-ups rewritten by the app ("Follow-ups, rewritten by the app" row) and lists every rewrite for review.
- **Step 23b built (2026-11-20): spaced review.**
  - **Rule change from the plan (your approval):** a pass moves a lesson up the ladder only when it is due (or it is the first attempt); an early pass changes nothing. As first written, passing five times in ten minutes would have reached "mastered". A failure always resets to 1 day, mastered or not.
  - **Scheduler:** `app/learning/review.py`, pure (attempts in, schedule out), replayed from stored attempts on every request; no schedule table, no AI calls. "Due" counts 24-hour periods.
  - **Endpoint:** `GET /me/reviews?course_id=` (required; owner only; 404 unknown course). "Now" is a dependency (`current_time`) so tests fix the clock. With the switch off it returns `enabled: false` and no items.
  - **Switch:** `courses.spaced_review_enabled` (migration `0008`, default off) on the same admin-only `PATCH`. Settings' switches are now one table-driven loop (`FEATURES`), ready for 23c.
  - **Course page:** "Due for review" above "What to do next"; its Review button opens the lesson on Practice. Due lessons are left out of the review part of "What to do next" (filtered in the frontend, which has both lists).
- **Step 23a built (2026-11-20): Open in Practice.**
  - **Switch:** `courses.arc_practice_enabled` (migration `0007`, default off); `PATCH /admin/courses/{course_id}` (admin only, 403 for students) accepts only known switches (empty, null-only or unknown → 422), commits before clearing the course cache so the change takes effect at once, and logs the admin id, course and change. Settings has one toggle per course; it calls the API only when the admin flips it (a "compare every run" version looped forever when the server value did not change, found by the tests).
  - **"Coding courses only" without dead code:** the database already allows only the six runnable languages, so every course is a coding course and the endpoint has no language check; the model and endpoint say a check is needed if non-coding courses are ever allowed.
  - **Citations carry `course_id`** (answers and stored history); citations saved earlier have none and simply get no button.
  - **Arc** reads the cached course list once per page and shows "Open in Practice: <lesson>" under answers citing a switched-on course (one button per distinct lesson). The button switches to LearnX with the lesson open on its **Practice** tab (`st.tabs(default=...)`); the tab stays fixed for the visit, and lessons opened inside LearnX start on Reading. Navigation state moved to `frontend/components/lesson_nav.py`, shared by LearnX and Arc.
  - **Not in this piece:** "Run this example" (to decide after this ships).
  - **Tests:** API (default off; admin on/off seen by students at once; student 403; four bad bodies 422; unknown course 404; `course_id` in answers and history; old citations still load) and frontend (button opens the lesson on Practice; no button when off or for old citations; LearnX lessons start on Reading; admin toggle sends the change; a failed change shows the error and keeps the server value).
- **Step 22 decisions (2026-11-20).**
  - **README = setup; docs/ = reference.** The README now opens with live links, a docs index and a numbered **Quick start** (free Neon database and Gemini key → `.env` → migrate → API → frontend → load the course → register a student through Swagger, since the app has no sign-up form), then provider switching, the configuration table, a **deliverables map** (each grading area → its files or links) and the project layout. Reference material moved out instead of being copied: `docs/architecture.md` (components, RAG flow with diagrams, data, security, changes from the brief, limitations, ArchintX integration), `docs/api.md` (all 29 endpoints, errors, quotas), `docs/evaluation.md` (every result with its report), `docs/testing.md`.
  - **Docs cannot drift:** `tests/docs/test_docs.py` fails if an API route (read from the OpenAPI spec) is missing from `docs/api.md`, or a setting is missing from the README's configuration table or `.env.example`. It immediately found one (`CODE_RUNS_PER_USER_PER_DAY` was only written as `_PER_DAY`).
  - **Corrections found while writing:** the course takes about 5 minutes to index (424 chunks at the free tier's pace), not "about a minute" (that was the 4-lesson demo course); migrations live in `backend/migrations/`, not `backend/app/`; Step 22's goal named Wandbox/Piston (replaced in Step 7).
  - **Clean-machine check (2026-11-20):** a fresh clone, a new virtual environment and only the README's commands reached a running app (`/health` ok, Swagger, sign-in, the LearnX course list) on Neon dev. Finding: on Windows, pip failed inside a deep folder (OpenAI's SDK has very long file paths, past the 260-character limit), so the README now says to clone into a short path; a cold install takes about 10 minutes. The clone (with a copy of `.env`) was deleted afterwards.
  - **Pending (your Step 21 tasks):** the production evaluation report and the backup recording; both are marked "pending" in the README's deliverables map.
- **Whole-codebase re-check (2026-11-20, your request).** Judged on the real code: dead code and unused imports, complexity per function, code smells.
  - **Clean:** ruff (PEP 8, pyflakes, bandit, import order) passes across backend, frontend, eval, scripts and tests; no function over 10 branches; no commented-out code; no TODO/FIXME markers; pip-audit finds no known vulnerabilities (backend and frontend requirements).
  - **Fixed (`28e6fb7`):** removed `CourseRepository.get_module` (dead: only its own test called it). Chunking's `_pieces` took 8 parameters that always travel together; a `Source` value object (document, course, module, lesson) brings it to 5, and all 424 chunks of the real course were checked byte-identical before and after. `create_app` went from 95 to 75 lines (support services and the router list moved out of the lifespan). The coding helper's `show_result` (nesting depth 5) became one renderer per task, with new tests for the example and practice-question paths (file coverage 69% → 95%).
  - **Kept, with reasons:** `wait_until_idle`, `course_size` and `FakeChatModel.push` are small documented hooks only tests use. Unused-but-required arguments: the `user` login dependency on endpoints, exception-handler and protocol signatures, uniform renderer tables. `create_app`'s 8 parameters are optional keyword-only test injection points; `upload_document` (7) takes FastAPI dependencies; the `EmbeddingClient` constructor (7) is keyword-only with two test hooks; `ApiClient` has one method per endpoint (26); two short loops nest 4 deep (retrieval evaluation, the one-off backfill script).
  - **Result:** all 836 tests pass locally (219 database-backed, 617 others), coverage 98%. **CI for `28e6fb7` was still running when this was written** (its test step takes about 30 minutes); Render deploys the API only once it passes.
- **LearnX-style frontend (2026-11-20, your request, after Step 21).** The Streamlit frontend now follows the LearnX platform's design (from the saved LearnX lesson pages): restyled Streamlit (your choice over a React rebuild), no backend change.
  - **Rail:** only Arc (the assistant chat) and LearnX (courses), plus Settings (Manage courses) for admins; Circle, Campus and Launch are left out. A top bar holds the page title and a profile menu (level, log out).
  - **LearnX:** course cards → course page (modules with mastery, "what to do next") → lesson tabs Reading (numbered stages from the course JSON), Practice (exercises + compiler panel), Code (coding helper) and Quiz & activities (platform links, Step 17). The old Courses, Practice, Coding helper and My progress pages are folded into it.
  - **Theme:** LearnX `--ax-*` colours for light and dark in `.streamlit/config.toml`, Inter and JetBrains Mono from Google Fonts. Streamlit has no in-page theme toggle; users switch at the top of the ⋮ menu.
  - **Known limits:** the rail is CSS over Streamlit's sidebar markup, which may need adjusting when Streamlit is upgraded (version pinned); flowcharts stay as Mermaid source.
  - **Checked in a browser (local API + Neon dev, dev test admin), light and dark:** rail, top bar, profile menu, course list, course page, lesson stages, Practice tab, and one Arc question with sources. Fixes from this check: header overlap, repeated objective, squeezed "Open" button, message order in Arc.
- **Step 21 decisions (2026-11-20).**
  - **Deployment was already live** from Step 6 (Render auto-deploys `main` after CI passes; Streamlit Cloud redeploys on push), so this step re-checks it rather than redeploying. `render.yaml` now pins `GEMINI_MODEL=gemini-3.5-flash-lite` (the model the evaluations measured) and declares `PLATFORM_LESSON_URL` as an optional dashboard value.
  - **Checked from a fresh browser (2026-11-20):** the Streamlit app is public (sleep page, then the login form after about 50 s; no menu before login). API cold start **58 s** for `/health` after idle; warm 0.1–0.2 s.
  - **Production evaluation through the API** (`eval/run_live_eval.py`, logic in `app/evaluation/live.py` and `live_api.py`): 20 cases (10 covered, 4 out-of-course, 3 follow-up chats, 3 solution requests), 23 questions at 4 a minute (the API allows 5 per student). Scored from responses only, no LLM judge, to save the shared quota; correctness stays measured offline (Step 12). Credentials are prompted (password hidden) and never printed or saved; https only.
  - **Your part (security):** I can't enter production passwords or create production accounts, so you upload the course (admin), register the evaluation student and run the script, and make the backup recording (kept outside the repository). Steps in `docs/deployment.md` §5.
- **Step 20 decisions (2026-11-19).**
  - **Sign-in protection:** after 5 wrong passwords for a username in 15 minutes, that username gets 429 with `Retry-After` (other accounts unaffected); app-wide caps of 60 sign-ins and 20 registrations a minute (`app/auth/limits.py`). Per username, not per IP: behind Render's proxy the client IP is not trustworthy without extra setup.
  - **Quotas stay in process memory** (`app/core/quota.py`, one Render instance; reset on restart). A shared store would need Redis, which the ₹0 budget rules out. The plan's `app/core/ratelimit.py` is that existing module.
  - **Uploads:** `POST /admin/documents` without a bearer token is refused (401) before the body is read; students still get 403 after authentication.
  - **Database connection:** `/code/run` commits before the runner call, like `/chat/ask`.
  - **Chat retention:** chats untouched for `CHAT_RETENTION_DAYS` (90) are deleted when their owner lists chats (no scheduler on the free tier).
  - **Caching:** the course list, course and lesson responses are cached for `CONTENT_CACHE_SECONDS` (600) and cleared by any admin upload or delete; question embeddings are cached in memory (512 entries), so repeated questions and evaluation runs spend less of the daily embedding quota. Answers are not cached (they depend on the chat and the student's level).
  - **Errors:** AI timeouts are now 504 (were 503). The full status table is in the README ("Errors"). The quiz-platform failure case is dropped (Step 17: no quiz platform API).
  - **Done-when result (2026-11-19):** `tests/api/test_failures.py` simulates AI timeout (504), provider down or out of quota (503), embedding failure (503), unusable reply (502), our AI quota (429 + `Retry-After`), code runner down (503), oversized body (413), token-less upload (401) and account lockout (429); none leaks provider details. `tests/api/test_privacy.py`: another student's chat is 403 for read, follow-up and delete; attempts and progress are per student; students get 403 on admin endpoints and 422 when setting their own role; logs hold no question text, code, passwords or tokens; old chats are purged; admin deletes clear the content cache.
- **Step 19 decisions (2026-11-19).**
  - **Pages:** Courses, Ask the assistant, Practice, Coding helper, My progress, and (admins only) Manage courses, through `st.navigation` with the menu built from the user's role (`frontend/menu.py`). The account (log out, level) is in the sidebar (`components/account.py`).
  - **"Takes a quiz"** became: the student sees the lesson's quiz and activities and opens them on the learning platform (your Step 17 decision); links appear once `PLATFORM_LESSON_URL` is set.
  - **Page scripts in `frontend/views/`, not `pages/`** (the plan's name): the browser check found that before login Streamlit auto-listed a `pages/` folder, showing every page, admin included, to anyone. Renamed; a test checks there is no `pages/` folder.
  - **Admin hidden three ways:** not in a student's navigation (unreachable), the admin page checks the role, and the API returns 403.
  - **Friendly errors:** 429 says when to retry; any 503 gets a fixed "busy or starting up" message (5xx bodies are never shown).
  - **Testing note:** AppTest re-runs only the current page after the first run, so the sidebar (drawn by the entry point) is tested on its own with `AppTest.from_function`.
  - **Done-when result (2026-11-19, local API + Neon dev + Gemini, in a browser), student part:** logged in (menu without admin pages), asked "What is an array in JavaScript?" (cited answer, Array Basics activities listed), followed up "How do I loop over it?" (answered about loops over arrays, cited the loop lessons), ran the Array Basics bug hunt, asked the AI (hints only), submitted it (graded "Not yet" with a hint), and My progress recommended reviewing Array Basics first, then the next Arrays lessons. **Admin part (with your approval, a local test admin `devadmin` on Neon dev):** the admin menu showed Manage courses; a small demo course (`demo-js`, 4 lessons; uploaded through the same API call the page makes, since the built-in browser cannot pick files) reached `ready` in about a minute; deleting it from the page removed it and left `javascript-beginner-v1` untouched. Fixes from this check: the delete confirmation now survives the page rerun, and the uploader is capped at 10 MB like the API.
- **Step 18 decisions (2026-11-19).**
  - **Mastery from exercise attempts only** (quiz scores live on the platform; asking questions in the chat is not treated as weakness). Exercise score weights attempts 1, 1/2, 1/4... newest first (no clock, deterministic); lesson = mean of attempted exercises (`None` = not started, not 0%); module = mean of started lessons plus coverage.
  - **Weak** = below `WEAK_MASTERY_THRESHOLD` (0.6). **Recommendations** (max 5): weak lessons weakest first with the exercises still under the threshold, then the not-started lessons after the furthest one worked on; each with its platform practice. `course_id` defaults to the most-attempted course, then the first course.
  - **API only** (`/me/progress`, `/me/recommendations`, caller's own data only); the pages come in Step 19.
  - **Done-when result:** on the real course, a seeded student who passes modules 1-3 and fails module 4 gets 5 Arrays reviews first, each with its three exercises at 0% and its quiz; progress shows Arrays 0%, Variables 100%, untouched modules not started (`tests/api/test_progress.py`). Scoring rules: `tests/learning/test_progress.py`.
- **Step 17 revised (2026-11-19, your decision).** Quizzes, drag and drop, card matching and code reordering run on the learning platform; the assistant points to them instead of rebuilding them. The external quiz platform API and AI-generated quizzes are dropped (the "quiz platform JSON" pending input is closed).
  - **Practice pointers:** ingestion stores each lesson's activities as names and sizes only (`lessons.content["practice"]`); chat answers and coding responses list the cited lessons' activities (`practice`), linked when `PLATFORM_LESSON_URL` (https, with `{lesson_id}`) is set. `scripts/backfill_practice.py` adds them to courses uploaded earlier (run on Neon dev: 64 lessons).
  - **"Quiz me" requests** get a pointer to the lessons' activities (outcome `practice`, no LLM call) instead of questions written into the chat.
  - **Exercise attempts:** `POST /exercises/{id}/attempts` grades a bug hunt, challenge or interactive exercise with the AI (reference shown to the model only; feedback quoting a reference line or containing code is replaced by a generic hint) and stores pass/fail + feedback (migration `0006`, not the code). `GET` lists your own attempts. The compiler panel has "Submit for grading".
  - **Live check (2026-11-19, Neon dev + `gemini-3.5-flash-lite`):** "Quiz me on let and const" pointed to Declaring Variables (quiz 10, drag and drop 6, card matching 6, code reordering 6) with no LLM call; a normal answer listed the same lesson's activities; the bug hunt's buggy code failed with a hint and the fixed code passed; both attempts were stored.
  - **For Step 18:** quiz and activity scores live on the platform; recommendations here use chat topics, coding help and exercise attempts unless the platform shares scores later.
- **Step 16 decisions (2026-11-19).**
  - **Profile level:** `users.level` (migration `0005`, default `beginner`, checked to the three values). `PATCH /auth/me {"level"}` changes only the caller's own level; any other field (e.g. `role`) is a 422. The Streamlit account area has an "Explanation level" selector.
  - **Per-request override:** optional `level` on `/chat/ask` and `/coding/*`; otherwise the profile's level. Follow-up rewriting is unaffected.
  - **Shared templates:** `app/llm/prompt_levels.py` (one guidance text per level). It is appended after each prompt's rules and states that the rules still apply; tests check every rule survives at every level. "Beginner-friendly" wording moved out of the base prompts into the beginner level.
  - **Evaluations stay comparable:** the services default to `beginner`, so the Step 11-14 scripts (which pass no level) measure the same prompts as before.
  - **Done-when result (2026-11-19, `gemini-3.5-flash-lite`, `eval/reports/levels-2026-11-19.md`):** the same closure explained at each level: beginner 236 words with analogies and every term defined; intermediate 197 words with a common pitfall; advanced 158 words on lexical environments and execution contexts. Re-run with `python eval/run_level_demo.py` (3 LLM calls, no embeddings).
- **Step 15 decisions (2026-11-19).**
  - **Editor:** `st.text_area`, not `streamlit-ace` (last release 2021-12, bundles an old Ace). No third-party JavaScript, and the panel stays testable with AppTest. No syntax highlighting while typing.
  - **"Open in Wandbox" became "Open in Compiler Explorer"** (`/code/share`; C, C++, Java, Python; the link is public and the UI says so). Wandbox was dropped in Step 7.
  - **Host page:** a minimal Practice view (course, lesson, exercise) in `frontend/components/practice.py`; full lesson pages are Step 19.
  - **DOM sandbox:** student code runs in a nested iframe with `sandbox="allow-scripts"` only (Streamlit's own component iframe has `allow-same-origin`), under a CSP with `default-src 'none'`; code and markup are posted in as data. The course's DOM exercises ship no HTML, so elements for the selectors the code uses are created automatically.
  - **Pasted output:** `run.outcome` is optional in `/coding/debug`; pasted output is labelled "outcome unknown".
  - **Robustness fix:** related lessons are optional. If the embedding call fails (e.g. daily quota), `/coding/*` answers without them instead of failing with 503.
  - **Done-when result (2026-11-19, local API + Neon dev + `gemini-3.5-flash-lite`, in a browser):** a student opened the "Declaring Variables" bug hunt with its starter code, ran it (Judge0: `TypeError: Assignment to constant variable.`), and got a hints-only AI explanation (no corrected code). In the DOM lesson's sandbox, code trying to read the parent page, cookies, storage and the network got `SecurityError` / blocked for all four. A local test account `devstudent` was created on the Neon dev database for this check.
- **Step 14 decisions (2026-11-19).**
  - **Endpoints:** `/coding/explain`, `/coding/debug` (optional `run` = the `/code/run` result, last 4 KB of each stream used), `/coding/example`, `/coding/practice` (hints and expected output, never solutions). Code up to 8 KB / 200 lines (the runner allows 20 KB, too long to explain line by line).
  - **Exercise solutions stay hidden:** `/debug` compares the code with the course's bug hunts and mini challenges in that language (whitespace-insensitive similarity >= 0.8, measured on the 64 JavaScript bug hunts) and switches to hints only with `corrected_code` forced to null. **Known limit:** a heavily rewritten copy is not recognised; the prompt's hints-only rule for exercises is then the only guard.
  - **JSON:** each task has a response schema (`app/coding/schemas.py`); an unusable reply is retried once, then 502. Line numbers outside the code are dropped and long text is trimmed server-side.
  - **Related lessons:** found from the model's `concepts` (one embedding per request), up to 3 distinct lessons above `RAG_MIN_SCORE`.
  - **Shared AI budget:** chat and coding use one LLM client and one quota (`CHAT_QUESTIONS_*`), owned by `create_app`. Provider errors map to 429/502/503 in one place (`app/api/ai_errors.py`).
  - **Done-when result (2026-11-19, `gemini-3.5-flash-lite`, `eval/reports/coding-2026-11-19.md`):** bugs identified 18/18 (100%, target >= 80%), every language 3/3; JSON validation 100%; the 3 JavaScript course bug hunts were recognised as exercises (hints only). Caveat: the snippets are classic beginner bugs written for this check, so real student code will score lower.
  - **Evaluation:** `eval/code_cases.jsonl` (18 snippets, 3 per language; JavaScript = course bug hunts mod-1 lesson 1, mod-2 lesson 3, mod-4 lesson 4) and `eval/run_code_eval.py`. Identified = an issue within one line of the known bug that names a keyword. A live probe on 2026-11-19 (`gemini-3.5-flash-lite`) found the Python off-by-one on its exact line with valid JSON.
- **Step 13 — chat retention (owner: maintainer, Step 20).** Chats are kept until the student deletes them. Add an age limit (e.g. 90 days) and count chats against the free-tier storage budget. **Resolved in Step 20:** `CHAT_RETENTION_DAYS` (90), purged when the owner lists chats.
- **Step 12 — Gemini availability (owner: you, watch).** On 2026-11-19 `gemini-3.8-flash` returned 504 or hung for minutes, and `gemini-3.5-flash` returned 503 (high demand); the `-lite` models answered in about 1 s. The same day, repeated evaluation runs used up the daily embedding quota (resets at midnight Pacific), so the API key shared with production could not embed questions until then. Keep evaluation runs to one or two a day.

## Pending inputs

> **Deferred (2026-11-20, your decision):** the Done-when verifications for Steps 21 and 22 are postponed until you are ready (the items marked Step 21 / Step 22 below). The code and docs for both steps are done and pushed.

- [x] ~~Quiz platform JSON and API details~~: not needed; Step 17 points to the platform's activities instead (2026-11-19).
- [x] Step 19 admin demo: done on 2026-11-19 with a local test admin (`devadmin`, created on the Neon dev database with your approval; credentials kept outside the repo).
- [x] Steps 12 and 13 Done-when checks: passed on 2026-11-19 (`eval/reports/retrieval-2026-11-19-gemini.md`, `answers-2026-11-19-gemini.md`).
- [x] Step 6 cold-start check: 58 s on 2026-11-20 (recorded in `docs/deployment.md`).
- [ ] Step 21: upload `javascript-beginner-v1` to production (admin, Settings in the rail), if not loaded yet.
- [ ] Step 21: register an evaluation student, run `eval/run_live_eval.py` against production at least a few hours before the demo, and commit `eval/reports/production.{md,json}`.
- [ ] Step 21: record the backup demo (script in `docs/deployment.md` §5) and note where the video is kept in `eval/reports/production.md`.
- [ ] Step 23b: test it later (your decision, 2026-11-20): apply migration 0008 (any local run or deploy), Settings → Course features → Spaced review on, then as a student fail an exercise; about 24 hours later the lesson is under "Due for review" and not repeated in "What to do next". Production needs the switch turned on per course after deploy.
- [ ] Step 23a: test it later (your decision, 2026-11-20): Settings → Course features on, ask Arc, Open in Practice lands on the lesson's Practice tab; production needs the switch turned on per course after deploy.
- [ ] Step 22: once the two Step 21 items above exist, change their "pending" rows in the README's Deliverables table and the Production section of `docs/evaluation.md`.
- [ ] Step 6 memory reading: Render → archintx-api → Metrics had no data right after the first deploy; record the peak once available (expected well under 512 MB; local ~70 MB).
