# Testing and quality checks

## Commands

```bash
ruff check .
ruff format --check .
pytest
pip-audit -r requirements.txt -r requirements-dev.txt -r frontend/requirements.txt
```

GitHub Actions ([.github/workflows/ci.yml](../.github/workflows/ci.yml)) runs all four on every push to `main` and every pull request, plus a check that the production install contains no `torch`. Render deploys a commit only after CI passes (`autoDeployTrigger: checksPass`).

| Check | Standard |
|---|---|
| `ruff check` | PEP 8 (E, W), pyflakes (F), import order (I), naming (N), bugbear (B), modern syntax (UP), simplifications (SIM), bandit security rules (S), and cyclomatic complexity at most **10** per function (C90). Config: `[tool.ruff]` in `pyproject.toml` |
| `ruff format` | formatting, 100-character lines |
| `pytest` | fails if coverage of `backend/app` + `frontend` drops below **80%** (currently 98%) |
| `pip-audit` | no known vulnerabilities in any pinned dependency |

## Test layout

`tests/` mirrors `backend/app/` (one folder per package: `api/`, `auth/`, `rag/`, `runner/`…), plus `tests/frontend/` for the Streamlit app and `tests/docs/` for documentation drift. Tests run in importlib mode, so test folders need no `__init__.py` (and test modules cannot import each other; shared fixtures live in `conftest.py`).

| Kind | How |
|---|---|
| Unit | pure logic (chunking, citations, quotas, mastery, scoring) with injected clocks and fakes; no network |
| Provider adapters | Gemini, OpenAI and Hugging Face adapters against stub SDK clients (shaped like the real responses); retries and error mapping with a fake clock |
| Database | real PostgreSQL: each run migrates a brand-new `test_<random>` schema on the Neon `test` branch and drops it afterwards. Without `TEST_DATABASE_URL` these tests are **skipped**, not failed |
| API | the whole app in-process (`httpx2.ASGITransport`) with scripted fake providers |
| Frontend | Streamlit's `AppTest` against a tiny fake API on localhost; widgets drawn by the entry point (profile menu) are tested on their own with `AppTest.from_function`, because AppTest re-runs only the current page after the first run |
| Docs | `tests/docs/test_docs.py`: every API route is listed in [api.md](api.md); every setting is in the README's configuration table and in `.env.example` |

## Fakes, not mocks

External services are replaced at their interface, never by patching internals:

- `LLM_PROVIDER=fake` / `FakeChatModel` (scripted replies and errors), `EMBEDDING_PROVIDER=fake`, `CODE_RUNNERS=fake` / `FakeRunner`. All three are **refused in production** by the settings validator.
- `create_app()` accepts injected services (database, auth, indexing, answers, coding, grader, code runner); tests pass their own, production builds the real ones.

## Suites worth knowing

| File | Proves |
|---|---|
| `tests/api/test_failures.py` | AI timeout → 504; provider down or out of quota → 503; embedding failure → 503; unusable reply → 502; our quota → 429 with `Retry-After`; code runner down → 503; oversized body → 413; upload without a token → 401 before the body is read; repeated wrong passwords → 429 for that username only. None leaks provider details |
| `tests/api/test_privacy.py` | another student's chat is 403 (read, follow-up, delete); attempts and progress are per student; students get 403 on admin endpoints and 422 when setting their own role; logs hold no questions, code, passwords or tokens; old chats are purged; admin deletes clear the content cache |
| `tests/ingestion/test_chunking.py` | sentinel values planted in every answer field (quiz answers, fixes, solutions) never reach a chunk; chunk ids are stable |
| `tests/rag/` | grounding rules, server-built citations (fake markers dropped), refusal below the threshold, follow-up rewriting, prompt-injection neutralising |
| `tests/coding/`, `tests/learning/` | hints-only for course exercises, grading leak guard, mastery and recommendations |
| `tests/frontend/` | login, profile menu, the navigation per role (no admin page for students), LearnX course → lesson tabs and course outline, the compiler panel, the DOM sandbox, Nexus chats and the Past chats panel, guest browsing |

## Manual smoke tests (real providers, use quota)

```bash
python scripts/llm_smoke.py           # the configured chat model answers
python scripts/embedding_smoke.py     # the configured embedding model answers
python scripts/code_runner_smoke.py   # ~30 small programs on Judge0 / Compiler Explorer
```

Run `code_runner_smoke.py` before a demo: the runners are free community services without an SLA.

Model quality is measured separately, with the evaluation scripts: see [evaluation.md](evaluation.md).
