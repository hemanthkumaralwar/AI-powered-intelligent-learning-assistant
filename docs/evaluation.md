# Evaluation

What was measured, the results, and how to re-run each check. Every number below comes from a committed report in [`eval/reports/`](../eval/reports/).

## Datasets

| File | Contents |
|---|---|
| `eval/dataset.jsonl` | 84 hand-written cases from the JavaScript course: 58 answerable questions (acceptable `lessonId`s, expected answer, keywords), 12 out-of-course questions, 8 follow-ups (with history and an ideal standalone rewrite), 6 requests for an exercise's solution (which must get hints only). Lesson ids are checked against the real course on load |
| `eval/code_cases.jsonl` | 18 snippets with one known bug each, 3 per language (C, C++, Java, Python, JavaScript, SQL); the JavaScript ones are course bug hunts |
| `eval/materials/javascript-beginner.json` | the course used by the evaluation and the tests (64 lessons, 424 chunks) |

## Results (2026-11-19, `gemini-3.5-flash-lite`, `gemini-embedding-001` at 768 dimensions)

### Retrieval (RAG)

From [retrieval-2026-11-19-gemini.md](../eval/reports/retrieval-2026-11-19-gemini.md):

| Questions | n | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|---|
| Answerable | 58 | 98% | 100% | **100%** (target ≥ 80%) | 0.989 |
| Follow-ups, as asked | 8 | 38% | 50% | 62% | 0.483 |
| Follow-ups, rewritten by the app | 8 | 100% | 100% | **100%** (target ≥ 7/8) | 1.000 |

- **Answer-or-refuse threshold:** every answerable question's best chunk scored ≥ 0.640 and every out-of-course question's ≤ 0.624, so the app refuses below **0.63** (100% separation on this set; the margin is thin, so it was re-checked with the model in the loop below).
- **Why follow-ups are rewritten:** asked as-is ("How do I loop over it?"), follow-ups find the right lesson only 62% of the time; rewritten into standalone questions from the chat history, 100%.

### Grounded answers

From [answers-2026-11-19-gemini.md](../eval/reports/answers-2026-11-19-gemini.md):

| Measure | Result |
|---|---|
| Answerable questions answered (not refused) | 97% of 58 |
| Judged correct (LLM judge) | 97% |
| Expected keywords present | 95% |
| Grounded answers with a valid citation | **100%** |
| Citation names an expected lesson | 100% |
| Out-of-course questions correctly refused | **100% of 12** (target ≥ 90%) |
| Exercise-solution requests answered with hints only | **100% of 6** |

The 2 misses were Gemini briefly unavailable (provider errors), not wrong answers: all 56 answered questions were judged correct. The judge is the same free model, so it may be lenient; the report quotes every failure for review.

### Coding assistant

From [coding-2026-11-19.md](../eval/reports/coding-2026-11-19.md): bugs identified **18/18** (100%, target ≥ 80%; 3/3 in every language), JSON validation 100%, and the 3 JavaScript course bug hunts were recognised as exercises (hints only). Caveat: the snippets are classic beginner bugs written for this check, so real student code will score lower.

### Explanation levels

From [levels-2026-11-19.md](../eval/reports/levels-2026-11-19.md): the same closure explained at each level. Beginner (236 words) uses analogies and defines every term; intermediate (197) adds a common pitfall; advanced (158) covers lexical environments and execution contexts. Judged by eye; word counts are a rough guide.

### Chunk size (offline, no quota)

Compared with the local Hugging Face model (`BAAI/bge-small-en-v1.5`) before indexing on Gemini:

| Chunk body / overlap | Chunks | Answerable hit@5 | MRR |
|---|---|---|---|
| 1,000 / 150 | 865 | 98% | 0.894 |
| **1,500 / 150 (kept)** | **424** | 97% | 0.881 |
| 2,000 / 200 | 424 | 97% | 0.881 |

1,000 found one more question but did worse on follow-ups and on separating answerable from out-of-course questions, with twice the chunks, and so twice the daily embedding quota.

## Production

The live evaluation asks 20 of the dataset's cases (10 covered, 4 out-of-course, 3 follow-up chats, 3 solution requests; 23 questions) through the deployed API as a registered student, and scores only what the API returns (refusals, cited lessons, no solution code, response times).

- **Status:** optional, not run (the brief does not require it). It runs with a student account on production, which the maintainer creates ([deployment.md](deployment.md#run-the-production-evaluation)), and writes `eval/reports/production.md`.
- **Measured already:** API cold start 58 s for `/health` after idle; 0.1–0.2 s warm (2026-11-20).

## Re-running

| Check | Command | Cost |
|---|---|---|
| Retrieval, live index | `python eval/run_eval.py` | ~86 query embeddings |
| Retrieval + answers + follow-up rewrites + judge | `python eval/run_eval.py --answers` | + ~140 LLM calls, paced |
| Retrieval offline, any chunk size | `python eval/run_eval.py --offline --max-body 1000 --overlap 150` | none (needs `requirements-local.txt`) |
| Coding assistant | `python eval/run_code_eval.py` | ~18 LLM calls |
| Explanation levels | `python eval/run_level_demo.py` | 3 LLM calls |
| Production | `python eval/run_live_eval.py --api-url https://…onrender.com` | 23 questions on the live app |

Live runs read `DATABASE_URL` (the course must already be indexed there) and the provider keys from `.env`. Judge verdicts are cached in `eval/cache/` (gitignored), so re-runs only judge answers that changed. **Keep live runs to one or two a day:** they share the free Gemini quota with the app.
