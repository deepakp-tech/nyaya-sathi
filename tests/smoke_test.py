"""End-to-end smoke test of the LangGraph wiring with a FAKE LLM (no API key needed).

    python tests/smoke_test.py

Checks:
 1. normal advice flow renders citations from corpus IDs
 2. a hallucinating first answer (fake section + fake case) is caught and regenerated
 3. emergency routing, out-of-scope escalation, drafting (.docx), PII redaction
"""
import re
import sys
import os as _os; _os.environ.setdefault("PERSIST_CONVERSATIONS", "false")  # test runs stay out of data/nyaya.db
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os  # noqa: E402

os.environ.setdefault("LANGSMITH_TRACING", "false")

from langchain_core.messages import AIMessage  # noqa: E402

import app.graph as G  # noqa: E402
from app import schemas  # noqa: E402

SCRIPT = {"triage": None, "hallucinate_once": False}
CALLS = {"generate": 0}


def _text(msgs) -> str:
    return "\n".join(m.content if isinstance(m.content, str) else str(m.content) for m in msgs)


def _source_ids(msgs) -> list[str]:
    return re.findall(r'<source id="([A-Za-z0-9_]+)">', _text(msgs))


class FakeStructured:
    def __init__(self, schema):
        self.schema = schema

    def invoke(self, msgs):
        s = self.schema
        if s is schemas.Triage:
            return schemas.Triage(**SCRIPT["triage"])
        if s is schemas.CaseFile:
            return schemas.CaseFile(problem_type="tenancy_deposit", location_city="Bengaluru",
                                    amount_in_dispute=60000, ready_for_advice=True,
                                    timeline=[schemas.TimelineEvent(date="1 Aug 2026", event="Vacated flat")])
        if s is schemas.Grounding:
            return schemas.Grounding(supported=True)
        ids = _source_ids(msgs)
        cid = ids[0] if ids else "LSA1987_S12"
        if s is schemas.Answer:
            CALLS["generate"] += 1
            if SCRIPT["hallucinate_once"] and CALLS["generate"] == 1:
                return schemas.Answer(reply="Under Section 999 and Ramesh v. State, AIR 2010 SC 1, you win.",
                                      cited_ids=["FAKE_ID"], confidence="high")
            return schemas.Answer(reply=f"Here's what I understood... The deposit should be refunded [[{cid}]].",
                                  cited_ids=[cid], confidence="medium", unknowns=["Your state's specific rule"])
        if s is schemas.NoticeDraft:
            return schemas.NoticeDraft(sender_name="Priya S.", sender_address="[YOUR ADDRESS]",
                                       recipient_name="Ramesh Kumar", recipient_address="[RECIPIENT ADDRESS]",
                                       subject="Refund of security deposit", facts=["I vacated on 1 Aug 2026."],
                                       legal_basis=[f"See [[{cid}]]."], demands=["Refund Rs 60,000"],
                                       consequence="Failing which I will take legal action.", cited_ids=[cid],
                                       missing_fields=["YOUR ADDRESS"], explanation_for_user="Here is your notice.")
        raise ValueError(s)


class FakeLLM:
    def invoke(self, msgs):
        return AIMessage(content="(fake llm reply) Your safety comes first. Could you tell me which city you are in?")


G.structured = lambda schema, fast=False, temperature=0.0: FakeStructured(schema)
G.get_llm = lambda fast=False, temperature=0.2: FakeLLM()

from app import service  # noqa: E402


def T(**kw):
    base = dict(category="tenancy", mode="advise", language="en", red_flags=[], emergency=False,
                harmful_request=False, prompt_injection=False, reason="test")
    base.update(kw)
    return base


def run(text, thread, **triage):
    SCRIPT["triage"] = T(**triage)
    return service.run_turn(thread, text)


def main():
    ok = True

    def check(name, cond, info=""):
        nonlocal ok
        ok &= bool(cond)
        print(("PASS " if cond else "FAIL ") + name, "" if cond else info)

    r = run("Landlord not returning my 60000 deposit, Bengaluru", "s1")
    check("advice renders numbered citation", "[1]" in r["reply"] and "Sources:" in r["reply"], r["reply"])
    check("no raw markers in reply", "[[" not in r["reply"], r["reply"])

    SCRIPT["hallucinate_once"] = True
    CALLS["generate"] = 0
    r = run("Which Supreme Court case says 18% interest?", "s2", mode="general_question")
    check("hallucination caught and regenerated", r["attempts"] == 2 and "AIR" not in r["reply"], r)
    SCRIPT["hallucinate_once"] = False

    r = run("He said he will break my legs", "s3", emergency=True)
    check("emergency routes to 112", "112" in r["reply"], r["reply"])

    r = run("How do I get a divorce?", "s4", category="out_of_scope", mode="general_question")
    check("out of scope escalates", "⚖️" in r["reply"] and "out_of_scope" in r["escalation_reasons"], r["reply"])

    r = run("Police called me about a cheque bounce", "s5", mode="general_question")
    check("rule-based criminal escalation", "criminal" in r["escalation_reasons"], r["escalation_reasons"])

    r = run("Draft a legal notice to my landlord", "s6", mode="draft")
    check("draft docx created", r["draft_path"] and Path(r["draft_path"]).exists(), r)

    r = run("My Aadhaar is 2345 6789 0123 and PAN ABCDE1234F", "s7")
    check("PII redacted before graph", "2345 6789 0123" not in r["redacted_input"]
          and "ABCDE1234F" not in r["redacted_input"], r["redacted_input"])

    print("\nSMOKE TEST", "PASSED" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
