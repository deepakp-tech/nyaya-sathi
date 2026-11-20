# How Nyaya Saathi stays honest and avoids inventing law

> The brief: *"Your AI should be honest about what it doesn't know, say when someone needs a real lawyer. AI models
> confidently invent laws, sections and past cases, so tell us how yours avoids that."*

Our principle: **don't trust the model to be careful — make it structurally hard to be wrong, and visible when it might be.**
No single technique is enough, so we use seven layers. Each is in the code and covered by tests.

---

## 1. A closed, verified legal corpus
- The only law the assistant may use is in `corpus/sections.jsonl` (statute sections + procedural facts) and
  `corpus/playbooks/` (practical steps), built from official sources (indiacode.nic.in, eGazette, consumerhelpline.gov.in,
  edaakhil.nic.in, NALSA).
- Each entry records `source_url`, `verified` and `verified_on`. Entries start as **pending** and are flipped to
  verified only after a human checks them against the official text.
- Entries carry a `status`: `in_force`, `model_law` (e.g. Model Tenancy Act — applies only where adopted),
  or `check_current` (fees, limits, helplines, labour-code notification) so the model is told to hedge on them.
- Repeal notes (IPC → BNS, CrPC → BNSS, Evidence Act → BSA, CPA 1986 → 2019) are part of the corpus, so the
  model can correct users who cite old law.

## 2. The model never writes a citation — code does
- The prompt allows law to be referenced **only** with markers like `[[CPA2019_S69]]`, which must be among the
  sources retrieved for that turn.
- `citations.render()` turns markers into "Consumer Protection Act, 2019, Section 69". The model therefore cannot
  invent a section number in a citation: an unknown ID simply has nothing to render.

## 3. A deterministic verifier on every answer (`app/guardrails/citations.py`)
Rejects an answer if it contains:
| Check | Example caught |
|---|---|
| Citation ID not in corpus / not retrieved this turn | `[[CPA2019_S999]]` |
| Section/article number written as free text (English **and** Hindi) | "Section 35", "धारा 420" |
| A named law that isn't in the corpus | "Rent Control Act 2023" |
| Case-law patterns | "X v. Y", "AIR 2015 SC 123", "(2019) 4 SCC 210" |
| Repealed law presented as current | "IPC 420 punishes…" (without saying it was replaced) |
| Raw personal identifiers | Aadhaar/PAN/phone in the answer |

On rejection the graph **regenerates with the exact problems as feedback** (max `MAX_REGENERATIONS`, default 2).
If it still fails, the unverifiable parts are **stripped and replaced with "[reference removed — could not be
verified]"**, confidence is set to low, and the user is told.

## 4. LLM grounding judge
After the deterministic checks pass, a second LLM call checks that every *legal claim* (rights, deadlines, limits,
fees, authorities) is supported by the retrieved sources. Unsupported claims → regenerate. This catches
hallucinations that don't look like citations ("you get 18% interest").

## 5. No case law — by design
We cannot reliably verify judgments, and invented cases are the most damaging failure. The assistant never cites
cases; when asked, it says why and suggests a lawyer. (If case law is added later, it would be a small hand-verified
list with full citations, under the same ID-only mechanism.)

## 6. Honest uncertainty, shown to the user
- Structured output requires `confidence` and an `unknowns` list. Unknowns are shown as **"What I'm not sure about"**.
- Every answer ends with numbered **Sources** marked ✔ verified / ⚠ pending verification.
- Prompts require: say "I don't know / couldn't verify", don't accept user-stated laws you can't find, flag
  state-specific rules, never promise outcomes, never add false facts to documents (placeholders for unknowns).

## 7. "You need a real lawyer" — rules first, model second
`app/guardrails/rules.py` runs **before** the LLM and can only *add* flags:
| Trigger | Response |
|---|---|
| Danger / violence / domestic violence | Immediate 112 / 181 block, then lawyer + legal aid |
| Police, FIR, arrest, cheque bounce, criminal law | Escalate |
| Summons, hearing date, case filed, notice with deadline | Escalate |
| Amount ≥ Rs 20 lakh or property | Escalate |
| Events ≥ 2 years old (limitation risk) | Escalate |
| Outside tenancy / consumer / employment | Honest "outside what I can help with" + referral |

Escalation text is **deterministic** (not generated), in English/Hindi, and always includes free legal aid via
DLSA / NALSA helpline 15100.

## Privacy (related honesty commitment)
Aadhaar, PAN, phone, UPI, bank account, IFSC and email are redacted **before** the graph runs. The LLM and LangSmith
traces see only placeholders; real values are restored only inside the .docx saved locally for the user.

## How we test it
- `tests/test_guardrails.py` — unit tests for each verifier rule (fake IDs, free-text sections, Hindi sections,
  case-law formats, invented Acts, repealed laws, PII, false-alarm cases like "fake product").
- `tests/smoke_test.py` — runs the real graph with a fake LLM whose first answer hallucinates
  ("Section 999 … Ramesh v. State, AIR 2010") and checks it is caught and regenerated.
- `tests/cases.yaml` T15–T20 — hallucination traps against the real model; T21–T28 — escalation; results in
  `tests/outputs/` and `EVAL.md`.

## What this does NOT guarantee
- The corpus summaries are only as good as our verification — that's why verification status is shown.
- The grounding judge is itself an LLM and can miss subtle errors.
- Practical advice in playbooks is general and may not fit every situation.
These limits are stated to the user via the disclaimer, unknowns list and escalation rules.
