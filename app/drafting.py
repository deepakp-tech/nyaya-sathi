"""Render a NoticeDraft into plain text and a .docx file."""
import re
from datetime import date
from pathlib import Path

from app import config


def draft_to_text(d: dict) -> str:
    lines = [
        f"{d.get('doc_type', 'Legal notice').upper()}",
        "",
        f"Date: {date.today().strftime('%d %B %Y')}",
        "Sent by: Registered Post A.D. / Speed Post / Email",
        "",
        "From:", d.get("sender_name", "[YOUR NAME]"), d.get("sender_address", "[YOUR ADDRESS]"),
        "",
        "To:", d.get("recipient_name", "[RECIPIENT NAME]"), d.get("recipient_address", "[RECIPIENT ADDRESS]"),
        "",
        f"Subject: {d.get('subject', '')}",
        "",
        "Sir/Madam,",
        "",
    ]
    n = 1
    for f in d.get("facts", []):
        lines.append(f"{n}. {f}")
        n += 1
    for lb in d.get("legal_basis", []):
        lines.append(f"{n}. {lb}")
        n += 1
    if d.get("demands"):
        lines.append(f"{n}. I therefore call upon you to, within {d.get('deadline_days', 15)} days of receipt of this notice:")
        for i, dm in enumerate(d["demands"]):
            lines.append(f"   ({chr(97 + i)}) {dm}")
        n += 1
    if d.get("consequence"):
        lines.append(f"{n}. {d['consequence']}")
    lines += ["", "Yours faithfully,", "", d.get("sender_name", "[YOUR NAME]"), "(Signature)"]
    if d.get("sources"):
        lines += ["", "References:"] + [f"[{s['n']}] {s['ref']}" for s in d["sources"]]
    lines += ["", "Note: Prepared with an AI assistant from facts supplied by the sender. "
              "Please have it reviewed by an advocate before sending."]
    return "\n".join(lines)


def save_docx(d: dict, filename_hint: str = "draft", out_dir: Path | None = None, unique: str | None = None) -> Path:
    """Write the draft as .docx. With out_dir/unique (per conversation + run) files never overwrite each other."""
    from docx import Document
    from docx.shared import Pt

    folder = out_dir or config.DRAFT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", filename_hint)[:40] or "draft"
    suffix = f"_{unique}" if unique else ""
    path = folder / f"{safe}_{date.today().isoformat()}{suffix}.docx"

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)
    text = draft_to_text(d)
    first = True
    for line in text.split("\n"):
        if first:
            doc.add_heading(line, level=1)
            first = False
        elif line.startswith("Subject:"):
            p = doc.add_paragraph()
            p.add_run(line).bold = True
        else:
            doc.add_paragraph(line)
    doc.save(path)
    return path
