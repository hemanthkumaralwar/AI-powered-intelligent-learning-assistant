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

## Project layout

```
backend/app/        FastAPI application (package "app")
  main.py           entry point: create_app()
  api/              HTTP routers
  core/             configuration, logging, error handling
tests/              mirrors backend/app/
```
