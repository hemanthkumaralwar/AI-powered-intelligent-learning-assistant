# API reference

The FastAPI backend serves interactive **Swagger** docs at `/docs` (and the raw spec at `/openapi.json`):

- Local: http://127.0.0.1:8000/docs
- Production: https://archintx-api-kday.onrender.com/docs (the first request after idle takes up to a minute)

This page is the overview; Swagger has every field, type and limit. `tests/docs/test_docs.py` fails if a route exists in the app but not on this page.

## Authentication

Send the token from `POST /auth/login` as `Authorization: Bearer <token>`; in Swagger, use **Authorize**. Tokens are HS256 JWTs carrying only the user id, valid for `ACCESS_TOKEN_MINUTES`. The role is read from the database on every request, so role changes and deleted accounts take effect at once.

| Who | Meaning |
|---|---|
| anyone | no token needed |
| logged in | any valid token (`CurrentUser` in `backend/app/api/deps.py`) |
| admin | an admin's token (`AdminUser`); students get 403 `Admin access required` |
| owner | logged in, and only your own data is ever returned; someone else's chat is 403 (admins included) |

## Endpoints

### Health and accounts

| Method and path | Who | What |
|---|---|---|
| `GET /health` | anyone | `{"status": "ok"}`; does not touch the database, so Render's health check never restarts a healthy app over a database hiccup |
| `POST /auth/register` | anyone | creates a **student** (`username`: 3–50 chars of `a-z 0-9 . _ -`, case-insensitive; `password`: 8–128 chars). Admins come only from `ADMIN_USERNAME` / `ADMIN_PASSWORD` at startup |
| `POST /auth/login` | anyone | `{"access_token", "token_type": "bearer", "expires_in"}`; the same 401 whether the username or the password was wrong |
| `GET /auth/me` | logged in | your account: `id`, `username`, `role`, `level` |
| `PATCH /auth/me` | logged in | `{"level": "beginner" \| "intermediate" \| "advanced"}`; any other field (e.g. `role`) is 422 |

### Courses and lessons

| Method and path | Who | What |
|---|---|---|
| `GET /courses` | anyone | course list |
| `GET /courses/{course_id}` | anyone | outline: modules (with explanations) and lesson titles, in order |
| `GET /lessons/{lesson_id}` | anyone | teaching content and exercises (starter code, hints), **never** solutions or quiz answers |

**Public since Step 24:** no token needed. Requests without a valid token share one app-wide guest quota (`GUEST_REQUESTS_PER_MINUTE`, 429 + `Retry-After` when reached); a valid token is never counted. They expose course text only: the response models have no fields for answers or solutions. Course and lesson responses are cached for `CONTENT_CACHE_SECONDS`; any admin upload or delete clears the cache.

### Admin: course files and indexing

| Method and path | Who | What |
|---|---|---|
| `POST /admin/documents` | admin | multipart `file` (course `.json`, at most 10 MB) + form field `language` (`c`, `cpp`, `java`, `python`, `javascript`, `sql`). Creates the course, then indexes it in the background. Without a token the request is refused before the file is read |
| `GET /admin/documents` | admin | uploaded course files, newest first, with indexing `status` (`pending`, `processing`, `ready`, `failed`) and a safe `error_message`; `?course_id=` filters |
| `GET /admin/documents/{document_id}/download` | admin | the original file (it includes every answer) |
| `DELETE /admin/documents/{document_id}` | admin | delete one uploaded file |
| `DELETE /admin/courses/{course_id}` | admin | delete a course and **everything** attached to it: lessons, quizzes, exercises, documents, vectors |
| `POST /admin/reindex` | admin | re-queue every document; unchanged content already in the current embedding space costs no quota |
| `POST /admin/search` | admin | `{query, course_id?, k}`: what retrieval would return, to check retrieval quality |

### Nexus: questions and chats

| Method and path | Who | What |
|---|---|---|
| `POST /chat/ask` | logged in | `{question, course_id?, session_id?, level?}` → `{session_id, answer, grounded, citations, practice}`. Without `session_id` a new chat starts; send it back for follow-ups. `grounded: false` means the course does not cover it. Each citation has `course_id` and `lesson_id` (citations saved before `course_id` existed have `null`) |
| `GET /chat/sessions` | owner | your chats, most recently active first (`limit` 1–50, `offset`); chats untouched for `CHAT_RETENTION_DAYS` are deleted first |
| `GET /chat/sessions/{session_id}` | owner | one chat with all its messages (answers include `grounded` and `citations`) |
| `DELETE /chat/sessions/{session_id}` | owner | delete a chat and its messages (204) |

How an answer is produced (follow-up rewriting, retrieval, grounding, server-built citations): [architecture.md](architecture.md#asking-a-question).

### Running code

| Method and path | Who | What |
|---|---|---|
| `POST /code/run` | logged in | `{language, code, stdin?}` → `{outcome, stdout, stderr, compile_output, exit_code, time_ms, provider, truncated}`. `outcome` (`ok`, `compile_error`, `runtime_error`, `timeout`, `output_limit`) describes the program and comes back as 200 |
| `POST /code/share` | logged in | `{language, code}` → `{url, warning}`: a **public, permanent** Compiler Explorer link (C, C++, Java, Python) |

Code at most 20 KB, input at most 8 KB, 5 s CPU / 10 s wall per program, output cut at 64 KB per stream. Java: name the class `Main`.

### Coding assistant

| Method and path | Who | Body → returns |
|---|---|---|
| `POST /coding/explain` | logged in | `language`, `code` → `summary`, `lines: [{line, explanation}]` |
| `POST /coding/debug` | logged in | `language`, `code`, optional `run` (a `/code/run` result) → `summary`, `issues: [{line, problem, fix_hint}]`, `corrected_code`, `exercise` |
| `POST /coding/example` | logged in | `language`, `topic` → `title`, `code`, `explanation` |
| `POST /coding/practice` | logged in | `language`, `topic` → `questions: [{question, hints, expected_output}]`, never solutions |

All four take an optional `level`, return validated JSON, and list up to 3 `related_lessons` and their `practice` activities. Code up to 8 KB / 200 lines; topics up to 200 characters. If the code is (nearly) a course bug hunt or mini challenge, `/debug` gives hints only: `corrected_code: null`, `exercise: true`.

### Exercises, quizzes and progress

| Method and path | Who | What |
|---|---|---|
| `POST /exercises/{exercise_id}/attempts` | logged in | `{code}` → `{id, passed, feedback, created_at}`; graded by the AI with hint-style feedback. Only the result is stored, not the code |
| `GET /exercises/{exercise_id}/attempts` | owner | your attempts at this exercise, newest first |
| `GET /lessons/{lesson_id}/quiz` | logged in | the lesson's quiz: each question with its options, shuffled in a fixed order per student. No answers or explanations. 404 if the lesson has no quiz |
| `POST /lessons/{lesson_id}/quiz/attempts` | logged in | `{answers: {question_id: option_id}}` → `{id, correct, total, created_at, results}`; marked on the server (no AI). Each result has `chosen`, `correct_option`, `correct` and the `explanation`. A question left out or `null` counts as wrong; an answer for another lesson's question or a missing option is 422 |
| `GET /lessons/{lesson_id}/quiz/attempts` | owner | your scores on this lesson's quiz, newest first |
| `GET /me/progress` | owner | `?course_id=`: mastery per module and lesson (`null` = not started) from exercises and quiz scores, each lesson's `quiz_score`, module coverage, `weak` lessons |
| `GET /me/recommendations` | owner | `?course_id=`: up to 5 lessons to **review** (weakest first) then the **next** ones, each with its exercises, `quiz_score` and platform practice. A review's `reason` says whether the quiz, the exercises or both are low |

## Errors

Every error is JSON `{"detail": "..."}`. Provider, runner and server internals are never returned.

| Status | When |
|---|---|
| `401` | missing, invalid or expired token; wrong username or password |
| `403` | logged in but not allowed: someone else's chat, or a student calling an admin endpoint |
| `404` | course, lesson, exercise, chat or document does not exist |
| `409` | username taken; course already uploaded (delete it first); chat full (100 messages) or changed while answering |
| `413` | body too large: 64 KB for JSON, 10 MB for uploads |
| `415` | upload is not course JSON ("Convert other material to course JSON first"; PDF, DOCX and TXT convert with [archintx-course-converter](https://github.com/hemanthkumaralwar/archintx-course-converter)) |
| `422` | invalid input: where and why, never the submitted value |
| `429` | over a quota (questions, code runs, sign-ins); `Retry-After` says how many seconds to wait |
| `500` | unexpected bug: a generic message; details only in the server log |
| `502` | the model's reply was unusable (still not valid JSON after one retry) |
| `503` | the AI provider, embedding provider or code runner is unavailable or out of its free quota |
| `504` | the AI provider took longer than `LLM_TIMEOUT_SECONDS` |

`tests/api/test_failures.py` simulates each failure and checks the status and that nothing internal leaks.

## Quotas

| Quota | Default | Setting |
|---|---|---|
| Questions and coding requests (shared AI budget) | 5 per student per minute, 20 per minute app-wide | `CHAT_QUESTIONS_*` |
| Code runs | 10 per student per minute, 200 per day; 30 per minute app-wide | `CODE_RUNS_*` |
| Sign-ins | 5 wrong passwords per username per 15 minutes; 60 sign-ins and 20 registrations per minute app-wide | `LOGIN_*`, `REGISTRATIONS_PER_MINUTE` |

Quotas live in process memory (one Render instance) and reset on restart.
