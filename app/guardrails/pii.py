"""PII redaction for Indian identifiers.

User text is redacted BEFORE it reaches the graph, the LLM, or LangSmith traces.
Real values live only in an in-memory vault (per conversation) and are restored
only inside generated documents saved locally.
"""
import re

# Order matters: more specific patterns first.
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("UPI", re.compile(r"\b[\w.-]{2,}@(?:ok\w+|ybl|ibl|axl|paytm|upi|apl|icici|sbi|hdfcbank|axisbank|[a-z]{3,10})\b", re.I)),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("IFSC", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
    ("AADHAAR", re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b")),
    ("PHONE", re.compile(r"(?:(?<=\s)|^|(?<=[(:]))(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}\b")),
    ("BANK_ACCOUNT", re.compile(r"\b\d{9,18}\b")),
]


def redact(text: str, vault: dict | None = None) -> tuple[str, dict]:
    """Replace PII with placeholders like <AADHAAR_1>. Returns (text, vault)."""
    vault = {} if vault is None else vault
    reverse = {v: k for k, v in vault.items()}
    for label, pat in PATTERNS:
        def _sub(m, label=label):
            val = m.group(0)
            if val in reverse:
                return reverse[val]
            n = sum(1 for k in vault if k.startswith(f"<{label}_")) + 1
            key = f"<{label}_{n}>"
            vault[key] = val
            reverse[val] = key
            return key
        text = pat.sub(_sub, text)
    return text, vault


def restore(text: str, vault: dict) -> str:
    for key, val in vault.items():
        text = text.replace(key, val)
    return text


def mask_for_display(text: str, vault: dict) -> str:
    """Show only the last 4 characters of any PII echoed back in chat."""
    for key, val in vault.items():
        tail = re.sub(r"\W", "", val)[-4:]
        text = text.replace(key, f"XXXX{tail}")
    return text


def contains_raw_pii(text: str) -> list[str]:
    found = []
    for label, pat in PATTERNS:
        if label == "BANK_ACCOUNT":
            continue  # too many false positives on amounts
        found += [f"{label}:{m.group(0)}" for m in pat.finditer(text)]
    return found
