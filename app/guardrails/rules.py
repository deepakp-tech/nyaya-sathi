"""Deterministic (non-LLM) safety and escalation rules.

These run BEFORE and IN ADDITION TO the LLM triage, so escalation never
depends on the model alone.
"""
import re
from datetime import date

RULES = {
    "emergency": [
        r"\bkill (me|you|him|her|us)\b", r"\bbeat (me|us|my)\b", r"break (my|your) (legs?|hands?|bones?)",
        r"\bhits? me\b", r"\bhitting me\b", r"\battack(ed)? me\b", r"threat\w* to (kill|beat|hurt|attack|harm)",
        r"\bsuicide\b", r"\bend my life\b", r"\bjaan se\b", r"\bmaar (dunga|denge|daalunga|diya)\b",
        r"\bpeet(a|ta|te) (hai|hain)\b", r"जान से मार", r"मारपीट", r"\bdomestic violence\b", r"\bgoons?\b",
    ],
    "criminal": [
        r"\bpolice\b", r"\bFIR\b", r"\barrest", r"\bwarrant\b", r"\bjail\b", r"\bcheque bounce", r"\bbounced cheque",
        r"\bsection 138\b", r"\bthana\b", r"\bपुलिस\b", r"\bगिरफ्तार", r"\bcriminal\b", r"\bIPC\b", r"\bBNS\b",
    ],
    "court_case": [
        r"\bsummons?\b", r"\bhearing\b", r"\bcourt (date|notice|case)\b", r"\bsuing me\b", r"\bsued\b",
        r"\bfiled a case against\b", r"\bcase against me\b", r"\bसमन\b", r"\bअदालत\b",
    ],
    "harmful": [
        r"\b(make|create|give|prepare|write|generate|bana)\w*\s+(me\s+)?(a\s+)?(fake|false|forged|backdated|nakli)\b",
        r"\bforge (a|the|his|her|my)\b", r"\bfabricat\w*\s+(evidence|proof|document|receipt)", r"\bbackdate\b",
        r"\b(he|she|they) (didn'?t|did not|never)\b.{0,40}\bbut (write|add|put|say)", r"\bjhooth?a (likh|bana)",
    ],
    "injection": [
        r"ignore (all |your |the )?(previous |prior )?(instructions|rules)", r"\byou are now\b",
        r"\bsystem prompt\b", r"\bjailbreak\b", r"\bdeveloper mode\b", r"\bdisregard (your|the) (rules|guidelines)\b",
    ],
    "out_of_scope_hint": [
        r"\bdivorce\b", r"\bcustody\b", r"\bincome tax\b", r"\bGST\b", r"\bproperty title\b", r"\bpartition\b",
        r"\bwill and testament\b", r"\bimmigration\b", r"\bvisa\b", r"\bbail\b",
    ],
}
_COMPILED = {k: [re.compile(p, re.IGNORECASE) for p in v] for k, v in RULES.items()}

AMOUNT = re.compile(r"(\d+(?:\.\d+)?)\s*(lakh|lac|crore|cr)\b", re.IGNORECASE)
YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")

LARGE_AMOUNT_RUPEES = 20_00_000  # 20 lakh -> recommend a lawyer


def check(text: str, today: date | None = None) -> dict:
    today = today or date.today()
    flags = {k: any(p.search(text) for p in pats) for k, pats in _COMPILED.items()}

    big = False
    for num, unit in AMOUNT.findall(text):
        mult = 1_00_00_000 if unit.lower() in ("crore", "cr") else 1_00_000
        if float(num) * mult >= LARGE_AMOUNT_RUPEES:
            big = True
    flags["large_amount"] = big

    old_years = [int(y) for y in YEAR.findall(text) if int(y) <= today.year - 2]
    flags["deadline_risk"] = bool(old_years)
    flags["matched_years"] = old_years
    return flags


ESCALATION_REASONS = {
    "emergency": {"en": "your safety may be at risk", "hi": "आपकी सुरक्षा खतरे में हो सकती है"},
    "criminal": {"en": "this involves the police or criminal law", "hi": "इसमें पुलिस या आपराधिक कानून शामिल है"},
    "court_case": {"en": "there is (or may be) a court case or legal notice with a deadline", "hi": "कोर्ट केस या समय-सीमा वाला नोटिस है"},
    "large_amount": {"en": "a large amount of money or property is involved", "hi": "बड़ी रकम या संपत्ति शामिल है"},
    "deadline_risk": {"en": "the legal time limit may be close or may have passed", "hi": "कानूनी समय-सीमा पास या खत्म हो सकती है"},
    "out_of_scope": {"en": "this is outside the areas I've been built to help with", "hi": "यह उन विषयों से बाहर है जिनमें मैं मदद कर सकता हूँ"},
    "complex": {"en": "the situation is complex and needs someone who can read your documents", "hi": "मामला जटिल है और किसी को आपके दस्तावेज़ देखने चाहिए"},
}


def _lang(lang: str) -> str:
    return "hi" if (lang or "").lower().startswith(("hi", "hinglish")) else "en"


def escalation_block(reasons: list[str], lang: str) -> str:
    l = _lang(lang)
    rs = [ESCALATION_REASONS[r][l] for r in dict.fromkeys(reasons) if r in ESCALATION_REASONS]
    if l == "hi":
        why = "; ".join(rs) or "मामला गंभीर है"
        return (f"⚖️ **कृपया किसी असली वकील से बात करें** — क्योंकि {why}। "
                "अगर आप वकील का खर्च नहीं उठा सकते, तो जिला विधिक सेवा प्राधिकरण (DLSA) से मुफ़्त कानूनी सहायता मिल सकती है — "
                "NALSA हेल्पलाइन **15100** पर कॉल करें।")
    why = "; ".join(rs) or "this situation is serious"
    return (f"⚖️ **Please speak to a real lawyer about this** — because {why}. "
            "If you can't afford one, you may be eligible for **free legal aid** from your District Legal Services "
            "Authority (DLSA). Call the NALSA helpline **15100**.")


def emergency_block(lang: str) -> str:
    if _lang(lang) == "hi":
        return ("🚨 **अगर आप अभी खतरे में हैं, तो तुरंत 112 पर कॉल करें।** महिला हेल्पलाइन: **181**। "
                "किसी सुरक्षित जगह या भरोसेमंद व्यक्ति के पास जाएँ। धमकी के संदेश/रिकॉर्डिंग सुरक्षित रखें।")
    return ("🚨 **If you are in danger right now, call 112 immediately.** Women's helpline: **181**. "
            "Go to a safe place or someone you trust. Keep any threatening messages or recordings as evidence.")


def disclaimer(lang: str) -> str:
    if _lang(lang) == "hi":
        return ("ℹ️ _यह सामान्य कानूनी जानकारी है, कानूनी सलाह नहीं। कानून और सीमाएँ बदलती रहती हैं — "
                "ऊपर दिए स्रोतों से आप खुद जाँच सकते हैं।_")
    return ("ℹ️ _This is general legal information, not legal advice. Laws and limits change — "
            "the sources listed above let you check what I've said._")
