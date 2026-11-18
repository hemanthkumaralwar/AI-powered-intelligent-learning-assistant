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

## 4. Check it works (Step 6 done-when)

- [ ] The public Streamlit URL logs in with the admin account (or a student registered through the API's `/docs`).
- [ ] `https://…onrender.com/health` responds after a cold start (wait 15+ minutes, then load it; the first response may take up to a minute).
- [ ] Render → service → **Metrics** → memory stays well under 512 MB. Locally the API uses about **70 MB** (measured 2026-11-18 on Windows with Python 3.12).

## Cold starts and the demo

There is **no keep-alive** (decided in Step 6), so:

- **Before a demo:** open `…/health`, then log in once in the Streamlit app, about 2 minutes before you start. That wakes both Render and Supabase.
- **If Supabase paused** after a quiet week: Supabase dashboard → your project → **Restore**. It takes a few minutes, and the data is kept.
- The frontend waits up to 60 s and shows "The server is waking up…" instead of an error, so a cold start looks like a pause, not a crash.

## Running locally

```bash
.venv/Scripts/uvicorn app.main:app --app-dir backend --loop asyncio:SelectorEventLoop
```
```bash
API_BASE_URL=http://127.0.0.1:8000 .venv/Scripts/streamlit run frontend/streamlit_app.py
```
