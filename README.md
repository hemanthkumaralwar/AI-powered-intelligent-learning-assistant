# ArchintX AI-Powered Intelligent Learning Assistant

A learning assistant for the ArchintX platform. It shows courses as staged lessons, and it helps signed-in students with:

- **Nexus**, a course assistant that answers questions **from the uploaded course material** (retrieval-augmented generation, RAG). Every answer cites the lesson it came from, follow-up questions keep their context, and when the course doesn't cover something Nexus says so instead of guessing.
- **A coding assistant** for Python, C, C++, Java, SQL and JavaScript: explain code line by line, find bugs, show examples, write practice questions, and run code.
- **Practice and progress**: AI-graded exercises, a lesson quiz, and recommendations for which lesson to review next.

Anyone can browse the courses and read lessons without an account.

## Try it online (nothing to install)

| | |
|---|---|
| Live app | https://ai-powered-intelligent-learning-assistant.streamlit.app/ |
| Live API and its interactive docs (Swagger) | https://archintx-api-kday.onrender.com/docs |

The API runs on a free server that sleeps after 15 minutes without visitors. **The first page load after a quiet spell can take about a minute.** If you see "The server is waking up", wait a minute and try again.

## Documentation

| Document | What's in it |
|---|---|
| [docs/architecture.md](docs/architecture.md) | how it's built: components, the RAG pipeline, data, security and privacy, changes from the brief, limitations |
| [docs/api.md](docs/api.md) | every API endpoint, who may call it, errors and quotas |
| [docs/evaluation.md](docs/evaluation.md) | how answer quality was measured, and the results |
| [docs/testing.md](docs/testing.md) | the automated tests and checks |
| [docs/deployment.md](docs/deployment.md) | putting it online for free (Render, Supabase, Streamlit Cloud), plus a demo script |
| [PLAN.md](PLAN.md) | the build plan and every decision, with dates |

---

## Run it on your own computer

Follow the steps in order. Plan for **about 45 minutes** the first time, most of it waiting for downloads. Everything used here is free.

**Words used below:**

- **Terminal**: the window where you type commands. On Windows, open **PowerShell** (Start menu → type "PowerShell"). On macOS, open **Terminal**.
- **Repository folder**: the `AI-powered-intelligent-learning-assistant` folder you download in step 2. Run every command from inside it.
- **Virtual environment (venv)**: a private folder of Python packages for this project, so it doesn't clash with anything else on your computer.
- **API** (or backend): the server that does the work. **Frontend**: the web page you click around in. You run both, each in its own terminal.

### Step 1. Install the tools and create two free accounts

| You need | How to get it | Check it worked |
|---|---|---|
| **Python 3.12** | https://www.python.org/downloads/ (pick a 3.12.x release). On Windows, tick **"Add python.exe to PATH"** on the first installer screen. | `python --version` prints `Python 3.12.…` (on macOS: `python3 --version`) |
| **Git** | https://git-scm.com/downloads (default options are fine) | `git --version` prints a version |
| **A Neon account** (free PostgreSQL database) | https://neon.tech: sign up, create a project | you can see the project dashboard |
| **A Gemini API key** (free AI model) | https://aistudio.google.com: sign in with a Google account → **Get API key** → **Create API key** | you have a long key; keep it private |
| About **3 GB of free disk space** | | |

Close and reopen your terminal after installing Python and Git, so it finds them.

### Step 2. Download the code

**Windows:** use a short folder path such as `C:\dev`. Some packages have very long file names, and installs fail past Windows' 260-character path limit.

```powershell
mkdir C:\dev
cd C:\dev
git clone https://github.com/hemanthkumaralwar/AI-powered-intelligent-learning-assistant.git
cd AI-powered-intelligent-learning-assistant
```

On macOS or Linux, clone into any folder, then `cd AI-powered-intelligent-learning-assistant`.

### Step 3. Create the virtual environment and install packages

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell says *running scripts is disabled on this system*, run this once, then try `Activate.ps1` again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt now starts with `(.venv)`. **Every time you open a new terminal for this project, activate the venv again** with the same command; most "No module named …" errors mean you forgot.

Then install everything (the first time downloads several hundred MB and can take 10 minutes or more):

```bash
pip install -r requirements.txt -r requirements-dev.txt -r frontend/requirements.txt
```

### Step 4. Get your database address from Neon

1. In your Neon project, open **Connect** (or **Connection details**) on the dashboard.
2. Choose the **direct** connection, not the pooled one: **turn off "Connection pooling"**. The address must **not** contain `-pooler`.
3. Copy the connection string. It looks like `postgresql://user:password@ep-something.region.aws.neon.tech/neondb?sslmode=require`. It must end with `?sslmode=require` (other options after it, such as `&channel_binding=require`, are fine).

### Step 5. Create your settings file (`.env`)

Copy the example file:

```powershell
copy .env.example .env
```

(macOS / Linux: `cp .env.example .env`.)

Make a random secret for signing log-ins, and copy what it prints:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Open `.env` in any text editor (Notepad is fine) and fill in these lines. Leave everything else as it is.

| Line in `.env` | What to put |
|---|---|
| `DATABASE_URL=` | the Neon address from step 4 |
| `JWT_SECRET_KEY=` | the random secret you just printed |
| `GEMINI_API_KEY=` | your Gemini key from step 1 |
| `ADMIN_USERNAME=` | a name for your admin account, e.g. `admin` |
| `ADMIN_PASSWORD=` | a password of **12 or more** characters |

Write no quotes and no spaces around `=`, for example `ADMIN_USERNAME=admin`. Save the file.

> **Keep `.env` private.** It holds your keys. Git already ignores it, so it is never uploaded; don't paste it anywhere.

### Step 6. Create the database tables

```bash
alembic upgrade head
```

It prints a few `Running upgrade …` lines and returns to the prompt. Errors here almost always mean a wrong `DATABASE_URL`: see [Troubleshooting](#troubleshooting).

### Step 7. Start the API (terminal 1)

```bash
uvicorn app.main:app --app-dir backend --loop asyncio:SelectorEventLoop
```

Wait for `Application startup complete`, then open http://127.0.0.1:8000/health in your browser. It should show `{"status":"ok"}`. The interactive API docs are at http://127.0.0.1:8000/docs.

**Leave this terminal open.** The API stops when you close it or press `Ctrl+C`. (The `--loop` part is needed on Windows and does no harm elsewhere.)

### Step 8. Start the frontend (terminal 2)

Open a **second** terminal, go to the repository folder, and **activate the venv again** (step 3). Tell the frontend where the API is, then start it:

**Windows:**

```powershell
copy frontend\.streamlit\secrets.toml.example .streamlit\secrets.toml
streamlit run frontend/streamlit_app.py
```

**macOS / Linux:**

```bash
cp frontend/.streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run frontend/streamlit_app.py
```

Your browser opens http://localhost:8501. If it doesn't, open that address yourself. (If Streamlit asks for an email address on its first run, just press Enter.)

### Step 9. Load the course (as admin)

1. In the app, click **Sign in** and log in with the `ADMIN_USERNAME` and `ADMIN_PASSWORD` from your `.env`.
2. Open **Settings** in the links at the top (or go to http://localhost:8501/admin).
3. Upload `eval/materials/javascript-beginner.json` (it's in the repository folder) as the JavaScript course.
4. Press **Refresh** every minute or so until the status says `ready`. This takes **about 5 minutes**: the course is split into 424 pieces, and each is sent to Gemini at the free tier's pace.

Courses are uploaded as course JSON files. Course material in PDF, DOCX or TXT is converted to course JSON by a separate converter project before upload.

### Step 10. Create a student account

The app has no sign-up page yet, so you create students through the API docs page:

1. Open http://127.0.0.1:8000/docs.
2. Find **`POST /auth/register`**, click it, then click **Try it out**.
3. Replace the example in the box with your own details and click **Execute**:

   ```json
   {
     "username": "student1",
     "password": "a-password-you-choose"
   }
   ```

   Usernames are 3–50 characters: lowercase letters, digits, `.`, `_` or `-`. Passwords need 8 or more characters.
4. A response code of **201** means it worked. **409** means the username is taken; pick another.

### Step 11. Try it

Log out of the admin account, sign in as your student, and:

1. Open **LearnX** → the JavaScript course → any lesson, and read through the stages.
2. Open the lesson's **Ask Nexus** tab and ask *"What is an array in JavaScript?"*. The answer cites a lesson.
3. Follow up with *"How do I loop over it?"*. Nexus remembers you were talking about arrays.
4. Ask *"How do React hooks work?"*. Nexus says the course doesn't cover it.
5. Open **Practice**, run the bug hunt, ask the AI for a hint, and submit your fix for grading.
6. Take the lesson quiz in **Quiz & activities**, then go back to the course page to see **what to do next**.

### Next time

You only need two terminals, each with the venv activated (step 3):

```bash
uvicorn app.main:app --app-dir backend --loop asyncio:SelectorEventLoop
```

```bash
streamlit run frontend/streamlit_app.py
```

The course and accounts stay in your Neon database. To get new code later, run `git pull`, then `pip install -r requirements.txt -r requirements-dev.txt -r frontend/requirements.txt` and `alembic upgrade head` again.

### Trying it without any AI key

To click around without Gemini, set these in `.env` and restart the API:

```
LLM_PROVIDER=fake
EMBEDDING_PROVIDER=fake
CODE_RUNNERS=fake
```

The assistant then gives canned replies, which is enough to see how every screen works. You still need the database (steps 4–6).

### Troubleshooting

| What you see | What to do |
|---|---|
| `'python' is not recognized` | Python isn't on your PATH. Reinstall it and tick **"Add python.exe to PATH"**, then open a new terminal. On macOS use `python3`. |
| `running scripts is disabled on this system` | Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` once (step 3). |
| `No module named …`, or `uvicorn` / `streamlit` / `alembic` not recognized | The venv isn't active in this terminal. Activate it (step 3). If it still fails, rerun the `pip install` line. |
| pip fails with `No such file or directory` on Windows | The folder path is too long. Clone into a short path like `C:\dev` (step 2) and start again. |
| `alembic upgrade head` can't connect, or mentions SSL or `pooler` | Check `DATABASE_URL` in `.env`: it must start with `postgresql://`, must not contain `-pooler`, and must end with `?sslmode=require`. |
| The API stops at startup with a settings error | A required line in `.env` is empty or too short: `JWT_SECRET_KEY` needs 32+ characters and `ADMIN_PASSWORD` 12+. The error message names the setting. |
| `address already in use` / port 8000 or 8501 busy | The API or frontend is already running in another terminal. Use that one, or close it first. |
| The app says "Cannot reach the server" | The API isn't running. Start it (step 7), and check `.streamlit/secrets.toml` exists (step 8). |
| Questions fail with a 503 error, or the course stays `pending` | Gemini's free daily limit is used up. It resets at midnight Pacific time; indexing then carries on by itself. |
| Questions fail with a 429 error | You hit the app's own limit (5 questions a minute per student). Wait a minute. |

Still stuck? Open an issue on the GitHub repository with the full error message, but **never include your `.env` contents or keys**.

---

## Using the app

The frontend follows the LearnX platform's look: page links at the top, a top bar with the page title and a profile menu (explanation level: beginner, intermediate or advanced; log out), an open lesson's course outline in a sidebar you can hide, previous/next arrows beside the lesson title, and light and dark colours (switch at the top of Streamlit's ⋮ menu).

| Page | For | What it does |
|---|---|---|
| **LearnX** | everyone; no account needed to read | courses → a course's modules → a lesson with **Reading** (numbered stages: mission, brief, concepts, analogy, syntax, examples, flow, real world, recap) and **Quiz & activities** (the platform's activities). Signed in, you also get **Ask Nexus** (the course assistant: answers with citations, follow-ups, and a **Past chats** panel), **Practice** (the lesson's exercises in a code editor: run, ask the AI about the output, submit for grading), **Code** (explain code, show an example, practice questions), the **lesson quiz** (marked on submit, with the right answers and explanations; retakes allowed), and on the course page your mastery and **what to do next** |
| **Sign in** | guests | the login form (accounts are created through the API for now) |
| **Settings** (`<app URL>/admin`) | admins only | upload course JSON, indexing status, delete a course, re-index |

- **Code runs remotely,** never on the server: Judge0 CE, with Compiler Explorer as fallback (and **Open in Compiler Explorer** for a public share link). JavaScript that uses the page (`document`, `window`) runs in a locked-down frame in your browser.
- **Exercise solutions stay hidden:** the assistant gives hints for exercises, never the fixed code.
- **Reloading the browser signs you out:** the log-in token lives only in Streamlit's server-side session, never in the browser.

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
- **Retries and limits:** timeouts, server errors and rate limits are retried with backoff (1, 2, 4… s, up to 20 s); bad keys and invalid requests are not. Embeddings are paced to the free tier (80 indexing + 20 question texts a minute, separate budgets).
- **Privacy:** on Gemini's free tier, Google may use what you send to improve its products. Prompts never include personal details; prompts, answers and code are never logged.

## Database

| Environment | Database | URL to use |
|---|---|---|
| Development | Neon branch `dev` | **direct** connection string (not `-pooler`), `?sslmode=require` |
| Tests / CI | Neon branch `test` (`TEST_DATABASE_URL`) | direct; each test run creates and drops its own `test_<random>` schema |
| Production | Supabase | **session pooler** (port 5432 on `pooler.supabase.com`; works over IPv4 from Render) |

Avoid transaction poolers (Neon `-pooler`, Supabase port 6543): migrations and per-session settings need a real session.

```bash
alembic upgrade head          # bring the database in DATABASE_URL up to date
alembic upgrade head --sql    # print the SQL without connecting, for review
alembic downgrade -1          # undo the last migration
```

Render runs `alembic upgrade head` on every deploy. Every table has Row Level Security enabled with no policies, so Supabase's public `anon` key reads nothing; turning off Supabase's Data API as well is recommended.

## Deployment

Render (API), Supabase (database) and Streamlit Community Cloud (frontend), all free, no Docker: see **[docs/deployment.md](docs/deployment.md)**.

## Running the tests

With the venv active, from the repository folder:

```bash
ruff check .
ruff format --check .
pytest
pip-audit -r requirements.txt -r requirements-dev.txt -r frontend/requirements.txt
```

| Command | What it checks |
|---|---|
| `ruff check .` | code style and common mistakes |
| `ruff format --check .` | consistent formatting |
| `pytest` | the automated tests; fails if coverage drops below 80% |
| `pip-audit …` | known security issues in the installed packages |

Database tests are skipped unless `TEST_DATABASE_URL` is set (use a separate Neon branch, never your real data). GitHub Actions runs all four on every push. Details: [docs/testing.md](docs/testing.md).

## Configuration

All settings come from environment variables or `.env`. `.env.example` lists every key. Never commit `.env`. For a local setup you only need the five settings in [step 5](#step-5-create-your-settings-file-env); everything else has a working default.

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
| `DATABASE_URL` | PostgreSQL URL: Neon direct (dev) or Supabase session pooler (prod) | — (required by the API) |
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

Where each grading area of the brief is covered:

| Grading area | Where |
|---|---|
| RAG implementation (20) | [architecture.md › Asking a question](docs/architecture.md#asking-a-question), [› Course ingestion](docs/architecture.md#course-ingestion); `backend/app/{rag,ingestion,indexing}/`; results in [evaluation.md](docs/evaluation.md) |
| Python and backend (15) | `backend/app/`; [docs/api.md](docs/api.md); Swagger at `/docs` (live: https://archintx-api-kday.onrender.com/docs) |
| LLM integration (15) | `backend/app/{llm,providers}/`; [Switching providers](#switching-providers); grounding and citation rules in [architecture.md](docs/architecture.md#asking-a-question) |
| Coding assistant (15) | `backend/app/{coding,runner}/`, `frontend/components/compiler.py`; [api.md › Coding assistant](docs/api.md#coding-assistant); 18/18 bugs found ([evaluation.md](docs/evaluation.md#coding-assistant)) |
| Vector database (10) | `backend/app/vectorstore/` (FAISS) + vectors in Postgres (`chunks`); why FAISS: [architecture.md › Design decisions](docs/architecture.md#design-decisions-changes-from-the-brief) |
| Personalization (10) | `backend/app/learning/` (mastery, recommendations, AI grading), explanation levels (`backend/app/llm/prompt_levels.py`); [architecture.md › Progress](docs/architecture.md#progress-and-recommendations) |
| Testing and documentation (10) | `tests/` (98% coverage), [docs/testing.md](docs/testing.md), CI in `.github/workflows/ci.yml`; evaluation results in [docs/evaluation.md](docs/evaluation.md) and `eval/reports/`; this README and `docs/` |
| Final demonstration (5) | the live app (above); demo script in [deployment.md › Backup recording](docs/deployment.md#backup-recording) |

**Optional extras** (not required by the brief): a backup recording of the demo, as a fallback if the live app is slow to wake, and a production evaluation report (`eval/run_live_eval.py`, which writes `eval/reports/production.md`). Both are described in [docs/deployment.md](docs/deployment.md#5-production-launch-step-21).

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
  learning/         practice pointers, AI grading, lesson quiz, progress, recommendations
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
                    coding helper, progress, practice, quiz, DOM sandbox
  menu.py           which pages each role sees; session.py: client, token and user for pages
eval/               evaluation datasets, scripts (run_eval, run_code_eval, run_level_demo,
                    run_live_eval) and reports/; materials/: the JavaScript course
docs/               architecture, API, evaluation, testing, deployment
scripts/            manual smoke tests (LLM, embeddings, code runner), practice backfill
tests/              mirrors backend/app/, plus frontend/ and docs/
render.yaml         Render blueprint for the API
.streamlit/         Streamlit config (theme, no usage statistics)
```
