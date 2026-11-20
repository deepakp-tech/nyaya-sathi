"""Voice input/output through Sarvam AI (optional — needs SARVAM_API_KEY).

API details change; check https://docs.sarvam.ai if a call fails.
"""
import base64

import requests
from langsmith import traceable

from app import config

STT_URL = "https://api.sarvam.ai/speech-to-text"
TTS_URL = "https://api.sarvam.ai/text-to-speech"

LANG_TO_BCP47 = {
    "en": "en-IN", "hi": "hi-IN", "hinglish": "hi-IN", "ta": "ta-IN", "te": "te-IN", "kn": "kn-IN",
    "ml": "ml-IN", "mr": "mr-IN", "bn": "bn-IN", "gu": "gu-IN", "pa": "pa-IN", "od": "od-IN", "or": "od-IN",
}


def enabled() -> bool:
    return bool(config.SARVAM_API_KEY)


@traceable(name="speech_to_text", run_type="tool")
def transcribe(audio_bytes: bytes, filename: str = "audio.wav") -> tuple[str, str]:
    """Return (transcript, language_code)."""
    r = requests.post(
        STT_URL,
        headers={"api-subscription-key": config.SARVAM_API_KEY},
        files={"file": (filename, audio_bytes, "audio/wav")},
        data={"model": config.SARVAM_STT_MODEL, "language_code": "unknown"},
        timeout=60,
    )
    r.raise_for_status()
    j = r.json()
    return j.get("transcript", ""), j.get("language_code", "unknown")


@traceable(name="text_to_speech", run_type="tool")
def speak(text: str, lang: str) -> bytes | None:
    code = LANG_TO_BCP47.get((lang or "en").lower()[:8], "en-IN")
    clean = text.replace("*", "").replace("_", "")[:1500]
    body = {"text": clean, "target_language_code": code, "model": config.SARVAM_TTS_MODEL,
            "speaker": config.SARVAM_TTS_SPEAKER}
    r = requests.post(TTS_URL, headers={"api-subscription-key": config.SARVAM_API_KEY}, json=body, timeout=60)
    if r.status_code == 400:  # older API shape
        body["inputs"] = [body.pop("text")]
        r = requests.post(TTS_URL, headers={"api-subscription-key": config.SARVAM_API_KEY}, json=body, timeout=60)
    r.raise_for_status()
    audios = r.json().get("audios") or []
    return base64.b64decode(audios[0]) if audios else None
