"""Persistent conversation storage tests (no API key needed).   Run: python tests/test_storage.py"""
import sys
import tempfile
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="nyaya_storage_"))
config.DATA_DIR = TMP
config.DB_PATH = TMP / "nyaya.db"
config.CONV_DRAFT_DIR = TMP / "drafts"

from app import storage  # noqa: E402


def test_conversations_are_isolated_per_user():
    a = storage.create_conversation("user_a", "Landlord not returning my deposit")
    b = storage.create_conversation("user_b", "Salary not paid")
    assert [c["id"] for c in storage.list_conversations("user_a")] == [a]
    assert [c["id"] for c in storage.list_conversations("user_b")] == [b]
    assert storage.get_conversation(a, "user_b") is None, "user_b must not open user_a's chat"
    assert storage.delete_conversation(a, "user_b") is False, "user_b must not delete user_a's chat"


def test_messages_are_separate_per_conversation_and_ordered():
    c1 = storage.create_conversation("u", "first chat")
    c2 = storage.create_conversation("u", "second chat")
    storage.add_message(c1, "user", "hello 1")
    storage.add_message(c1, "assistant", "reply 1", {"run_id": "r1", "panel": {"case_file": {"x": 1}}})
    storage.add_message(c2, "user", "hello 2")
    m1 = storage.get_messages(c1)
    assert [m["content"] for m in m1] == ["hello 1", "reply 1"]
    assert m1[1]["run_id"] == "r1" and m1[1]["panel"]["case_file"] == {"x": 1}
    assert [m["content"] for m in storage.get_messages(c2)] == ["hello 2"]
    assert storage.list_conversations("u")[0]["id"] == c2, "most recently active first"


def test_title_is_truncated():
    c = storage.create_conversation("t", "x" * 200)
    assert len(storage.get_conversation(c, "t")["title"]) <= 49


def test_graph_state_survives_new_checkpointer():
    """Simulates a server restart: a second SqliteSaver on the same file sees the earlier state."""
    import sqlite3

    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.graph.message import add_messages

    class S(TypedDict):
        messages: Annotated[list, add_messages]

    def echo(state):
        return {"messages": [AIMessage(content=f"turns={len(state['messages'])}")]}

    def build(saver):
        g = StateGraph(S)
        g.add_node("echo", echo)
        g.add_edge(START, "echo")
        g.add_edge("echo", END)
        return g.compile(checkpointer=saver)

    cfg = {"configurable": {"thread_id": "thread-1"}}
    build(storage.get_checkpointer()).invoke({"messages": [HumanMessage(content="hi")]}, cfg)

    fresh = SqliteSaver(sqlite3.connect(config.DB_PATH, check_same_thread=False))  # "after restart"
    out = build(fresh).invoke({"messages": [HumanMessage(content="again")]}, cfg)
    assert out["messages"][-1].content == "turns=3", out["messages"][-1].content
    other = build(fresh).invoke({"messages": [HumanMessage(content="new")]}, {"configurable": {"thread_id": "t2"}})
    assert other["messages"][-1].content == "turns=1", "threads must not share history"


def test_delete_removes_messages_checkpoints_and_drafts():
    c = storage.create_conversation("d", "to delete")
    storage.add_message(c, "user", "secret")
    folder = config.CONV_DRAFT_DIR / c
    folder.mkdir(parents=True)
    (folder / "draft.docx").write_bytes(b"x")
    assert storage.delete_conversation(c, "d") is True
    assert storage.get_messages(c) == []
    assert storage.list_conversations("d") == []
    assert not folder.exists()


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"\n{len(tests)} storage tests passed")
