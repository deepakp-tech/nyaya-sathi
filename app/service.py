"""Entry point used by the UI and the test runner.

PII is redacted HERE, before the graph runs, so raw identifiers never reach
the LLM, the checkpointer, or LangSmith traces.
"""
import uuid
from functools import lru_cache

from langchain_core.messages import HumanMessage

from app import config
from app.drafting import draft_to_text, save_docx
from app.graph import build_graph
from app.guardrails.pii import mask_for_display, redact, restore

_VAULTS: dict[str, dict] = {}  # thread_id -> {placeholder: real value}; in memory only


@lru_cache(maxsize=1)
def get_app():
    """Graph with a persistent SQLite checkpointer, so every conversation (thread_id) survives restarts.
    Set PERSIST_CONVERSATIONS=false to fall back to in-memory state (e.g. throwaway test runs)."""
    if config.env("PERSIST_CONVERSATIONS", "true").lower() == "false":
        return build_graph()
    from app.storage import get_checkpointer
    return build_graph(checkpointer=get_checkpointer())


def run_turn(thread_id: str, user_text: str, tags: list[str] | None = None, extra_metadata: dict | None = None) -> dict:
    vault = _VAULTS.setdefault(thread_id, {})
    safe_text, vault = redact(user_text, vault)
    run_id = uuid.uuid4()

    app = get_app()
    cfg = {
        "configurable": {"thread_id": thread_id},
        "run_id": run_id,
        "run_name": "ai_lawyer_turn",
        "tags": ["ai-lawyer", *(tags or [])],
        "metadata": {"thread_id": thread_id, "llm_provider": config.LLM_PROVIDER, "llm_model": config.LLM_MODEL,
                     **(extra_metadata or {})},
    }
    state = app.invoke({"messages": [HumanMessage(content=safe_text)]}, config=cfg)

    reply = mask_for_display(state.get("final_text", ""), vault)
    draft_text, draft_path = None, None
    if state.get("draft"):
        d = {k: (restore(v, vault) if isinstance(v, str) else v) for k, v in state["draft"].items()}
        d["facts"] = [restore(x, vault) for x in d.get("facts", [])]
        draft_text = draft_to_text(d)
        draft_path = str(save_docx(d, filename_hint=d.get("doc_type", "draft"),
                                    out_dir=config.CONV_DRAFT_DIR / thread_id, unique=str(run_id)[:8]))

    return {
        "run_id": str(run_id),
        "reply": reply,
        "redacted_input": safe_text,
        "pii_redacted": sorted({k.split("_")[0].strip("<") for k in vault}),
        "triage": state.get("triage"),
        "escalation_reasons": state.get("escalation_reasons", []),
        "case_file": state.get("case_file"),
        "retrieved_ids": state.get("retrieved_ids", []),
        "sources_used": state.get("sources_used", []),
        "guard_report": state.get("guard_report"),
        "attempts": state.get("attempts", 0),
        "raw_llm_answer": state.get("raw_answer"),
        "draft_text": draft_text,
        "draft_path": draft_path,
        "active_mode": state.get("active_mode"),
    }


def send_feedback(run_id: str, score: int, comment: str = "") -> bool:
    """Thumbs up/down -> LangSmith (no-op if LangSmith is not configured)."""
    if not config.env("LANGSMITH_API_KEY"):
        return False
    try:
        from langsmith import Client
        Client().create_feedback(run_id, key="user_rating", score=score, comment=comment or None)
        return True
    except Exception:
        return False
