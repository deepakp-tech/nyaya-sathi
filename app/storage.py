"""Persistent conversation storage (SQLite, one file: data/nyaya.db).

Two layers live in the same database file:
- LangGraph checkpoints (tables created by SqliteSaver): the full graph state per thread_id
  (messages, case file, active mode). This is what lets a conversation continue after a restart.
- App tables below: the list of conversations per user and the messages as displayed in the UI
  (with draft paths and a snapshot of the case panel), so a chat can be reopened instantly.

Privacy: only text that already went through PII redaction reaches the graph checkpoints. The UI messages
store the reply as shown (masked). The placeholder -> real-value vault is deliberately NOT persisted.
"""
import json
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from functools import lru_cache

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,          -- also the LangGraph thread_id
    user_id     TEXT NOT NULL,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS messages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id  TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content          TEXT NOT NULL,
    meta             TEXT,                 -- JSON: run_id, draft_path, draft_text, panel snapshot
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, id);
"""

_init_lock = threading.Lock()
_initialized = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _connect() -> sqlite3.Connection:
    global _initialized
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not _initialized:
        with _init_lock:
            if not _initialized:
                conn.execute("PRAGMA journal_mode = WAL")  # readers don't block the writer
                conn.executescript(SCHEMA)
                conn.commit()
                _initialized = True
    return conn


# ---------------------------------------------------------------- LangGraph checkpointer
@lru_cache(maxsize=1)
def get_checkpointer():
    """One shared SqliteSaver for the process (it serialises access with its own lock)."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    _connect().close()  # make sure the folder, WAL mode and app tables exist
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, timeout=30)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


# ---------------------------------------------------------------- conversations
def new_id() -> str:
    return str(uuid.uuid4())


def _title_from(text: str) -> str:
    t = " ".join((text or "").split())
    return (t[:48] + "…") if len(t) > 48 else (t or "New conversation")


def create_conversation(user_id: str, first_message: str, conversation_id: str | None = None) -> str:
    cid = conversation_id or new_id()
    now = _now()
    with _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO conversations (id, user_id, title, created_at, updated_at) "
                     "VALUES (?, ?, ?, ?, ?)", (cid, user_id, _title_from(first_message), now, now))
    return cid


def get_conversation(conversation_id: str, user_id: str) -> dict | None:
    """Returns the conversation only if it belongs to this user."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ? AND user_id = ?",
                           (conversation_id, user_id)).fetchone()
    return dict(row) if row else None


def list_conversations(user_id: str, limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT id, title, created_at, updated_at FROM conversations WHERE user_id = ? "
                            "ORDER BY updated_at DESC LIMIT ?", (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def rename_conversation(conversation_id: str, user_id: str, title: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE conversations SET title = ? WHERE id = ? AND user_id = ?",
                     (_title_from(title), conversation_id, user_id))


def delete_conversation(conversation_id: str, user_id: str) -> bool:
    """Delete messages, graph checkpoints and draft files of one conversation."""
    if not get_conversation(conversation_id, user_id):
        return False
    with _connect() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
    try:
        get_checkpointer().delete_thread(conversation_id)
    except Exception:  # noqa: BLE001 - checkpoint rows are harmless if left behind
        pass
    shutil.rmtree(config.CONV_DRAFT_DIR / conversation_id, ignore_errors=True)
    return True


# ---------------------------------------------------------------- messages
def add_message(conversation_id: str, role: str, content: str, meta: dict | None = None) -> None:
    now = _now()
    with _connect() as conn:
        conn.execute("INSERT INTO messages (conversation_id, role, content, meta, created_at) VALUES (?, ?, ?, ?, ?)",
                     (conversation_id, role, content, json.dumps(meta, ensure_ascii=False, default=str) if meta else None,
                      now))
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))


def get_messages(conversation_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT role, content, meta FROM messages WHERE conversation_id = ? ORDER BY id",
                            (conversation_id,)).fetchall()
    out = []
    for r in rows:
        m = {"role": r["role"], "content": r["content"]}
        if r["meta"]:
            m.update(json.loads(r["meta"]))
        out.append(m)
    return out
