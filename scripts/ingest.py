"""Build the vector index from corpus/sections.jsonl + corpus/playbooks/.

    python scripts/ingest.py                 # build / rebuild the index
    python scripts/ingest.py --pdf acts/     # ALSO extract sections from India Code PDFs into
                                             # corpus/candidates.jsonl for HUMAN review (not auto-trusted)
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.corpus_store import build_index, load_corpus  # noqa: E402

SECTION_SPLIT = re.compile(r"\n\s*(\d{1,3}[A-Z]?)\.\s+([A-Z][^\n.—-]{2,120})[.—-]")


def extract_pdf(pdf_path: Path) -> list[dict]:
    from pypdf import PdfReader
    text = "\n".join(p.extract_text() or "" for p in PdfReader(str(pdf_path)).pages)
    act = pdf_path.stem.replace("_", " ")
    out = []
    matches = list(SECTION_SPLIT.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = re.sub(r"\s+", " ", text[m.end():end]).strip()
        out.append({"id": f"CAND_{re.sub(r'[^A-Z0-9]', '', act.upper())[:12]}_S{m.group(1)}",
                    "act": act, "section": m.group(1), "title": m.group(2).strip(),
                    "summary": body[:1500], "topics": [], "status": "in_force",
                    "jurisdiction": "Central", "source_url": "https://www.indiacode.nic.in/",
                    "verified": False, "verified_on": None})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", help="folder of bare-act PDFs downloaded from indiacode.nic.in")
    a = ap.parse_args()

    if a.pdf:
        cands = []
        for p in sorted(Path(a.pdf).glob("*.pdf")):
            secs = extract_pdf(p)
            print(f"{p.name}: {len(secs)} sections extracted")
            cands += secs
        out = ROOT / "corpus" / "candidates.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            for c in cands:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        print(f"\nWrote {len(cands)} candidates to {out}. Review them, then copy the ones you need "
              "into corpus/sections.jsonl (add topics + a plain-language summary).")

    print(f"Corpus entries: {len(load_corpus())}")
    n = build_index()
    print(f"Vector index built with {n} documents.")


if __name__ == "__main__":
    main()
