"""Citation guardrail — the core of the anti-hallucination design.

Rule: the LLM may refer to law ONLY with markers like [[CPA2019_S69]].
Code (not the LLM) turns a marker into "Consumer Protection Act, 2019, Section 69".
Anything that looks like a legal reference but did not come from a valid marker
is treated as a possible hallucination.
"""
import re

MARKER = re.compile(r"\[\[([A-Za-z0-9_]+)\]\]")

# free-text section/article numbers the model wrote itself
STRAY_SECTION = re.compile(
    r"(\b(?:Section|Sec\.|S\.|u/s|Sections|Article|Art\.|Rule|Order)\s*\d+[A-Za-z]?(?:\(\d+\))?)"
    r"|(धारा\s*\d+)|(\bपरिच्छेद\s*\d+)",
    re.IGNORECASE,
)
# "Something Act, 2019" / "Something Act 2023" / "Sanhita, 2023"
NAMED_LAW = re.compile(
    r"\b((?:[A-Z][A-Za-z()&]+\s+){0,7}(?:Act|Sanhita|Adhiniyam|Code|Rules|Regulations),?\s+(?:of\s+)?(1[89]\d{2}|20\d{2}))\b"
)
CASE_LAW = re.compile(
    r"(\b[A-Z][\w.&']+(?:\s+[A-Z][\w.&']+){0,6}\s+(?:v\.|vs\.?|versus)\s+[A-Z][\w.&']+)"
    r"|(\bAIR\s*\d{4})|(\(\d{4}\)\s*\d+\s*SCC)|(\b\d{4}\s*SCC\b)|(\bSCC\s+(?:OnLine\s+)?\w+\s+\d+)"
    r"|(\b\d{4}\s*SCR\b)|(\bINSC\b)",
)
REPEALED = re.compile(
    r"\b(IPC|I\.P\.C\.?|Indian Penal Code|CrPC|Cr\.?P\.?C\.?|Code of Criminal Procedure|Indian Evidence Act"
    r"|Consumer Protection Act,?\s*1986)\b",
    re.IGNORECASE,
)
REPEAL_ACK = re.compile(r"replaced|repealed|Bharatiya|BNS|BNSS|no longer|पुरान|बदल", re.IGNORECASE)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def known_law_names(corpus: dict) -> set[str]:
    return {_norm(e["act"]) for e in corpus.values() if e.get("kind") == "section"}


def validate(raw_text: str, cited_ids: list[str], corpus: dict, retrieved_ids: list[str]) -> dict:
    """Return a report. `ok` is False if anything unverifiable was found."""
    markers = MARKER.findall(raw_text)
    all_ids = list(dict.fromkeys(markers + list(cited_ids or [])))
    unknown_ids = [i for i in all_ids if i not in corpus]
    not_retrieved = [i for i in all_ids if i in corpus and i not in retrieved_ids]

    text_wo_markers = MARKER.sub("", raw_text)
    stray_sections = [m.group(0) for m in STRAY_SECTION.finditer(text_wo_markers)]

    known = known_law_names(corpus)
    unknown_laws = []
    for m in NAMED_LAW.finditer(text_wo_markers):
        name = _norm(m.group(1))
        if not any(k in name or name in k for k in known):
            unknown_laws.append(m.group(1).strip())

    case_law = [m.group(0) for m in CASE_LAW.finditer(text_wo_markers)]

    repealed = [m.group(0) for m in REPEALED.finditer(text_wo_markers)]
    repealed_unacknowledged = repealed if (repealed and not REPEAL_ACK.search(text_wo_markers)) else []

    problems = []
    if unknown_ids:
        problems.append(f"Citation IDs not in corpus: {unknown_ids}")
    if not_retrieved:
        problems.append(f"Citation IDs not among the provided sources: {not_retrieved}")
    if stray_sections:
        problems.append(f"Section/article numbers written as free text (use [[ID]] markers only): {stray_sections}")
    if unknown_laws:
        problems.append(f"Laws named that are not in the verified corpus: {unknown_laws}")
    if case_law:
        problems.append(f"Case law / judgment citations are not allowed: {case_law}")
    if repealed_unacknowledged:
        problems.append(f"Repealed law mentioned as if current: {repealed_unacknowledged}")

    return {
        "ok": not problems,
        "problems": problems,
        "valid_ids": [i for i in all_ids if i in corpus and i in retrieved_ids],
        "unknown_ids": unknown_ids,
        "stray_sections": stray_sections,
        "unknown_laws": unknown_laws,
        "case_law": case_law,
        "repealed_unacknowledged": repealed_unacknowledged,
    }


def strip_unverifiable(raw_text: str, report: dict) -> str:
    """Last-resort cleanup: remove anything the validator flagged."""
    text = raw_text
    for bad in report.get("unknown_ids", []):
        text = text.replace(f"[[{bad}]]", "")
    for frag in report.get("case_law", []) + report.get("stray_sections", []):
        text = text.replace(frag, "[reference removed — could not be verified]")
    return text


def render(raw_text: str, corpus: dict, human_ref, order: list[str] | None = None) -> tuple[str, list[str]]:
    """Replace [[ID]] markers with numbered references; return (text, ordered ids).
    Pass the same `order` list to number references consistently across several texts."""
    order = [] if order is None else order

    def _sub(m):
        cid = m.group(1)
        if cid not in corpus:
            return ""
        if cid not in order:
            order.append(cid)
        return f" [{order.index(cid) + 1}]"

    text = MARKER.sub(_sub, raw_text)
    text = re.sub(r"\s+\[(\d+)\]", r" [\1]", text)
    return text, order
