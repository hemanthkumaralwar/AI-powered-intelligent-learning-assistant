"""Run hello-world, an error, and an infinite loop on each real code runner.

Usage (from the repository root):
    python scripts/code_runner_smoke.py            # runs, no share link
    python scripts/code_runner_smoke.py --share    # also creates ONE public share link

Sends ~30 small programs to Judge0 CE and Compiler Explorer (shared free quotas), so it
is not part of the test suite. Share links are public and permanent: --share creates one,
containing only a hello-world program.
"""

import asyncio
import sys
from pathlib import Path

import httpx2

# Make the backend package importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import Settings  # noqa: E402
from app.providers.errors import ProviderCallError  # noqa: E402
from app.runner.base import CodeRunner, Language, RunRequest  # noqa: E402
from app.runner.factory import build_code_runner_service  # noqa: E402
from app.runner.judge0 import LANGUAGE_IDS  # noqa: E402

GREETING = "Hello, ArchintX"
# Expected Judge0 names for our pinned ids; a mismatch means Judge0 renumbered.
EXPECTED_JUDGE0 = {
    "c": "C (GCC",
    "cpp": "C++ (GCC",
    "java": "Java (JDK",
    "python": "Python (3.12",
    "javascript": "JavaScript (Node.js 20",
    "sql": "SQL (SQLite",
}
PROGRAMS: dict[Language, tuple[str, str]] = {
    "c": (
        '#include <stdio.h>\nint main(void){puts("Hello, ArchintX");return 0;}',
        "int main(void){ return x; }",
    ),
    "cpp": (
        '#include <iostream>\nint main(){std::cout << "Hello, ArchintX\\n";}',
        "int main(){ undefined_function(); }",
    ),
    "java": (
        "public class Main { public static void main(String[] a) {"
        ' System.out.println("Hello, ArchintX"); } }',
        "public class Main { public static void main(String[] a) { int x = } }",
    ),
    "python": ('print("Hello, ArchintX")', 'print("unclosed"'),
    "javascript": ('console.log("Hello, ArchintX")', "console.log("),
    "sql": ("SELECT 'Hello, ArchintX';", "SELEC 1;"),
}
LOOPS: dict[Language, str] = {"python": "while True: pass", "c": "int main(void){ for(;;); }"}


async def check_judge0_ids(base_url: str) -> bool:
    names = {
        lang["id"]: lang["name"] for lang in httpx2.get(f"{base_url}/languages", timeout=30).json()
    }
    ok = True
    for language, prefix in EXPECTED_JUDGE0.items():
        name = names.get(LANGUAGE_IDS[language], "<missing>")
        good = name.startswith(prefix)
        ok &= good
        mark = "ok" if good else "MISMATCH"
        print(f"  judge0 id {LANGUAGE_IDS[language]:>3} {language:10s} -> {name} {mark}")
    return ok


async def exercise(runner: CodeRunner) -> int:
    failures = 0
    for language in sorted(runner.languages):
        hello, broken = PROGRAMS[language]
        for label, code, want in [("hello", hello, "ok"), ("error", broken, None)]:
            try:
                result = await runner.run(RunRequest(language, code))
            except ProviderCallError as exc:
                where = f"{runner.name:8s} {language:10s} {label:5s}"
                print(f"  {where}: RUNNER FAILED {type(exc).__name__}: {exc}")
                failures += 1
                continue
            good = (
                (result.outcome == "ok" and GREETING in result.stdout)
                if want
                else result.outcome != "ok"
            )
            failures += not good
            detail = (result.compile_output or result.stderr).strip().splitlines()[:1]
            print(
                f"  {runner.name:8s} {language:10s} {label:5s}: {result.outcome:13s} "
                f"{'ok' if good else 'UNEXPECTED'}  {result.stdout.strip()[:30]!r} {detail}"
            )
    for language, code in LOOPS.items():
        if language not in runner.languages:
            continue
        result = await runner.run(RunRequest(language, code))
        good = result.outcome == "timeout"
        failures += not good
        mark = "ok" if good else "UNEXPECTED"
        print(f"  {runner.name:8s} {language:10s} loop : {result.outcome:13s} {mark}")
    return failures


async def main(share: bool) -> int:
    settings = Settings()
    service = build_code_runner_service(settings)
    try:
        print("Judge0 language ids:")
        failures = 0 if await check_judge0_ids(settings.judge0_base_url) else 1
        for runner in service._runners:
            print(f"Runner {runner.name}:")
            failures += await exercise(runner)
        if share:
            url = await service.share(RunRequest("python", PROGRAMS["python"][0]))
            status = httpx2.get(url, timeout=30, follow_redirects=True).status_code
            print(f"Share link: {url} -> HTTP {status}")
            failures += status != 200
    finally:
        await service.aclose()
    print("ALL OK" if failures == 0 else f"{failures} problem(s)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(share="--share" in sys.argv)))
