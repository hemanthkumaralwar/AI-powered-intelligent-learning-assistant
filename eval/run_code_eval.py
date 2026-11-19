"""Coding-assistant evaluation (Step 14): runs eval/code_cases.jsonl through /coding/debug.

    python eval/run_code_eval.py

Uses the configured LLM (one call per case, paced to --llm-per-minute; an unusable reply
is retried once, like the API) and DATABASE_URL only to read the course exercises, so
JavaScript bug hunts are checked in hint mode exactly as students get them. Related
lessons are skipped: they would cost an embedding per case and are not scored.

Writes eval/reports/coding-<date>.{md,json}.
"""

import argparse
import asyncio
import datetime
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.coding.service import CodingService  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.quota import Quota  # noqa: E402
from app.db.repositories.courses import CourseRepository  # noqa: E402
from app.db.session import build_database  # noqa: E402
from app.evaluation.coding import (  # noqa: E402
    CodeCase,
    CodeResult,
    coding_summary,
    evaluate_debug,
    render_coding_markdown,
)
from app.evaluation.dataset import load_cases  # noqa: E402
from app.evaluation.pacing import paced_llm  # noqa: E402
from app.rag.retriever import Retriever  # noqa: E402


async def no_search(query: str, k: int, course_id: str | None) -> list:
    return []


async def run(settings: Settings, cases: list[CodeCase], per_minute: int) -> tuple:
    database = build_database(settings)
    llm = paced_llm(settings, per_minute)
    service = CodingService(llm, Quota([]), Retriever(no_search, 1, 1.0))
    try:
        exercise_code: dict[str, list[str]] = {}
        async with database.session() as session:
            for language in {case.language for case in cases}:
                exercise_code[language] = await CourseRepository(session).exercise_code(language)

        async def debug(case: CodeCase):
            return await service.debug(
                "eval", case.language, case.code, None, exercise_code[case.language]
            )

        results = await evaluate_debug(cases, debug)
        return results, llm.model
    finally:
        await llm.aclose()
        await database.dispose()


def write_report(results: list[CodeResult], run_info: dict) -> None:
    out = ROOT / "eval" / "reports" / f"coding-{run_info['date']}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".md").write_text(render_coding_markdown(results, run_info), "utf-8")
    data = {
        "run": run_info,
        "summary": coding_summary(results),
        "results": list(map(asdict, results)),
    }
    out.with_suffix(".json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    s = coding_summary(results)
    print(
        f"coding: identified {s['identified']:.0%}, valid JSON {s['valid_json']:.0%} "
        f"| {out.with_suffix('.md').relative_to(ROOT)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", type=Path, default=ROOT / "eval" / "code_cases.jsonl")
    parser.add_argument("--llm-per-minute", type=int, default=8, help="pace for LLM calls")
    args = parser.parse_args()

    cases = load_cases(args.cases, CodeCase)
    results, model = asyncio.run(
        run(Settings(), cases, args.llm_per_minute), loop_factory=asyncio.SelectorEventLoop
    )
    run_info = {
        "date": datetime.date.today().isoformat(),
        "llm_model": model,
        "dataset": args.cases.name,
    }
    write_report(results, run_info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
