"""Central configuration loaded from .env."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # dotenv optional for unit tests
    pass

ROOT = Path(__file__).resolve().parent.parent
CORPUS_FILE = ROOT / "corpus" / "sections.jsonl"
PLAYBOOK_DIR = ROOT / "corpus" / "playbooks"
PROMPT_DIR = ROOT / "app" / "prompts"
DRAFT_DIR = ROOT / "outputs" / "drafts"
# Persistent storage: conversation list + LangGraph checkpoints (SQLite) and per-conversation drafts
DATA_DIR = ROOT / os.getenv("DATA_DIR", "data")
DB_PATH = DATA_DIR / "nyaya.db"
CONV_DRAFT_DIR = DATA_DIR / "drafts"


def env(name: str, default: str = "") -> str:
    val = os.getenv(name, default)
    return val.strip() if isinstance(val, str) else default


LLM_PROVIDER = env("LLM_PROVIDER", "groq")
LLM_MODEL = env("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_FAST_MODEL = env("LLM_FAST_MODEL") or LLM_MODEL

EMBEDDING_MODEL = env("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
CHROMA_DIR = str(ROOT / env("CHROMA_DIR", ".chroma"))
RETRIEVAL_K = int(env("RETRIEVAL_K", "6"))

ENABLE_GROUNDING_CHECK = env("ENABLE_GROUNDING_CHECK", "true").lower() == "true"
MAX_REGENERATIONS = int(env("MAX_REGENERATIONS", "2"))

SARVAM_API_KEY = env("SARVAM_API_KEY")
SARVAM_STT_MODEL = env("SARVAM_STT_MODEL", "saarika:v2.5")
SARVAM_TTS_MODEL = env("SARVAM_TTS_MODEL", "bulbul:v3")
SARVAM_TTS_SPEAKER = env("SARVAM_TTS_SPEAKER", "priya")

PROVIDER_KEY_VAR = {
    "groq": "GROQ_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def check_setup() -> list[str]:
    """Return a list of human-readable setup problems (empty = ready)."""
    problems = []
    key_var = PROVIDER_KEY_VAR.get(LLM_PROVIDER)
    if not key_var:
        problems.append(f"LLM_PROVIDER '{LLM_PROVIDER}' is not one of {list(PROVIDER_KEY_VAR)}")
    elif not env(key_var):
        problems.append(f"{key_var} is empty in .env (needed for LLM_PROVIDER={LLM_PROVIDER})")
    if not CORPUS_FILE.exists():
        problems.append(f"Corpus file missing: {CORPUS_FILE}")
    if env("LANGSMITH_TRACING").lower() == "true" and not env("LANGSMITH_API_KEY"):
        problems.append("LANGSMITH_TRACING=true but LANGSMITH_API_KEY is empty")
    return problems
