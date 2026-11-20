"""Step 21: the production evaluation, asked through the live API as a student.

    python eval/run_live_eval.py --api-url https://archintx-api-xxxx.onrender.com

Asks for a student's username and password (hidden). Register that student yourself
first; the password and token are never printed or saved. Run it at least a few hours
before a demo: it asks 23 questions (shared Gemini quota), paced to --per-minute, about
6 minutes. The API URL can also come from LIVE_API_URL.

Writes eval/reports/production.md and production.json.
"""

import argparse
import asyncio
import datetime
import getpass
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx2  # noqa: E402

from app.evaluation.dataset import load_dataset  # noqa: E402
from app.evaluation.live import LiveReport, evaluate, pick_cases, render_markdown, summary  # noqa: E402
from app.evaluation.live_api import (  # noqa: E402
    REQUEST_TIMEOUT_SECONDS,
    LiveApi,
    LiveApiError,
    check_api_url,
)
from app.providers.rate_limit import RateLimiter  # noqa: E402

COURSE_ID = "javascript-beginner-v1"
REPORTS = ROOT / "eval" / "reports"
# The API allows 5 questions a minute per student; stay just under it.
DEFAULT_PER_MINUTE = 4


async def run(api_url: str, username: str, password: str, per_minute: int) -> LiveReport:
    cases = pick_cases(load_dataset(ROOT / "eval" / "dataset.jsonl"))
    timeout = httpx2.Timeout(REQUEST_TIMEOUT_SECONDS)
    async with httpx2.AsyncClient(base_url=api_url, timeout=timeout) as client:
        api = LiveApi(client, RateLimiter(per_minute))
        health = await api.health_seconds()
        await api.login(username, password)
        await api.require_course(COURSE_ID)
        print(f"Asking {len(cases)} cases at {per_minute} questions a minute...")
        results = await evaluate(cases, api.ask)
    run_info = {
        "date": datetime.date.today().isoformat(),
        "api": api_url,
        "course_id": COURSE_ID,
        "health_seconds": health,
        "per_minute": per_minute,
    }
    return LiveReport(results, run_info)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-url", default=os.environ.get("LIVE_API_URL"))
    parser.add_argument("--per-minute", type=int, default=DEFAULT_PER_MINUTE)
    args = parser.parse_args()
    if not args.api_url:
        parser.error("give --api-url or set LIVE_API_URL")
    try:
        api_url = check_api_url(args.api_url)
    except ValueError as exc:
        parser.error(str(exc))
    username = input("Student username: ").strip()
    password = getpass.getpass("Password (hidden): ")
    try:
        report = asyncio.run(run(api_url, username, password, args.per_minute))
    except (LiveApiError, httpx2.HTTPError) as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 1
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "production.md").write_text(render_markdown(report), encoding="utf-8")
    data = {"run": report.run, "summary": summary(report.results)}
    data["results"] = [asdict(result) for result in report.results]
    (REPORTS / "production.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    stats = data["summary"]
    print(f"{stats['passed']}/{stats['total']} passed; report: eval/reports/production.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
