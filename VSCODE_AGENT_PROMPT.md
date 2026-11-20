# Prompt for the VS Code AI agent

Open this project folder in VS Code, open your AI agent (Claude Code / Copilot agent / Cursor-style agent) and paste
everything inside the box below. It is written so the agent finishes the project end to end and only stops when it
needs something from you (API keys, a voice recording, a decision).

---

```text
You are working in an existing, nearly complete Python project: "Nyaya Saathi", an AI legal helper for ordinary
people in India (hiring assignment for an AI Engineer role). Your job is to get it fully running, tested and
submission-ready within the time available. Read README.md and docs/HONESTY_AND_HALLUCINATION.md first.

PROJECT FACTS
- Stack: Python 3.11+, LangChain (init_chat_model), LangGraph (app/graph.py), LangSmith (tracing + eval),
  Chroma + HuggingFace embeddings, Streamlit UI (ui/streamlit_app.py), Sarvam AI voice (optional), python-docx.
- Config comes ONLY from .env (template: .env.example). The user adds keys; you never hard-code keys.
- Anti-hallucination design: law is cited ONLY via [[SOURCE_ID]] markers that exist in corpus/sections.jsonl or
  corpus/playbooks/; app/guardrails/citations.py rejects anything else; code renders citations.
- Tests: tests/test_guardrails.py (no key), tests/smoke_test.py (fake LLM, no key), tests/run_tests.py (real LLM,
  33 cases in tests/cases.yaml, writes raw outputs to tests/outputs/), tests/langsmith_eval.py (LangSmith).

HARD RULES (never break these)
1. Do NOT redesign the architecture or replace LangGraph/LangChain/LangSmith. Fix and finish; don't rewrite.
2. NEVER weaken a guardrail or a test expectation just to make a test pass. If a test fails, fix the prompt,
   routing, rules or corpus — and if you believe an expectation is genuinely wrong, explain why in EVAL.md first.
3. NEVER add legal content (sections, limits, fees, deadlines, case law) from memory. Corpus changes must come from
   official sources (indiacode.nic.in, egazette.gov.in, consumerhelpline.gov.in, edaakhil.nic.in, nalsa.gov.in,
   labour ministry sites). If you cannot verify something, leave verified=false and say so.
4. Never commit .env or any secret. Never print API keys.
5. Keep every prompt in app/prompts/*.md (reviewers read them).
6. After each phase, run the relevant tests and report the result in one short line before continuing.

PHASE 1 — Environment (15 min)
- Create a venv, `pip install -r requirements.txt`. If a package/version conflict appears, pin compatible
  versions in requirements.txt.
- If .env does not exist, copy .env.example to .env and STOP to ask me to fill in: LLM_PROVIDER, LLM_MODEL and the
  matching API key (optional: LANGSMITH_API_KEY with LANGSMITH_TRACING=true, SARVAM_API_KEY). Tell me exactly which
  lines to edit. Check the model ID is current for that provider (look it up in the provider's docs).

PHASE 2 — Make it run without keys (20 min)
- Run `python tests/test_guardrails.py` and `python tests/smoke_test.py`.
- Fix any import errors or API drift in LangChain/LangGraph/LangSmith (e.g. moved imports, renamed params,
  structured-output differences between providers) with minimal changes. Re-run until both pass.

PHASE 3 — Index + real model (20 min)
- Run `python scripts/ingest.py` (builds .chroma/). If the embedding model is too heavy, keep the default small one.
- Check `python -c "from app.config import check_setup; print(check_setup())"` returns [].
- Run 3 quick cases: `python tests/run_tests.py --only T01 T15 T21`. Fix runtime errors (e.g. provider-specific
  structured output issues: if with_structured_output fails, try method="json_schema" or "function_calling" for
  that provider inside app/llm.py — keep it configurable).

PHASE 4 — UI (15 min)
- Run `streamlit run ui/streamlit_app.py`. Verify: chat works, Hindi/Hinglish reply language, citations render as
  [1] with a Sources list, escalation block appears for a police question, draft .docx downloads, guardrail panel
  shows the case file. Fix any Streamlit API issues (e.g. st.audio_input availability) gracefully.
- If SARVAM_API_KEY is set, test voice in and out. If a Sarvam endpoint/model ID changed, update app/voice.py
  according to docs.sarvam.ai.

PHASE 5 — Corpus verification (30–45 min, important for credibility)
- For each entry in corpus/sections.jsonl, open the official source and check the section number, title and that
  the plain-language summary is accurate and current (amendments, notified limits, helpline numbers, labour code
  commencement). Fix summaries to match the official text in simple words. Set "verified": true and
  "verified_on": "<YYYY-MM-DD>" ONLY for entries you actually confirmed, and put the exact official URL in
  source_url. Leave the rest verified=false and list them in EVAL.md.
- Optionally add a few more sections the test cases need (e.g. the state rent law for one state), following the
  same schema and the same verification rule. Re-run `python scripts/ingest.py` afterwards.

PHASE 6 — Full test run and improvement loop (45–60 min)
- Run `python tests/run_tests.py`. Read tests/outputs/SUMMARY.md and the failing transcripts.
- For each failure, find the root cause (triage, routing, prompt, retrieval, corpus gap, check too strict) and fix
  it within the HARD RULES. Re-run failing cases with --only. Keep a log of "failure → cause → fix → result".
- When it's stable, run the full suite once more for the final raw outputs (do not hand-edit outputs).
- If LANGSMITH_API_KEY is set: run `python tests/langsmith_eval.py --prefix v1-baseline` before fixes and
  `--prefix v2-fixed` after, so the experiments can be compared in LangSmith.
- T33 (voice): if I haven't recorded tests/audio/t33_hindi_salary.wav, ask me to record a 10-second Hindi voice
  note about unpaid salary, then run it.

PHASE 7 — Submission package (20 min)
- Fill EVAL.md from tests/outputs/SUMMARY.md: metrics, hallucination-trap table, escalation results, honest list of
  failures and fixes, unverified corpus entries, limitations.
- Add to README a Mermaid diagram of the graph generated by
  `python -c "from app.graph import build_graph; print(build_graph().get_graph().draw_mermaid())"`.
- Make sure README Quick start works from a fresh clone. Ensure .gitignore covers .env, .venv, .chroma.
- `git init` (if needed), commit with a clear message. Do not push unless I ask.
- Finally give me: (1) a 5-line status summary, (2) the final pass rate, (3) anything I must do manually
  (keys, recording, demo video), and (4) a 3–5 minute demo script covering: Hinglish deposit case → case file →
  options with sources → draft notice download → practice mode → fake Supreme Court case trap → police question
  escalation → LangSmith trace.

Work autonomously through the phases. Only stop to ask me when you need a key, a recording, or a decision that
changes scope.
```

---

## What you need to have ready

| Item | When the agent asks |
|---|---|
| One LLM API key (Groq or Gemini free tier is fine) + model ID | Phase 1 |
| LangSmith API key (optional, free) | Phase 1 |
| Sarvam API key (optional, for voice) | Phase 1 |
| A 10-second Hindi voice note about unpaid salary, saved as `tests/audio/t33_hindi_salary.wav` | Phase 6 |
| Recording the demo video | After Phase 7 |
