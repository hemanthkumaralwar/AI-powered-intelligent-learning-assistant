# Answer evaluation — 2026-11-19

- Answer model: `gemini-3.5-flash-lite`; judge: the same model (may favour its own style; read the failures below)
- Embedding space: `gemini:gemini-embedding-001:768`; k = 5, threshold = 0.63
- Dataset: `dataset.jsonl`; judge calls this run: 61 (the rest came from the cache)

## Summary

| Measure | Result |
|---|---|
| Answerable questions answered (not refused) | 97% of 58 |
| Judged correct | 97% |
| Expected keywords present | 95% |
| Citation names an expected lesson | 100% |
| Grounded answers with a valid citation | 100% |
| Out-of-course questions correctly refused | 100% of 12 (target ≥ 90%) |
| Exercise-solution requests answered with hints only | 100% of 6 |
| Provider errors (counted as failures) | 2 |

## Answerable: refused or judged wrong (2)

### rest-parameters

Judge: provider error: ProviderUnavailableError

> 

### classlist

Judge: provider error: ProviderUnavailableError

> 

## Per question

| Group | Case | Outcome | Passed | Cited lessons |
|---|---|---|---|---|
| answerable | let-vs-const | answered | yes | mod-1-lesson-1, mod-1-lesson-1, mod-1-lesson-1, mod-1-lesson-1 |
| answerable | why-avoid-var | answered | yes | mod-1-lesson-1, mod-1-lesson-1, mod-1-lesson-1 |
| answerable | primitive-types | answered | yes | mod-1-lesson-2, mod-1-lesson-2, mod-1-lesson-2, mod-1-lesson-2, mod-1-lesson-2 |
| answerable | typeof-null | answered | yes | mod-1-lesson-8, mod-1-lesson-8 |
| answerable | falsy-values | answered | yes | mod-3-lesson-5, mod-3-lesson-5, mod-3-lesson-5 |
| answerable | float-precision | answered | yes | mod-1-lesson-4 |
| answerable | slice-indexes | answered | yes | mod-1-lesson-5 |
| answerable | template-literals | answered | yes | mod-1-lesson-6, mod-1-lesson-6, mod-1-lesson-6, mod-1-lesson-6 |
| answerable | triple-equals | answered | yes | mod-1-lesson-7, mod-1-lesson-7, mod-1-lesson-7, mod-1-lesson-7, mod-1-lesson-7 |
| answerable | nan-check | answered | yes | mod-1-lesson-7, mod-1-lesson-7, mod-1-lesson-7, mod-4-lesson-7 |
| answerable | plus-string-coercion | answered | yes | mod-1-lesson-3, mod-1-lesson-3, mod-1-lesson-3 |
| answerable | hoisting | answered | yes | mod-2-lesson-1, mod-2-lesson-1, mod-2-lesson-1 |
| answerable | arrow-object-return | answered | yes | mod-2-lesson-2, mod-2-lesson-2, mod-2-lesson-2 |
| answerable | rest-parameters | error | **no** | — |
| answerable | higher-order | answered | yes | mod-2-lesson-4, mod-2-lesson-4, mod-2-lesson-4, mod-2-lesson-4, mod-2-lesson-4 |
| answerable | pure-function | answered | yes | mod-2-lesson-6, mod-2-lesson-6 |
| answerable | recursion-base-case | answered | yes | mod-2-lesson-7, mod-2-lesson-7, mod-2-lesson-7, mod-2-lesson-7, mod-2-lesson-7 |
| answerable | closure | answered | yes | mod-2-lesson-8, mod-2-lesson-8, mod-2-lesson-8, mod-2-lesson-8 |
| answerable | error-first-callback | answered | yes | mod-8-lesson-2, mod-2-lesson-5, mod-8-lesson-2, mod-8-lesson-2 |
| answerable | ternary | answered | yes | mod-3-lesson-1, mod-3-lesson-1, mod-3-lesson-1, mod-3-lesson-1 |
| answerable | switch-break | answered | yes | mod-3-lesson-2, mod-3-lesson-2, mod-3-lesson-2, mod-3-lesson-2 |
| answerable | loop-choice | answered | yes | mod-3-lesson-7, mod-3-lesson-7, mod-4-lesson-3 |
| answerable | nullish-vs-or | answered | yes | mod-3-lesson-4, mod-3-lesson-4, mod-3-lesson-4, mod-3-lesson-4 |
| answerable | empty-array-truthy | answered | yes | mod-3-lesson-5, mod-3-lesson-5, mod-3-lesson-5, mod-3-lesson-5 |
| answerable | break-continue | answered | yes | mod-3-lesson-6, mod-3-lesson-6, mod-3-lesson-6, mod-3-lesson-6 |
| answerable | for-in-vs-for-of | answered | yes | mod-3-lesson-7, mod-3-lesson-7, mod-3-lesson-7, mod-3-lesson-7 |
| answerable | try-catch-finally | answered | yes | mod-3-lesson-8, mod-3-lesson-8, mod-3-lesson-8, mod-3-lesson-8 |
| answerable | last-element | answered | yes | mod-4-lesson-1, mod-4-lesson-1, mod-4-lesson-1 |
| answerable | push-vs-unshift | answered | yes | mod-4-lesson-2, mod-4-lesson-2, mod-4-lesson-2, mod-4-lesson-2 |
| answerable | break-foreach | answered | yes | mod-3-lesson-6, mod-3-lesson-6, mod-3-lesson-7, mod-4-lesson-3, mod-3-lesson-6 |
| answerable | map-undefined | answered | yes | mod-4-lesson-4, mod-4-lesson-4, mod-4-lesson-4 |
| answerable | filter-length | answered | yes | mod-4-lesson-5, mod-4-lesson-5, mod-4-lesson-5 |
| answerable | reduce-initial | answered | yes | mod-4-lesson-6, mod-4-lesson-6, mod-4-lesson-6, mod-4-lesson-6 |
| answerable | find-vs-filter | answered | yes | mod-4-lesson-5, mod-4-lesson-5, mod-4-lesson-7, mod-4-lesson-5 |
| answerable | sort-numbers | answered | yes | mod-4-lesson-8, mod-4-lesson-8, mod-4-lesson-8, mod-4-lesson-8 |
| answerable | dot-vs-bracket | answered | yes | mod-5-lesson-2, mod-5-lesson-2, mod-5-lesson-2, mod-5-lesson-2, mod-5-lesson-2 |
| answerable | destructuring-defaults | answered | yes | mod-5-lesson-3, mod-5-lesson-3, mod-5-lesson-3 |
| answerable | spread-copy | answered | yes | mod-5-lesson-4, mod-5-lesson-4, mod-5-lesson-4, mod-5-lesson-4 |
| answerable | optional-chaining | answered | yes | mod-5-lesson-5, mod-5-lesson-5, mod-5-lesson-5 |
| answerable | object-entries-loop | answered | yes | mod-5-lesson-6, mod-5-lesson-6, mod-5-lesson-6 |
| answerable | freeze-nested | answered | yes | mod-5-lesson-7, mod-5-lesson-7, mod-5-lesson-7 |
| answerable | json-stringify-pretty | answered | yes | mod-5-lesson-8, mod-5-lesson-8 |
| answerable | innerhtml-danger | answered | yes | mod-6-lesson-2, mod-6-lesson-2, mod-6-lesson-2, mod-6-lesson-2 |
| answerable | classlist | error | **no** | — |
| answerable | dom-ready | answered | yes | mod-6-lesson-8, mod-6-lesson-8 |
| answerable | target-vs-currenttarget | answered | yes | mod-7-lesson-2, mod-7-lesson-2, mod-7-lesson-2, mod-7-lesson-2 |
| answerable | event-delegation | answered | yes | mod-7-lesson-7, mod-7-lesson-7, mod-7-lesson-7, mod-7-lesson-7, mod-7-lesson-7 |
| answerable | fetch-errors | answered | yes | mod-8-lesson-5, mod-8-lesson-5, mod-8-lesson-5, mod-8-lesson-5 |
| answerable | promise-all-vs-allsettled | answered | yes | mod-8-lesson-7, mod-8-lesson-7, mod-8-lesson-7, mod-8-lesson-7, mod-8-lesson-7 |
| answerable | practice-loops-exercise | answered | yes | mod-3-lesson-3 |
| answerable | static-vs-live | answered | yes | mod-6-lesson-1, mod-6-lesson-1 |
| answerable | append-vs-appendchild | answered | yes | mod-6-lesson-5, mod-6-lesson-5, mod-6-lesson-5 |
| answerable | closest | answered | yes | mod-6-lesson-7, mod-6-lesson-7, mod-6-lesson-7 |
| answerable | remove-listener | answered | yes | mod-7-lesson-1, mod-7-lesson-1, mod-7-lesson-1, mod-7-lesson-1 |
| answerable | key-vs-code | answered | yes | mod-7-lesson-4, mod-7-lesson-4 |
| answerable | form-submit-reload | answered | yes | mod-7-lesson-8, mod-7-lesson-8, mod-7-lesson-5 |
| answerable | async-returns | answered | yes | mod-8-lesson-4, mod-8-lesson-4 |
| answerable | event-loop | answered | yes | mod-8-lesson-1, mod-8-lesson-1, mod-8-lesson-1, mod-8-lesson-1, mod-8-lesson-1 |
| unanswerable | react-hooks | no_relevant_material | yes | — |
| unanswerable | python-decorators | no_relevant_material | yes | — |
| unanswerable | sql-joins | no_relevant_material | yes | — |
| unanswerable | docker-compose | no_relevant_material | yes | — |
| unanswerable | typescript-generics | no_relevant_material | yes | — |
| unanswerable | css-grid | no_relevant_material | yes | — |
| unanswerable | git-rebase | no_relevant_material | yes | — |
| unanswerable | web-workers | no_relevant_material | yes | — |
| unanswerable | node-streams | no_relevant_material | yes | — |
| unanswerable | java-interfaces | no_relevant_material | yes | — |
| unanswerable | graphql | no_relevant_material | yes | — |
| unanswerable | regex-lookahead | no_relevant_material | yes | — |
| solution_request | sol-const-counter | answered | yes | mod-3-lesson-6, mod-1-lesson-1, mod-1-lesson-1 |
| solution_request | sol-rest-parameter | answered | yes | mod-2-lesson-3 |
| solution_request | sol-switch-break | answered | yes | mod-3-lesson-2, mod-3-lesson-2, mod-3-lesson-2 |
| solution_request | sol-map-braces | answered | yes | mod-4-lesson-4, mod-4-lesson-4, mod-4-lesson-4, mod-4-lesson-4, mod-4-lesson-4 |
| solution_request | sol-freeze-object | answered | yes | mod-5-lesson-7, mod-5-lesson-1 |
| solution_request | sol-innerhtml-chat | not_in_sources | yes | — |
