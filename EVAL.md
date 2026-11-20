# Evaluation

> Fill this in after running `python tests/run_tests.py` (and optionally `python tests/langsmith_eval.py`).
> Raw outputs: `tests/outputs/raw_outputs.jsonl` · Transcripts: `tests/outputs/T*.md` · Table: `tests/outputs/SUMMARY.md`

## Setup
- Model: `<provider/model>` · Date: `<date>` · Corpus entries: `<n>` (verified: `<n>`)
- 33 test cases written by us (no input pack was provided).

## Results
<!-- paste the "Key metrics" and "Per case" sections from tests/outputs/SUMMARY.md -->

## Hallucination traps (T15–T20)
| Case | Trap | What happened |
|---|---|---|
| T15 | Asked for a non-existent SC judgment | |
| T16 | "Section 999" of CPA | |
| T17 | IPC 420 (repealed) | |
| T18 | False premise ("Rent Control Act 2023") | |
| T19 | Exact fee | |
| T20 | Prompt injection asking for case law | |

## Escalation (T10, T17, T21–T28)
<!-- did it escalate every time it should? any false alarms? -->

## Failures found and fixes made
<!-- Be honest: list failures from the first run, what you changed (prompt, rule, corpus), and the re-run result.
     LangSmith experiment comparison screenshots are useful here. -->

| Run | Change | Pass rate |
|---|---|---|
| v1 | baseline | |
| v2 | | |

## Known limitations
See README → Known limitations.
