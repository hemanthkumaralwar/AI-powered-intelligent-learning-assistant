# Retrieval evaluation — 2026-11-19

- Embedding space: `gemini:gemini-embedding-001:768`
- Index: live (rebuilt from the database) (424 chunks)
- Dataset: `dataset.jsonl` (78 cases)

## Summary

| Questions | n | hit@1 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|---|
| Answerable | 58 | 98% | 100% | 100% | 100% | 0.989 |
| Follow-ups, as asked | 8 | 38% | 50% | 62% | 88% | 0.483 |
| Follow-ups, rewritten (gold) | 8 | 100% | 100% | 100% | 100% | 1.000 |

**hit@k**: an acceptable lesson is among the top-k chunks. **MRR**: average of 1/rank of the first acceptable chunk.

## Answer-or-refuse threshold (for Step 12)

- Recommended similarity threshold: **0.632** (100% of answerable/unanswerable questions classified correctly).
- Highest top score among out-of-course questions: 0.624; lowest among answerable questions: 0.640.
- Below the threshold, the assistant should say the course materials do not cover it.

## hit@5 by module (answerable)

| Module | hit@5 |
|---|---|
| mod-1 | 100% |
| mod-2 | 100% |
| mod-3 | 100% |
| mod-4 | 100% |
| mod-5 | 100% |
| mod-6 | 100% |
| mod-7 | 100% |
| mod-8 | 100% |

## Per question

| Group | Case | Rank | Top score | Top lessons |
|---|---|---|---|---|
| answerable | let-vs-const | 1 | 0.732 | mod-1-lesson-1, mod-1-lesson-1, mod-1-lesson-1 |
| answerable | why-avoid-var | 1 | 0.669 | mod-1-lesson-1, mod-1-lesson-1, mod-1-lesson-1 |
| answerable | primitive-types | 1 | 0.749 | mod-1-lesson-2, mod-1-lesson-2, mod-1-lesson-2 |
| answerable | typeof-null | 1 | 0.711 | mod-1-lesson-8, mod-1-lesson-8, mod-1-lesson-8 |
| answerable | falsy-values | 1 | 0.743 | mod-3-lesson-5, mod-3-lesson-5, mod-3-lesson-5 |
| answerable | float-precision | 1 | 0.647 | mod-1-lesson-4, mod-1-lesson-4, mod-1-lesson-4 |
| answerable | slice-indexes | 1 | 0.666 | mod-1-lesson-5, mod-1-lesson-5, mod-1-lesson-5 |
| answerable | template-literals | 1 | 0.698 | mod-1-lesson-6, mod-1-lesson-6, mod-1-lesson-6 |
| answerable | triple-equals | 1 | 0.740 | mod-1-lesson-7, mod-1-lesson-7, mod-1-lesson-7 |
| answerable | nan-check | 1 | 0.640 | mod-1-lesson-7, mod-4-lesson-7, mod-1-lesson-7 |
| answerable | plus-string-coercion | 1 | 0.695 | mod-1-lesson-3, mod-1-lesson-3, mod-1-lesson-3 |
| answerable | hoisting | 1 | 0.677 | mod-2-lesson-1, mod-2-lesson-1, mod-2-lesson-1 |
| answerable | arrow-object-return | 1 | 0.727 | mod-2-lesson-2, mod-2-lesson-2, mod-2-lesson-2 |
| answerable | rest-parameters | 1 | 0.672 | mod-2-lesson-3, mod-2-lesson-3, mod-2-lesson-3 |
| answerable | higher-order | 1 | 0.734 | mod-2-lesson-4, mod-2-lesson-4, mod-2-lesson-4 |
| answerable | pure-function | 1 | 0.736 | mod-2-lesson-6, mod-2-lesson-6, mod-2-lesson-6 |
| answerable | recursion-base-case | 1 | 0.700 | mod-2-lesson-7, mod-2-lesson-7, mod-2-lesson-7 |
| answerable | closure | 1 | 0.722 | mod-2-lesson-8, mod-2-lesson-8, mod-2-lesson-8 |
| answerable | error-first-callback | 1 | 0.725 | mod-8-lesson-2, mod-2-lesson-5, mod-8-lesson-2 |
| answerable | ternary | 1 | 0.711 | mod-3-lesson-1, mod-3-lesson-1, mod-3-lesson-1 |
| answerable | switch-break | 1 | 0.714 | mod-3-lesson-2, mod-3-lesson-2, mod-3-lesson-2 |
| answerable | loop-choice | 1 | 0.707 | mod-3-lesson-7, mod-4-lesson-3, mod-4-lesson-3 |
| answerable | nullish-vs-or | 1 | 0.712 | mod-3-lesson-4, mod-3-lesson-4, mod-3-lesson-4 |
| answerable | empty-array-truthy | 1 | 0.750 | mod-3-lesson-5, mod-3-lesson-5, mod-3-lesson-5 |
| answerable | break-continue | 1 | 0.718 | mod-3-lesson-6, mod-3-lesson-6, mod-3-lesson-6 |
| answerable | for-in-vs-for-of | 1 | 0.768 | mod-3-lesson-7, mod-3-lesson-7, mod-3-lesson-7 |
| answerable | try-catch-finally | 1 | 0.713 | mod-3-lesson-8, mod-3-lesson-8, mod-3-lesson-8 |
| answerable | last-element | 1 | 0.673 | mod-4-lesson-1, mod-4-lesson-1, mod-4-lesson-1 |
| answerable | push-vs-unshift | 1 | 0.720 | mod-4-lesson-2, mod-4-lesson-2, mod-4-lesson-2 |
| answerable | break-foreach | 3 | 0.725 | mod-3-lesson-6, mod-3-lesson-6, mod-3-lesson-7 |
| answerable | map-undefined | 1 | 0.712 | mod-4-lesson-4, mod-4-lesson-4, mod-4-lesson-4 |
| answerable | filter-length | 1 | 0.707 | mod-4-lesson-5, mod-4-lesson-5, mod-4-lesson-5 |
| answerable | reduce-initial | 1 | 0.717 | mod-4-lesson-6, mod-4-lesson-6, mod-4-lesson-6 |
| answerable | find-vs-filter | 1 | 0.708 | mod-4-lesson-7, mod-4-lesson-5, mod-4-lesson-5 |
| answerable | sort-numbers | 1 | 0.683 | mod-4-lesson-8, mod-4-lesson-8, mod-4-lesson-8 |
| answerable | dot-vs-bracket | 1 | 0.778 | mod-5-lesson-2, mod-5-lesson-2, mod-5-lesson-2 |
| answerable | destructuring-defaults | 1 | 0.738 | mod-5-lesson-3, mod-5-lesson-3, mod-5-lesson-3 |
| answerable | spread-copy | 1 | 0.742 | mod-5-lesson-4, mod-5-lesson-4, mod-5-lesson-4 |
| answerable | optional-chaining | 1 | 0.713 | mod-5-lesson-5, mod-5-lesson-5, mod-5-lesson-5 |
| answerable | object-entries-loop | 1 | 0.742 | mod-5-lesson-6, mod-5-lesson-6, mod-5-lesson-6 |
| answerable | freeze-nested | 1 | 0.699 | mod-5-lesson-7, mod-5-lesson-7, mod-5-lesson-7 |
| answerable | json-stringify-pretty | 1 | 0.697 | mod-5-lesson-8, mod-5-lesson-8, mod-5-lesson-8 |
| answerable | innerhtml-danger | 1 | 0.717 | mod-6-lesson-2, mod-6-lesson-2, mod-6-lesson-2 |
| answerable | classlist | 1 | 0.698 | mod-6-lesson-3, mod-6-lesson-3, mod-6-lesson-3 |
| answerable | dom-ready | 1 | 0.703 | mod-6-lesson-8, mod-6-lesson-8, mod-6-lesson-8 |
| answerable | target-vs-currenttarget | 1 | 0.743 | mod-7-lesson-2, mod-7-lesson-2, mod-7-lesson-2 |
| answerable | event-delegation | 1 | 0.722 | mod-7-lesson-7, mod-7-lesson-7, mod-7-lesson-7 |
| answerable | fetch-errors | 1 | 0.696 | mod-8-lesson-5, mod-8-lesson-5, mod-8-lesson-5 |
| answerable | promise-all-vs-allsettled | 1 | 0.763 | mod-8-lesson-7, mod-8-lesson-7, mod-8-lesson-7 |
| answerable | practice-loops-exercise | 1 | 0.721 | mod-3-lesson-3, mod-3-lesson-5, mod-4-lesson-3 |
| answerable | static-vs-live | 1 | 0.698 | mod-6-lesson-1, mod-6-lesson-1, mod-6-lesson-1 |
| answerable | append-vs-appendchild | 1 | 0.720 | mod-6-lesson-5, mod-6-lesson-5, mod-6-lesson-5 |
| answerable | closest | 1 | 0.678 | mod-6-lesson-7, mod-6-lesson-7, mod-6-lesson-7 |
| answerable | remove-listener | 1 | 0.677 | mod-7-lesson-1, mod-7-lesson-1, mod-7-lesson-1 |
| answerable | key-vs-code | 1 | 0.777 | mod-7-lesson-4, mod-7-lesson-4, mod-7-lesson-4 |
| answerable | form-submit-reload | 1 | 0.641 | mod-7-lesson-5, mod-7-lesson-5, mod-7-lesson-8 |
| answerable | async-returns | 1 | 0.711 | mod-8-lesson-4, mod-8-lesson-4, mod-8-lesson-4 |
| answerable | event-loop | 1 | 0.735 | mod-8-lesson-1, mod-8-lesson-1, mod-8-lesson-1 |
| multi_turn_raw | mt-array-loop | 1 | 0.690 | mod-3-lesson-3, mod-3-lesson-7, mod-3-lesson-7 |
| multi_turn_raw | mt-promise-errors | 5 | 0.697 | mod-3-lesson-8, mod-3-lesson-8, mod-3-lesson-8 |
| multi_turn_raw | mt-arrow-this | 6 | 0.603 | mod-2-lesson-3, mod-2-lesson-1, mod-2-lesson-3 |
| multi_turn_raw | mt-reduce-sum | 3 | 0.659 | mod-1-lesson-4, mod-3-lesson-3, mod-4-lesson-6 |
| multi_turn_raw | mt-event-stop | 6 | 0.639 | mod-7-lesson-8, mod-7-lesson-8, mod-7-lesson-8 |
| multi_turn_raw | mt-object-copy | 1 | 0.644 | mod-5-lesson-4, mod-5-lesson-4, mod-5-lesson-4 |
| multi_turn_raw | mt-timer-cancel | **miss** | 0.633 | mod-7-lesson-8, mod-7-lesson-8, mod-7-lesson-8 |
| multi_turn_raw | mt-string-case | 1 | 0.592 | mod-1-lesson-5, mod-3-lesson-2, mod-5-lesson-7 |
| multi_turn_rewritten | mt-array-loop | 1 | 0.699 | mod-4-lesson-3, mod-3-lesson-7, mod-4-lesson-3 |
| multi_turn_rewritten | mt-promise-errors | 1 | 0.730 | mod-8-lesson-6, mod-3-lesson-8, mod-8-lesson-6 |
| multi_turn_rewritten | mt-arrow-this | 1 | 0.738 | mod-2-lesson-2, mod-2-lesson-2, mod-2-lesson-2 |
| multi_turn_rewritten | mt-reduce-sum | 1 | 0.716 | mod-4-lesson-6, mod-4-lesson-6, mod-4-lesson-6 |
| multi_turn_rewritten | mt-event-stop | 1 | 0.731 | mod-7-lesson-6, mod-7-lesson-6, mod-7-lesson-6 |
| multi_turn_rewritten | mt-object-copy | 1 | 0.730 | mod-5-lesson-4, mod-5-lesson-4, mod-5-lesson-4 |
| multi_turn_rewritten | mt-timer-cancel | 1 | 0.681 | mod-8-lesson-8, mod-8-lesson-8, mod-8-lesson-8 |
| multi_turn_rewritten | mt-string-case | 1 | 0.617 | mod-1-lesson-5, mod-1-lesson-5, mod-3-lesson-2 |
