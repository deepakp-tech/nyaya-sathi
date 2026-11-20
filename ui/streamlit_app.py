"""Nyaya Saathi — chat UI.   Run:  streamlit run ui/streamlit_app.py"""
import io
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app import config

st.set_page_config(page_title="Nyaya Saathi — AI legal help", page_icon="⚖️", layout="wide",
                   initial_sidebar_state="expanded")

# ------------------------------------------------------------------ styling
st.markdown("""
<style>
.block-container {padding-top: 3.2rem; padding-bottom: 6rem; max-width: 1400px;}
.ns-hero {display:flex; align-items:center; gap:14px; margin-bottom:.25rem;}
.ns-hero .logo {font-size:2.3rem; line-height:1;}
.ns-hero h1 {font-size:1.75rem; margin:0; padding:0; color:#1F4E79; font-weight:700;}
.ns-hero p {margin:0; color:#5B6573; font-size:.95rem;}
.ns-badges {display:flex; flex-wrap:wrap; gap:6px; margin:.6rem 0 1.1rem 0;}
.ns-badge {font-size:.75rem; padding:3px 10px; border-radius:999px; background:#EAF0F7; color:#1F4E79;
           border:1px solid #D5E0EE; white-space:nowrap;}
.ns-chip {display:inline-block; font-size:.78rem; padding:3px 10px; border-radius:999px; margin:2px 4px 2px 0;}
.ns-chip.red {background:#FDECEC; color:#9B1C1C; border:1px solid #F5C2C2;}
.ns-chip.amber {background:#FFF4E0; color:#8A5300; border:1px solid #F3D9A4;}
.ns-chip.green {background:#E8F5EC; color:#1E6B3A; border:1px solid #BFE3CB;}
.ns-chip.grey {background:#F0F2F5; color:#4A5361; border:1px solid #DDE1E7;}
.ns-kv {display:grid; grid-template-columns: 110px 1fr; gap:4px 10px; font-size:.88rem; margin-bottom:.4rem;}
.ns-kv .k {color:#6B7480;}
.ns-tl {border-left:2px solid #D5E0EE; margin:.3rem 0 .6rem .3rem; padding-left:12px; font-size:.87rem;}
.ns-tl div {margin-bottom:6px;}
.ns-tl b {color:#1F4E79;}
.ns-help {font-size:.86rem; line-height:1.7;}
.ns-help b {color:#1F4E79;}
.ns-muted {color:#6B7480; font-size:.85rem;}
.ns-card-title {font-weight:600; margin-bottom:2px;}
.ns-card-desc {color:#5B6573; font-size:.85rem; min-height:2.6em;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ setup check
problems = config.check_setup()
if problems:
    st.error("**Setup needed** — edit your `.env` file:\n\n" + "\n".join(f"- {p}" for p in problems))
    st.stop()

from app import storage, voice  # noqa: E402
from app.service import run_turn, send_feedback  # noqa: E402

# ------------------------------------------------------------------ identity + conversation state
# No login: each browser gets a random user id kept in the URL (?u=...). Bookmark the link to come back to
# your conversations. The open conversation is kept in ?c=... so a page refresh reopens it.
qp = st.query_params
if not qp.get("u"):
    qp["u"] = uuid.uuid4().hex
USER_ID = qp["u"]

PANEL_KEYS = ("case_file", "sources_used", "retrieved_ids", "escalation_reasons", "guard_report", "attempts",
              "pii_redacted", "triage", "raw_llm_answer")


def open_conversation(cid: str | None):
    """Load a conversation from SQLite into the session (None = a fresh, not-yet-saved chat)."""
    st.session_state.conv_id = cid
    st.session_state.chat = storage.get_messages(cid) if cid else []
    st.session_state.last = next((m.get("panel") for m in reversed(st.session_state.chat)
                                  if m["role"] == "assistant" and m.get("panel")), None)
    st.session_state.setdefault("feedback_sent", set())
    if cid:
        qp["c"] = cid
    elif "c" in qp:
        del qp["c"]


if "conv_id" not in st.session_state:
    wanted = qp.get("c")
    open_conversation(wanted if wanted and storage.get_conversation(wanted, USER_ID) else None)

REASON_LABELS = {
    "emergency": ("Safety risk", "red"),
    "criminal": ("Police / criminal matter", "red"),
    "court_case": ("Court case or deadline notice", "red"),
    "large_amount": ("Large amount involved", "amber"),
    "deadline_risk": ("Time limit may be close", "amber"),
    "complex": ("Complex matter", "amber"),
    "out_of_scope": ("Outside my scope", "grey"),
}
QUICK_STARTS = [
    ("🏠", "Deposit not returned", "Get your security deposit back from a landlord.",
     "My landlord hasn't returned my ₹60,000 deposit for 3 months after I moved out. I'm in Bengaluru."),
    ("🛒", "Refund or defective product", "Seller or company refusing a refund or replacement.",
     "Seller refused refund for a phone that arrived broken. I ordered it online 10 days ago."),
    ("💼", "Unpaid salary", "Employer holding back salary or full & final settlement.",
     "My company hasn't paid my last 2 months' salary after I resigned."),
    ("🎭", "Practise the conversation", "I play the other side so you can rehearse.",
     "Can you play my landlord so I can practise asking for my deposit?"),
]
EXAMPLE_PROMPTS = [
    "landlord ne deposit nahi lautaya, paint ke paise kaat raha hai",
    "मेरी कंपनी ने दो महीने से सैलरी नहीं दी है",
    "Draft a legal notice to my landlord for my deposit",
    "I got a police notice about a cheque bounce. What should I do?",
]


def esc(s) -> str:
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def extract_document(f) -> tuple[str, str]:
    """Return (text, error) from an uploaded notice (PDF or text)."""
    data = f.getvalue()
    name = (f.name or "").lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
        else:
            text = data.decode("utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        return "", f"Couldn't read {f.name}: {e}"
    text = text.strip()
    if not text:
        return "", f"No readable text found in {f.name} (scanned PDFs aren't supported yet — paste the text instead)."
    return text[:8000], ""


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("### ⚖️ Nyaya Saathi")
    st.caption("Free legal information for everyday problems in India.")
    if st.button("➕ New conversation", use_container_width=True, type="primary"):
        st.session_state.pop("pending", None)
        open_conversation(None)
        st.rerun()

    convs = storage.list_conversations(USER_ID)
    st.markdown("##### Your conversations")
    if not convs:
        st.caption("Your chats will appear here and are saved automatically.")
    for c in convs:
        current = c["id"] == st.session_state.conv_id
        if st.button(("▸ " if current else "") + c["title"], key=f"conv_{c['id']}", use_container_width=True,
                     type="secondary", disabled=current, help=f"Last active {c['updated_at'][:16].replace('T', ' ')} UTC"):
            st.session_state.pop("pending", None)
            open_conversation(c["id"])
            st.rerun()
    if st.session_state.conv_id:
        with st.popover("🗑️ Delete this conversation", use_container_width=True):
            st.markdown("This permanently deletes the chat, its case file and any drafts.")
            if st.button("Yes, delete it", type="primary", key="confirm_delete"):
                storage.delete_conversation(st.session_state.conv_id, USER_ID)
                open_conversation(None)
                st.rerun()
    st.caption("🔖 Bookmark this page's link to come back to your conversations.")

    st.markdown("##### Settings")
    tts_on = st.toggle("🔊 Read replies aloud", value=False, disabled=not voice.enabled(),
                       help=None if voice.enabled() else "Add SARVAM_API_KEY to .env to enable voice")
    show_debug = st.toggle("🔍 Show technical details", value=False,
                           help="Raw triage, verifier report and retrieved source IDs (for reviewers).")

    st.markdown("##### Need help now?")
    with st.container(border=True):
        st.markdown(
            "<div class='ns-help'>🚨 Emergency: <b>112</b><br>👩 Women's helpline: <b>181</b><br>"
            "⚖️ Free legal aid (NALSA): <b>15100</b><br>🛒 Consumer helpline: <b>1915</b></div>",
            unsafe_allow_html=True)

    with st.expander("How this works"):
        st.markdown(
            "1. Your phone numbers, Aadhaar, PAN etc. are **masked** before anything is sent to the AI.\n"
            "2. I find the relevant laws in a small **curated legal library**.\n"
            "3. The AI answers using **only** those sources; laws are cited as **[1], [2]**.\n"
            "4. A verifier rejects invented sections, case law or repealed laws and asks the AI to retry.\n"
            "5. Police, court, large-amount and deadline issues are **always** flagged for a lawyer.")
    st.caption("I'm not a lawyer. I'll tell you when you need one.")
    st.caption(f"Model: {config.LLM_PROVIDER} / {config.LLM_MODEL}")

# ------------------------------------------------------------------ header
st.markdown("""
<div class="ns-hero"><div class="logo">⚖️</div><div>
<h1>Nyaya Saathi</h1>
<p>Tell me what happened — in any language. I'll explain where you stand, what you can do, and help you act.</p>
</div></div>
<div class="ns-badges">
<span class="ns-badge">📚 Answers grounded in a curated legal library</span>
<span class="ns-badge">🗣️ English · हिन्दी · Hinglish · தமிழ் · more</span>
<span class="ns-badge">🎙️ Voice in & out</span>
<span class="ns-badge">📄 Draft notices as .docx</span>
<span class="ns-badge">🔒 Personal details masked</span>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ input (pinned to bottom)
prompt = st.chat_input(
    "Describe your problem, attach a notice (PDF/TXT), or tap 🎙️ to speak…",
    accept_file=True, file_type=["pdf", "txt"],
    accept_audio=voice.enabled(),
)

incoming = None  # dict(display=..., send=...)
if prompt is not None:
    text = (prompt.text if hasattr(prompt, "text") else str(prompt)) or ""
    files = getattr(prompt, "files", None) or []
    audio = getattr(prompt, "audio", None)
    display_parts, send_parts = [], []
    if audio is not None and voice.enabled():
        try:
            with st.spinner("Listening…"):
                transcript, _ = voice.transcribe(audio.getvalue(), "voice.wav")
            if transcript:
                display_parts.append(f"🎙️ {transcript}")
                send_parts.append(transcript)
            else:
                st.toast("I couldn't hear anything in that recording — please try again.")
        except Exception as e:  # noqa: BLE001
            st.toast(f"Couldn't transcribe audio: {e}")
    if text.strip():
        display_parts.append(text.strip())
        send_parts.append(text.strip())
    for f in files:
        doc, err = extract_document(f)
        if err:
            st.toast(err)
            continue
        if not send_parts:
            send_parts.append("Please explain this notice/document I received: what it means, any deadline, "
                              "and what I should do.")
            display_parts.append("Please explain this document I received.")
        send_parts.append(f"--- Document I received ({f.name}) ---\n{doc}")
        display_parts.append(f"📎 *{f.name}*")
    if send_parts:
        incoming = {"display": "\n\n".join(display_parts), "send": "\n\n".join(send_parts)}

if st.session_state.get("pending"):
    p = st.session_state.pop("pending")
    incoming = {"display": p, "send": p}

# ------------------------------------------------------------------ layout
has_chat = bool(st.session_state.chat) or incoming is not None
if has_chat:
    chat_col, case_col = st.columns([0.63, 0.37], gap="large")
else:
    chat_col, case_col = st.container(), None


def render_assistant_extras(m: dict, i: int):
    if m.get("draft_path") and Path(m["draft_path"]).exists():
        with open(m["draft_path"], "rb") as fh:
            st.download_button("⬇️ Download draft (.docx)", fh.read(), file_name=Path(m["draft_path"]).name,
                               key=f"dl_{m.get('run_id') or i}", type="primary")
        with st.expander("Preview draft"):
            st.text(m.get("draft_text", ""))
    if m.get("audio"):
        st.audio(m["audio"], format="audio/wav")
    if m.get("run_id"):
        fb = st.feedback("thumbs", key=f"fb_{m['run_id']}")
        if fb is not None and m["run_id"] not in st.session_state.feedback_sent:
            st.session_state.feedback_sent.add(m["run_id"])
            sent = send_feedback(m["run_id"], int(fb))
            st.toast("Thanks for the feedback!" + ("" if sent else " (not logged — LangSmith is off)"))


with chat_col:
    if not has_chat:
        st.markdown("#### What do you need help with?")
        cols = st.columns(4)
        for col, (icon, title, desc, example) in zip(cols, QUICK_STARTS):
            with col, st.container(border=True):
                st.markdown(f"<div class='ns-card-title'>{icon} {title}</div>"
                            f"<div class='ns-card-desc'>{desc}</div>", unsafe_allow_html=True)
                if st.button("Start", key=f"qs_{title}", use_container_width=True):
                    st.session_state.pending = example
                    st.rerun()
        st.markdown("#### Or try one of these")
        pick = st.pills("Examples", EXAMPLE_PROMPTS, label_visibility="collapsed", key="example_pills")
        if pick:
            st.session_state.pending = pick
            st.session_state.pop("example_pills", None)
            st.rerun()
        st.markdown(
            "<p class='ns-muted'>You can also <b>attach a notice</b> you received (PDF or text) with the 📎 button, "
            "or <b>speak</b> with 🎙️. I cover tenancy, consumer and salary problems; for anything else I'll point "
            "you to free legal aid.</p>", unsafe_allow_html=True)

    for i, m in enumerate(st.session_state.chat):
        with st.chat_message(m["role"], avatar="🧑" if m["role"] == "user" else "⚖️"):
            st.markdown(m["content"])
            if m["role"] == "assistant":
                render_assistant_extras(m, i)

    if incoming:
        st.session_state.chat.append({"role": "user", "content": incoming["display"]})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(incoming["display"])
        is_new = st.session_state.conv_id is None
        conv_id = st.session_state.conv_id or storage.new_id()  # conversation id == LangGraph thread_id
        with st.chat_message("assistant", avatar="⚖️"):
            with st.spinner("Understanding your problem and checking sources…"):
                try:
                    res = run_turn(conv_id, incoming["send"], tags=["ui"], extra_metadata={"user_id": USER_ID})
                except Exception as e:  # noqa: BLE001
                    st.session_state.chat.pop()
                    st.error(f"Something went wrong — please try again. ({type(e).__name__}: {e})")
                    st.stop()
            panel = {k: res.get(k) for k in PANEL_KEYS}
            msg = {"role": "assistant", "content": res["reply"], "run_id": res["run_id"],
                   "draft_path": res["draft_path"], "draft_text": res["draft_text"], "panel": panel}
            # persist: the conversation row is created only once the first turn succeeded
            if is_new:
                storage.create_conversation(USER_ID, incoming["display"], conversation_id=conv_id)
            storage.add_message(conv_id, "user", incoming["display"])
            storage.add_message(conv_id, "assistant", res["reply"],
                                {k: msg[k] for k in ("run_id", "draft_path", "draft_text", "panel")})
            if tts_on:  # audio is kept for this session only, not stored
                try:
                    with st.spinner("Preparing audio…"):
                        msg["audio"] = voice.speak(res["reply"], (res.get("triage") or {}).get("language", "en"))
                except Exception as e:  # noqa: BLE001
                    st.toast(f"Voice unavailable: {e}")
            st.session_state.chat.append(msg)
            st.session_state.last = panel
            if is_new:
                st.session_state.conv_id = conv_id
                qp["c"] = conv_id
        st.rerun()

# ------------------------------------------------------------------ case panel
def render_case_file(cf: dict):
    if not cf:
        st.markdown("<p class='ns-muted'>As you describe your problem, I'll build a case file here: who, what, "
                    "when, how much, and what evidence you have.</p>", unsafe_allow_html=True)
        return
    rows = [
        ("Problem", (cf.get("problem_type") or "").replace("_", " ").capitalize()),
        ("You are", cf.get("user_role")),
        ("Other party", cf.get("other_party")),
        ("Location", ", ".join(x for x in [cf.get("location_city"), cf.get("location_state")] if x)),
        ("Amount", f"₹{cf['amount_in_dispute']:,.0f}" if cf.get("amount_in_dispute") else None),
        ("Your goal", cf.get("user_goal")),
    ]
    st.markdown("<div class='ns-kv'>" + "".join(
        f"<div class='k'>{k}</div><div>{esc(v)}</div>" for k, v in rows if v) + "</div>", unsafe_allow_html=True)
    if cf.get("timeline"):
        st.markdown("**Timeline**")
        st.markdown("<div class='ns-tl'>" + "".join(
            f"<div><b>{esc(e.get('date'))}</b> — {esc(e.get('event'))}</div>" for e in cf["timeline"]) + "</div>",
            unsafe_allow_html=True)
    if cf.get("evidence_have") or cf.get("evidence_missing"):
        st.markdown("**Evidence**")
        chips = "".join(f"<span class='ns-chip green'>✓ {esc(x)}</span>" for x in cf.get("evidence_have", []))
        chips += "".join(f"<span class='ns-chip amber'>+ {esc(x)}</span>" for x in cf.get("evidence_missing", []))
        st.markdown(chips, unsafe_allow_html=True)
        if cf.get("evidence_missing"):
            st.caption("Amber items would strengthen your case — try to collect them.")
    if cf.get("prior_actions"):
        st.markdown("**What you've already tried**")
        st.markdown("\n".join(f"- {x}" for x in cf["prior_actions"]))
    if cf.get("missing_info") and not cf.get("ready_for_advice"):
        st.markdown("**I still need to know**")
        st.markdown("\n".join(f"- {x}" for x in cf["missing_info"]))


def render_sources(res: dict):
    used = res.get("sources_used") or []
    if not used:
        st.markdown("<p class='ns-muted'>No laws were cited in the last reply.</p>", unsafe_allow_html=True)
    for n, s in enumerate(used, 1):
        badge = ("<span class='ns-chip green'>✔ verified</span>" if s.get("verified")
                 else "<span class='ns-chip amber'>⚠ pending verification</span>")
        st.markdown(f"**[{n}]** {esc(s.get('ref'))}<br>{badge}", unsafe_allow_html=True)
    st.caption(f"{len(res.get('retrieved_ids') or [])} passages from the legal library were given to the AI; "
               "it may cite only these.")


def render_checks(res: dict):
    reasons = res.get("escalation_reasons") or []
    st.markdown("**Should you see a lawyer?**")
    if reasons:
        st.markdown("".join(
            f"<span class='ns-chip {REASON_LABELS.get(r, (r, 'grey'))[1]}'>{esc(REASON_LABELS.get(r, (r,))[0])}</span>"
            for r in reasons), unsafe_allow_html=True)
        st.caption("Free legal aid: call 15100 or visit your District Legal Services Authority.")
    else:
        st.markdown("<span class='ns-chip green'>No red flags detected</span>", unsafe_allow_html=True)

    st.markdown("**Answer checks**")
    rep = res.get("guard_report") or {}
    if not rep:
        st.markdown("<span class='ns-chip grey'>No legal claims in this reply</span>", unsafe_allow_html=True)
    else:
        ok = rep.get("ok")
        attempts = res.get("attempts") or 1
        st.markdown(
            (f"<span class='ns-chip green'>✓ Passed citation & grounding checks</span>" if ok
             else "<span class='ns-chip amber'>Unverifiable parts removed</span>")
            + (f"<span class='ns-chip grey'>{attempts} attempt{'s' if attempts > 1 else ''}</span>")
            + ("<span class='ns-chip grey'>Rewritten after verifier feedback</span>" if attempts > 1 else ""),
            unsafe_allow_html=True)
    pii = res.get("pii_redacted") or []
    st.markdown("**Privacy**")
    st.markdown(f"<span class='ns-chip green'>🔒 Masked before AI: {esc(', '.join(pii))}</span>" if pii
                else "<span class='ns-chip grey'>No personal identifiers detected</span>", unsafe_allow_html=True)


if case_col is not None:
    with case_col:
        res = st.session_state.get("last") or {}
        with st.container(border=True):
            st.markdown("#### 📁 Your case")
            t1, t2, t3 = st.tabs(["Case file", "Sources", "Safety checks"])
            with t1:
                render_case_file(res.get("case_file") or {})
            with t2:
                render_sources(res)
            with t3:
                render_checks(res)
        if show_debug and res:
            with st.expander("🔍 Technical details", expanded=False):
                st.write("**Triage:**", res.get("triage"))
                st.write("**Retrieved source IDs:**", res.get("retrieved_ids"))
                st.write("**Verifier report:**", res.get("guard_report"))
                st.write("**Raw LLM answer:**", res.get("raw_llm_answer"))
