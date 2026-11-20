# Deployment (free tier, no Docker)

| Part | Host | Free-tier limits that matter |
|---|---|---|
| API (FastAPI) | **Render** web service, Singapore | 512 MB RAM; sleeps after 15 min idle (first request then takes ~30–60 s); 750 instance-hours/month |
| Database | **Supabase** Postgres | 500 MB; project pauses after ~1 week without database activity |
| Frontend (Streamlit) | **Streamlit Community Cloud** | app sleeps after a long period without visitors (wakes on visit) |

Secrets are only ever entered in each service's dashboard. Never commit them or paste them into issues or chat.

---

## 1. Supabase (database)

1. Create a project at **supabase.com/dashboard** and save the database password.
2. **Connect → Session pooler** (port **5432**, host `...pooler.supabase.com`). Copy the URI, put your password in, and make sure it ends with `?sslmode=require`. This is the production `DATABASE_URL`.
   - Don't use "Direct connection" (IPv6-only on the free plan) or "Transaction pooler" (port 6543).
3. **Project Settings → Data API → turn it off.** The app never uses it, and the first migration already enables Row Level Security on every table as a second layer.

Migrations run automatically on every Render build (`alembic upgrade head`), so there's nothing to run by hand.

## 2. Render (API)

1. Generate a production signing key, and **don't reuse the dev key from `.env`**:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
2. **render.com → New → Blueprint**, connect GitHub, pick this repository. Render reads [`render.yaml`](../render.yaml).
3. Fill in the values Render asks for:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | Supabase session-pooler URL from step 1 |
   | `JWT_SECRET_KEY` | the key you just generated |
   | `GEMINI_API_KEY` | your Google AI Studio key (required: the API embeds courses and questions) |
   | `ADMIN_USERNAME` | your admin login (optional) |
   | `ADMIN_PASSWORD` | 12+ characters (optional; set both admin values or neither) |

4. Apply. The first build installs packages, runs migrations, and starts the API. Your URL looks like `https://archintx-api-xxxx.onrender.com`.
5. Check it in a browser: `…/health` → `{"status":"ok"}`, and `…/docs` shows the API.
6. Once your admin can log in, you may delete `ADMIN_PASSWORD` in **Environment**. Seeding only creates a missing admin and never changes an existing one.

**Deploys:** every push to `main` deploys **only after GitHub Actions passes** (`autoDeployTrigger: checksPass`).

## 3. Streamlit Community Cloud (frontend)

1. **share.streamlit.io → Create app → Deploy a public app from GitHub**:
   - Repository: this repo, branch `main`
   - Main file path: `frontend/streamlit_app.py`
   - **Advanced settings → Python version: 3.12**
2. **Advanced settings → Secrets**, paste:
   ```toml
   API_BASE_URL = "https://archintx-api-xxxx.onrender.com"
   ```
   It must be `https://`. The app refuses plain `http://` except for localhost.
3. Deploy. Streamlit installs [`frontend/requirements.txt`](../frontend/requirements.txt) only (just `streamlit` and `httpx2`).
4. **Make it public.** Apps deployed from a private repo start **private**: visitors are sent to a Streamlit sign-in page. Go to share.streamlit.io → your app → **⋮ → Settings → Sharing → Who can view this app → public**. This controls only who can open the page; the source code stays private on GitHub.

## 4. Check it works (Step 6 done-when)

Results of the first deployment (2026-11-18):

| Check | Result |
|---|---|
| API | `https://archintx-api-kday.onrender.com`: `/health` 200, `/docs` 200, anonymous `/auth/me` 401, bad login 401, invalid input 422 with no echo |
| Frontend | `https://ai-powered-intelligent-learning-assistant.streamlit.app/`: public (anonymous visitors reach the app); admin login showed "Signed in as … (admin)", and log out returned to the form |
| Cold start | **58 s** for `/health` after the API had been idle (measured 2026-11-20, Step 21). Later requests answer in well under a second. |
| Memory | Render Metrics had no data yet right after the first deploy; local measurement ~70 MB (Windows, Python 3.12). Re-check Render → **Metrics** after a day of use; it should stay well under 512 MB. |
| Step 21 re-check (2026-11-20, fresh browser, not signed in to Streamlit) | Frontend still **public**: Streamlit's "app has gone to sleep" page, then the login form after about 50 s; no menu before login. CI passed for the Step 20 commit, which Render then deploys (confirm in Render → **Events**). |

To re-check later:

- [ ] The public Streamlit URL logs in with the admin account (or a student registered through the API's `/docs`).
- [x] `https://…onrender.com/health` responds after a cold start: 58 s on 2026-11-20.
- [ ] Render → service → **Metrics** → memory stays well under 512 MB.

## 5. Production launch (Step 21)

### Load the course

1. Open the Streamlit app and log in as the admin.
2. **Settings** (bottom of the rail): choose `eval/materials/javascript-beginner.json`, programming language JavaScript, **Upload**.
3. Press **Refresh** until its status is `ready` (about 5 minutes: 424 chunks, embedded at the free tier's pace). Students can now ask about it.

Uploading the same course again is refused (409). To replace it, delete it first on the same page.

### Run the production evaluation

Register a student for the evaluation (not the admin, which should not be used for routine checks): open `https://archintx-api-kday.onrender.com/docs` → `POST /auth/register` → **Try it out**, enter a username and password, **Execute** (201). The Streamlit app has no sign-up form. Then, from the repository root:

```bash
.venv/Scripts/python eval/run_live_eval.py --api-url https://archintx-api-kday.onrender.com
```

- It asks for the student's username and password (hidden). Neither they nor the token are printed or saved.
- 20 cases from `eval/dataset.jsonl` (10 covered questions, 4 out-of-course, 3 follow-up chats, 3 exercise-solution requests): 23 questions at 4 a minute, about 6 minutes.
- Scored from the API's responses only: grounded or refused, an expected lesson cited, no solution code, and response times. No LLM judge, to save quota; answer correctness is measured offline in Step 12.
- Writes `eval/reports/production.md` and `.json`. Commit both.
- **Run it at least a few hours before a demo.** It uses the same Gemini key as the app, and the free tier's daily limits are shared.

### Backup recording

Record the demo once, so a cold start or provider outage during the live demo has a fallback. Use **Win+Alt+R** (Xbox Game Bar) or OBS. Keep the video **outside the repository** (it is too large for git), for example in your cloud drive, and note where it is in `eval/reports/production.md`.

Demo script (about 5 minutes; warm up first, see below):

1. **Admin:** log in, open **Settings** (bottom of the rail, or `<app URL>/admin`): the JavaScript course is `ready`. Log out.
2. **Guest, then student:** before logging in, open a course and read a lesson (no account needed); then log in (the rail has only LearnX). Show light and dark from the ⋮ menu.
3. **LearnX:** open the course, then a lesson; scroll through the Reading stages.
4. **Ask Nexus** (a lesson tab): "What is an array in JavaScript?" Show the cited answer and the lesson's activities.
5. Follow up: "How do I loop over it?" The answer stays on arrays.
6. Out of course: "How do React hooks work?" Nexus says the course doesn't cover it.
7. **Lesson → Practice:** run the bug hunt (error shown), ask the AI (hints, no fixed code), submit (graded with a hint).
8. **LearnX course page:** "What to do next" recommends the weak lesson first.

## Cold starts and the demo

There is **no keep-alive** (decided in Step 6), so:

- **Before a demo (warm-up), about 2 minutes before you start:**
  1. Open `https://archintx-api-kday.onrender.com/health` and wait for `{"status":"ok"}` (up to a minute after idle).
  2. Open the Streamlit app and log in once. That also wakes Supabase.
  3. Ask one short question, so the course index and the AI provider are warm.
- **If Supabase paused** after a quiet week: Supabase dashboard → your project → **Restore**. It takes a few minutes, and the data is kept.
- The frontend waits up to 60 s and shows "The server is waking up…" instead of an error, so a cold start looks like a pause, not a crash.

## Running locally

```bash
.venv/Scripts/uvicorn app.main:app --app-dir backend --loop asyncio:SelectorEventLoop
```
```bash
API_BASE_URL=http://127.0.0.1:8000 .venv/Scripts/streamlit run frontend/streamlit_app.py
```
