# ⚖️ Nyaya Saathi — an AI legal helper for everyday problems in India

Most people never get legal help for everyday problems: a deposit the landlord won't return, a refund that never
came, salary that stopped, a notice they don't understand. Nyaya Saathi lets a person describe the problem **by text
or voice, in their own language**, and helps them act on it.

**What it does**
| | |
|---|---|
| 🧩 **Builds the case** | Turns a messy story into a structured case file: timeline, amounts, parties, evidence they have, evidence they're missing |
| 🧭 **Explains where they stand** | Plain-language explanation of their rights and options (cheapest first), grounded only in a verified legal corpus |
| 📄 **Prepares documents** | Legal notice / consumer complaint / reply as a downloadable **.docx**, using only facts the user gave |
| 🎭 **Practice mode** | Plays the landlord / company / employer so the user can rehearse, then gives coaching feedback |
| 📜 **Explains notices** | Paste a notice you received → what it means, the deadline, what to do |
| 🗣️ **Multilingual + voice** | Replies in the user's language (English, Hindi, Hinglish, Tamil, …); speech in/out via Sarvam AI |

**Scope (deliberate depth over breadth):** tenancy (deposits, eviction), consumer (refunds, defects, e-commerce),
employment (unpaid salary, full & final). Everything else is identified as out of scope and referred to a lawyer /
free legal aid instead of guessed.

---

## 🚀 Quick start (you only add keys)

```bash
# 1. install
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. configure — copy and add ONE LLM key (Groq and Gemini have free tiers)
cp .env.example .env        # then edit .env

# 3. check everything is wired (no key needed)
python tests/test_guardrails.py
python tests/smoke_test.py

# 4. build the vector index (downloads a small embedding model once)
python scripts/ingest.py

# 5. run the app
streamlit run ui/streamlit_app.py

# 6. run the test suite and save raw outputs for submission
python tests/run_tests.py                       # -> tests/outputs/
python tests/langsmith_eval.py --prefix v1      # optional, needs LANGSMITH_API_KEY
```

**What you must add in `.env`:**
| Variable | Required? | Where to get it |
|---|---|---|
| `LLM_PROVIDER` + `LLM_MODEL` + the matching key (`GROQ_API_KEY` / `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) | **Yes** (one) | console.groq.com · aistudio.google.com · console.anthropic.com · platform.openai.com |
| `LANGSMITH_API_KEY` + `LANGSMITH_TRACING=true` | Optional | smith.langchain.com (free Developer plan) |
| `SARVAM_API_KEY` | Optional (voice) | dashboard.sarvam.ai |

Copy the exact model ID from your provider's console — model names change often.

---

## 🏗️ Architecture

```
User (text / voice) ──► Sarvam STT ──► PII redaction (Aadhaar, PAN, phone, UPI, bank, email)
                                              │   raw identifiers never reach the LLM or traces
                                              ▼
                     ┌──────────────── LangGraph ────────────────┐
                     │ guard_in (deterministic red-flag rules)    │
                     │ triage  (LLM, structured)                  │
                     │   ├─ emergency ─► 112 / 181 + lawyer       │
                     │   ├─ harmful   ─► honest refusal           │
                     │   ├─ out of scope ─► referral + legal aid  │
                     │   ├─ roleplay / feedback                   │
                     │   └─ intake (case file) ─► follow-up Qs    │
                     │ retrieve (hybrid: vector + keyword)        │
                     │ generate (law only via [[SOURCE_ID]])      │
                     │ guard_out: citation validator, case-law &  │
                     │   repealed-law detector, PII check,        │
                     │   LLM grounding judge ──► retry ≤ 2        │
                     │ finalize: render citations by code, add    │
                     │   sources + verification status, unknowns, │
                     │   lawyer escalation, disclaimer            │
                     └────────────────────────────────────────────┘
                                              │
                         Streamlit UI  ◄──────┴──────►  LangSmith (traces, datasets, evals, feedback)
```

| Layer | Tech |
|---|---|
| Orchestration | **LangGraph** (`app/graph.py`) with checkpointer for multi-turn memory |
| LLM | **LangChain** `init_chat_model` — Groq / Gemini / Claude / OpenAI, switch via `.env` |
| Retrieval | Chroma + multilingual embeddings (`intfloat/multilingual-e5-small`) + keyword scoring |
| Guardrails | `app/guardrails/` — citation validator, PII redaction, deterministic safety rules, grounding judge |
| Observability | **LangSmith** — every node traced, tagged by test case; datasets + evaluators; 👍/👎 feedback |
| Voice | Sarvam AI (STT + TTS, 22 Indian languages) |
| Documents | python-docx |

---

## 🛡️ Honesty & anti-hallucination

Full write-up: **[docs/HONESTY_AND_HALLUCINATION.md](docs/HONESTY_AND_HALLUCINATION.md)**. In short:

1. **Closed corpus.** The model may only cite entries in `corpus/` — and only by ID (`[[CPA2019_S69]]`).
2. **Code writes citations, not the model.** IDs are rendered into "Consumer Protection Act, 2019, Section 69" by code.
3. **Verifier.** Any free-text section number, unknown Act, case-law pattern (`v.`, AIR, SCC) or repealed law (IPC/CrPC)
   rejects the answer → regenerate with feedback (max 2) → otherwise strip it and say so.
4. **Grounding judge.** A second LLM call checks every legal claim against the sources.
5. **No case law, by design.** We can't verify judgments, so the assistant never cites them.
6. **Visible uncertainty.** Each answer lists what it isn't sure about; sources show ✔ verified / ⚠ pending.
7. **Escalation is rule-based, not just model-based.** Police, court dates, large amounts, old deadlines, safety → lawyer + free legal aid (NALSA 15100).

---

## 🧪 Tests & raw outputs

- `tests/cases.yaml` — **33 test cases**: happy paths ×3 domains, messy stories, drafting, practice mode,
  **hallucination traps** (fake case, fake section, repealed IPC, false premise, prompt injection), escalation,
  safety, out-of-scope, privacy, multilingual, voice.
- `tests/run_tests.py` → `tests/outputs/raw_outputs.jsonl` (everything: every turn, triage, case file,
  retrieved sources, verifier report, raw LLM output) + one readable transcript per case + `SUMMARY.md`.
- `tests/test_guardrails.py` — unit tests for the validator, PII and rules (no key needed).
- `tests/smoke_test.py` — full graph with a fake LLM, including a deliberately hallucinating answer.
- Results and failures discussed in **[EVAL.md](EVAL.md)**.

---

## ⚠️ Known limitations

- The corpus is small and hand-curated; entries are marked **pending verification** until checked against India Code.
- Tenancy law is state-specific; the Model Tenancy Act applies only where a state has adopted it.
- No case law (a deliberate trade-off for reliability).
- Free LLM tiers may use inputs for training — the demo uses synthetic test cases; production should use paid tiers.
- Not a substitute for an advocate. It says so, and tells users when they need one.

## 📁 Structure
```
app/            config, llm, graph (LangGraph), service (PII + tracing), drafting, voice
app/guardrails/ citations.py (validator) · pii.py · rules.py
app/prompts/    every prompt as a readable .md file
corpus/         sections.jsonl (verified law) · playbooks/ (practical steps)
scripts/        ingest.py (vector index; optional PDF extraction from India Code)
ui/             streamlit_app.py
tests/          cases.yaml · run_tests.py · checks.py · langsmith_eval.py · smoke_test.py · outputs/
docs/           HONESTY_AND_HALLUCINATION.md
```

---

## ☁️ Deploy (Streamlit Community Cloud, free)

1. Push this repo to GitHub (`.env`, `data/` and `.chroma/` are git-ignored — never commit keys).
2. Go to **share.streamlit.io** → *Create app* → *Deploy a public app from GitHub* → pick the repo, branch `main`,
   main file `ui/streamlit_app.py`. Under *Advanced settings* choose Python **3.12**.
3. Paste your keys under *Advanced settings → Secrets* (TOML). Root-level secrets become environment variables,
   which is what `app/config.py` reads:
   ```toml
   LLM_PROVIDER = "groq"
   LLM_MODEL = "openai/gpt-oss-120b"
   LLM_FAST_MODEL = "openai/gpt-oss-20b"
   STRUCTURED_METHOD = "json_schema"
   STRUCTURED_STRICT = "true"
   GROQ_API_KEY = "..."
   SARVAM_API_KEY = "..."          # optional (voice)
   SARVAM_TTS_MODEL = "bulbul:v3"
   SARVAM_TTS_SPEAKER = "priya"
   ```
4. Deploy. The first start installs dependencies and builds the vector index automatically (a few minutes).

**Notes:** `requirements.txt` installs CPU-only PyTorch so the build fits small hosts. Conversation history is
stored in SQLite (`data/nyaya.db`); on Streamlit Community Cloud the disk is reset when the app restarts or
redeploys, so use a host with a persistent disk (e.g. Render + disk) or swap in `langgraph-checkpoint-postgres`
for durable history. Groq's free tier allows ~200k tokens/day for `gpt-oss-120b`.
