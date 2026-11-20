"""Run every test case through the real system and save RAW OUTPUTS for submission.

    python tests/run_tests.py                 # all cases
    python tests/run_tests.py --only T15 T17  # selected cases

Writes:
    tests/outputs/raw_outputs.jsonl   one line per case: every turn, full reply, triage, case file,
                                      retrieved sources, verifier report, raw LLM output, checks
    tests/outputs/<ID>.md             human-readable transcript per case
    tests/outputs/SUMMARY.md          pass/fail table + metrics (paste into EVAL.md)
"""
import argparse
import json
import sys
import os as _os; _os.environ.setdefault("PERSIST_CONVERSATIONS", "false")  # test runs stay out of data/nyaya.db
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import yaml  # noqa: E402

from app import config  # noqa: E402
from checks import run_checks  # noqa: E402

OUT = ROOT / "tests" / "outputs"


def load_cases(only=None):
    data = yaml.safe_load((ROOT / "tests" / "cases.yaml").read_text(encoding="utf-8"))
    cases = data["cases"]
    return [c for c in cases if not only or c["id"] in only]


def run_case(case: dict) -> dict:
    from app.service import run_turn
    thread = f"test-{case['id']}-{uuid.uuid4().hex[:6]}"
    turns = list(case.get("turns") or [])
    stt = None
    if case.get("audio"):
        from app import voice
        p = ROOT / case["audio"]
        if not (voice.enabled() and p.exists()):
            return {"id": case["id"], "skipped": f"audio test needs SARVAM_API_KEY and {case['audio']}"}
        transcript, lang = voice.transcribe(p.read_bytes(), p.name)
        stt = {"transcript": transcript, "detected_language": lang}
        turns = [transcript]

    results = []
    for t in turns:
        t0 = time.time()
        r = run_turn(thread, t, tags=["test", case["id"]], extra_metadata={"test_case": case["id"]})
        r["latency_s"] = round(time.time() - t0, 2)
        r["user"] = t
        results.append(r)
    final = results[-1] if results else {}
    checks = run_checks(case, final) if final else []
    return {
        "id": case["id"], "category": case.get("category"), "description": case.get("description"),
        "expected": case.get("expected"), "stt": stt, "turns": results, "checks": checks,
        "passed": all(c["passed"] for c in checks), "model": f"{config.LLM_PROVIDER}/{config.LLM_MODEL}",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def write_transcript(rec: dict):
    lines = [f"# {rec['id']} — {rec.get('description', '')}", "", f"Category: `{rec.get('category')}`  ",
             f"Model: `{rec.get('model')}`  ", f"Result: **{'PASS' if rec.get('passed') else 'FAIL'}**", ""]
    if rec.get("stt"):
        lines += [f"**Speech-to-text:** {rec['stt']}", ""]
    for i, t in enumerate(rec.get("turns", []), 1):
        lines += [f"## Turn {i}", "", "**User:**", "", t["user"], "", "**Assistant:**", "", t["reply"], "",
                  "<details><summary>Internals</summary>", "", "```json",
                  json.dumps({k: t.get(k) for k in ("triage", "escalation_reasons", "case_file", "retrieved_ids",
                                                    "guard_report", "attempts", "raw_llm_answer", "latency_s")},
                             ensure_ascii=False, indent=1), "```", "</details>", ""]
        if t.get("draft_text"):
            lines += ["**Draft document:**", "", "```", t["draft_text"], "```", ""]
    lines += ["## Checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    for c in rec.get("checks", []):
        lines.append(f"| {c['check']} | {'✅' if c['passed'] else '❌'} | {c['detail'][:150]} |")
    (OUT / f"{rec['id']}.md").write_text("\n".join(lines), encoding="utf-8")


def write_summary(records: list[dict]):
    ran = [r for r in records if not r.get("skipped") and not r.get("error")]
    passed = sum(r["passed"] for r in ran)
    all_checks = [c for r in ran for c in r["checks"]]

    def rate(name):
        cs = [c for c in all_checks if c["check"] == name]
        return f"{sum(c['passed'] for c in cs)}/{len(cs)}" if cs else "n/a"

    total_cites = sum(len(t.get("sources_used") or []) for r in ran for t in r["turns"])
    regenerations = sum(max(0, (t.get("attempts") or 0) - 1) for r in ran for t in r["turns"])
    lines = [
        "# Test summary", "",
        f"Run: {datetime.now():%Y-%m-%d %H:%M} · Model: `{config.LLM_PROVIDER}/{config.LLM_MODEL}`", "",
        f"**Cases passed: {passed}/{len(ran)}**  (skipped: {sum(1 for r in records if r.get('skipped'))}, "
        f"errors: {sum(1 for r in records if r.get('error'))})", "",
        "## Key metrics", "",
        f"- Citations shown to users: **{total_cites}** — all generated from verified corpus IDs by code",
        f"- Answers the verifier sent back for regeneration: **{regenerations}**",
        f"- Escalation correct: **{rate('escalation')}**",
        f"- No invented case law: **{rate('no_case_law')}**",
        f"- Admits unknowns when it should: **{rate('admits_unknown')}**",
        f"- Citations verified: **{rate('citations_verified')}**",
        f"- Language matched: **{rate('language')}**",
        "", "## Per case", "", "| ID | Category | Result | Failed checks |", "|---|---|---|---|",
    ]
    for r in records:
        if r.get("skipped") or r.get("error"):
            lines.append(f"| {r['id']} | — | ⏭ {r.get('skipped') or 'ERROR: ' + r['error'][:80]} | |")
            continue
        failed = ", ".join(c["check"] for c in r["checks"] if not c["passed"])
        lines.append(f"| [{r['id']}]({r['id']}.md) | {r['category']} | {'✅' if r['passed'] else '❌'} | {failed} |")
    (OUT / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    problems = config.check_setup()
    if problems:
        sys.exit("Setup problems:\n- " + "\n- ".join(problems))
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    with open(OUT / "raw_outputs.jsonl", "w", encoding="utf-8") as f:
        for case in load_cases(a.only):
            print(f"▶ {case['id']}: {case.get('description', '')}")
            try:
                rec = run_case(case)
            except Exception as e:  # keep going; record the error honestly
                rec = {"id": case["id"], "error": f"{type(e).__name__}: {e}"}
            records.append(rec)
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            f.flush()
            if rec.get("turns"):
                write_transcript(rec)
                print("   ", "PASS" if rec["passed"] else "FAIL",
                      [c["check"] for c in rec["checks"] if not c["passed"]])
            else:
                print("   ", rec.get("skipped") or rec.get("error"))
    write_summary(records)
    print(f"\nDone. See {OUT / 'SUMMARY.md'}")


if __name__ == "__main__":
    main()
