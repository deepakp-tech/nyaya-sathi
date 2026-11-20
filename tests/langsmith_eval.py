"""Upload test cases to a LangSmith dataset and run an evaluation experiment.

    python tests/langsmith_eval.py --prefix v1-baseline

Compare experiments (v1, v2, ...) side by side in the LangSmith UI.
"""
import argparse
import sys
import os as _os; _os.environ.setdefault("PERSIST_CONVERSATIONS", "false")  # test runs stay out of data/nyaya.db
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import yaml  # noqa: E402
from langsmith import Client, evaluate  # noqa: E402

from app import config  # noqa: E402
from checks import run_checks  # noqa: E402

DATASET = "ai-lawyer-india-test-cases"


def ensure_dataset(client: Client) -> str:
    cases = yaml.safe_load((ROOT / "tests" / "cases.yaml").read_text(encoding="utf-8"))["cases"]
    cases = [c for c in cases if c.get("turns")]  # audio cases run separately
    if client.has_dataset(dataset_name=DATASET):
        return DATASET
    ds = client.create_dataset(DATASET, description="Behavioural tests: honesty, escalation, citations, languages")
    client.create_examples(
        inputs=[{"id": c["id"], "turns": c["turns"]} for c in cases],
        outputs=[{"case": c} for c in cases],
        dataset_id=ds.id,
    )
    return DATASET


def target(inputs: dict) -> dict:
    from app.service import run_turn
    thread = f"ls-{inputs['id']}-{uuid.uuid4().hex[:6]}"
    final = {}
    for t in inputs["turns"]:
        final = run_turn(thread, t, tags=["langsmith-eval", inputs["id"]])
    return {"final": final}


def _make_evaluator(check_name: str):
    def _ev(run, example) -> dict:
        case = example.outputs["case"]
        res = [c for c in run_checks(case, run.outputs["final"]) if c["check"] == check_name]
        if not res:
            return {"key": check_name, "score": None}
        return {"key": check_name, "score": int(res[0]["passed"]), "comment": res[0]["detail"]}
    _ev.__name__ = check_name
    return _ev


CHECKS = ["escalation", "no_case_law", "citations_verified", "admits_unknown", "no_guarantee",
          "language", "category", "mentions_any", "must_not_mention", "refuses_harmful", "emergency_info"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="baseline")
    a = ap.parse_args()
    if not config.env("LANGSMITH_API_KEY"):
        sys.exit("Add LANGSMITH_API_KEY to .env first.")
    client = Client()
    ds = ensure_dataset(client)
    evaluate(target, data=ds, evaluators=[_make_evaluator(c) for c in CHECKS],
             experiment_prefix=a.prefix, max_concurrency=2,
             metadata={"model": f"{config.LLM_PROVIDER}/{config.LLM_MODEL}"})
    print("Done — open LangSmith > Datasets & Experiments to compare runs.")


if __name__ == "__main__":
    main()
