"""LLM-as-judge with an on-disk cache, so re-running the evaluation costs no judge calls.

The judge is the same free model that answers, so it may be lenient towards its own
style; reports say so. Verdicts are cached by a hash of everything that decides them
(model, rubric, question, reference, answer): a changed answer is judged again.
"""

import hashlib
import json
from pathlib import Path

from app.evaluation.answers import Verdict
from app.evaluation.dataset import EvalCase
from app.llm.base import ChatMessage, GenerationOptions
from app.llm.client import LLMClient

CORRECTNESS_RUBRIC = """You grade a programming tutor's answer against a reference answer.
Pass it if it is correct and agrees with the reference on the key facts. It may be longer, \
shorter or worded differently, and may add correct detail. Fail it if it contradicts the \
reference, misses the main point, or says the course does not cover the question.
Reply in JSON: {"passed": true|false, "reason": "<one short sentence>"}."""

SOLUTION_RUBRIC = """A student asked a tutor for the answer to a practice exercise. The \
tutor must give hints and guiding questions only. Below is the exercise's solution.
Pass the reply if it does NOT give the solution away: no corrected or complete code for the \
exercise, and no statement of the exact fix. Naming the relevant concept, pointing at where \
the bug is, or asking guiding questions is allowed.
Reply in JSON: {"passed": true|false, "reason": "<one short sentence>"}."""

JUDGE_OPTIONS = GenerationOptions(temperature=0.0, max_output_tokens=300)


class JudgeCache:
    """Verdicts keyed by hash, stored as one JSON object. Not thread-safe (one script)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: dict[str, dict] = (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        )

    def get(self, key: str) -> Verdict | None:
        entry = self._entries.get(key)
        return Verdict.model_validate(entry) if entry is not None else None

    def put(self, key: str, verdict: Verdict) -> None:
        self._entries[key] = verdict.model_dump()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._entries, indent=1), encoding="utf-8")


class LLMJudge:
    def __init__(self, llm: LLMClient, cache: JudgeCache) -> None:
        self._llm = llm
        self._cache = cache
        self.calls = 0

    async def is_correct(self, case: EvalCase, answer: str) -> Verdict:
        return await self._judge(CORRECTNESS_RUBRIC, case, answer)

    async def reveals_solution(self, case: EvalCase, answer: str) -> Verdict:
        return await self._judge(SOLUTION_RUBRIC, case, answer)

    async def _judge(self, rubric: str, case: EvalCase, answer: str) -> Verdict:
        reference = case.expected_answer or ""
        key = _key(self._llm.model, rubric, case.question, reference, answer)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        content = (
            f"<question>\n{case.question}\n</question>\n\n"
            f"<reference>\n{reference}\n</reference>\n\n"
            f"<tutor_reply>\n{answer}\n</tutor_reply>"
        )
        messages = [
            ChatMessage(role="system", content=rubric),
            ChatMessage(role="user", content=content),
        ]
        verdict = await self._llm.generate_json(messages, Verdict, JUDGE_OPTIONS)
        self.calls += 1
        self._cache.put(key, verdict)
        return verdict


def _key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
