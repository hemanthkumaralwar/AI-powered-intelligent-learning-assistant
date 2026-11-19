"""Step 16 manual check: the same code explained at each level, side by side.

    python eval/run_level_demo.py

Three /coding/explain calls through CodingService (one per level), no embeddings (related
lessons are skipped). Writes eval/reports/levels-<date>.md for a person to compare the
depth; word counts are a rough guide, not a pass/fail measure.
"""

import asyncio
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.coding.schemas import ExplainOutput  # noqa: E402
from app.coding.service import CodingService  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.quota import Quota  # noqa: E402
from app.evaluation.pacing import paced_llm  # noqa: E402
from app.llm.prompt_levels import LEVELS, Level  # noqa: E402
from app.rag.retriever import Retriever  # noqa: E402

LANGUAGE = "javascript"
# A short closure: deep enough that the levels should differ visibly.
CODE = """function makeCounter() {
  let count = 0;
  return function () {
    count += 1;
    return count;
  };
}

const next = makeCounter();
console.log(next());
console.log(next());"""


async def no_search(query: str, k: int, course_id: str | None) -> list:
    return []


async def explain_at_each_level(settings: Settings) -> tuple[dict[Level, ExplainOutput], str]:
    llm = paced_llm(settings, per_minute=8)
    service = CodingService(llm, Quota([]), Retriever(no_search, 1, 1.0))
    try:
        results = {
            level: (await service.explain("demo", LANGUAGE, CODE, level)).output for level in LEVELS
        }
        return results, llm.model
    finally:
        await llm.aclose()


def render(results: dict[Level, ExplainOutput], model: str, date: str) -> str:
    lines = [
        f"# Explanation levels — {date}",
        "",
        f"Model `{model}`; the same {LANGUAGE} code explained at each level "
        "(`/coding/explain`). Compare the depth by eye; word counts are only a rough guide.",
        "",
        "```javascript",
        CODE,
        "```",
        "",
        "| Level | Words | Line notes |",
        "|---|---|---|",
    ]
    for level, output in results.items():
        words = len(output.summary.split()) + sum(len(n.explanation.split()) for n in output.lines)
        lines.append(f"| {level} | {words} | {len(output.lines)} |")
    for level, output in results.items():
        lines += ["", f"## {level.capitalize()}", "", output.summary, ""]
        lines += [f"- **Line {note.line}:** {note.explanation}" for note in output.lines]
    return "\n".join(lines) + "\n"


def main() -> int:
    results, model = asyncio.run(
        explain_at_each_level(Settings()), loop_factory=asyncio.SelectorEventLoop
    )
    date = datetime.date.today().isoformat()
    out = ROOT / "eval" / "reports" / f"levels-{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(results, model, date), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
