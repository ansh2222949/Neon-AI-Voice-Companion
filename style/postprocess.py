import re


_SMART_PUNCT_TRANSLATION = str.maketrans({
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "—": " - ",
    "–": " - ",
    "…": "...",
})

def postprocess_reply(text: str, clean_for_tts: bool = True) -> str:
    if not text:
        return ""

    text = text.translate(_SMART_PUNCT_TRANSLATION)

    # ---------------------------------------------------------
    # 1. 🚫 REMOVE INTERNAL CONTROL TOKENS (Fixed Root Cause)
    # ---------------------------------------------------------
    # Matches "TYPE A:", "TYPE B:", "TYPE C:" followed by text until a dot or newline
    text = re.sub(
        r'\bTYPE\s*[ABC]\s*:\s*[^.\n]*', 
        '', 
        text, 
        flags=re.IGNORECASE
    )

    # ---------------------------------------------------------
    # 2. Standard Cleanup
    # ---------------------------------------------------------

    # Remove speaker labels (multiline-safe)
    text = re.sub(
        r"^\s*(Neon|Assistant|User|System)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE
    )

    # Remove parenthesis actions (TTS safety)
    text = re.sub(r"\*.*?\*", "", text)
    text = re.sub(r"\([^()]*\)", "", text)
    text = re.sub(r"\s*[\r\n]+\s*", ". ", text)

    if clean_for_tts:
        # Remove emojis / non-ASCII
        text = re.sub(r"[^\x00-\x7F]+", "", text)

        # Remove markdown
        text = re.sub(r"\*+|`+", "", text)

        # Expand slang
        slang_map = {
            r"\bidc\b": "I don't care",
            r"\bidk\b": "I don't know",
            r"\brn\b": "right now",
            r"\btbh\b": "to be honest",
            r"\bplz\b": "please",
            r"\bpls\b": "please",
            r"\bcuz\b": "because",
            r"\bcos\b": "because",
            r"\bnvm\b": "never mind",
            r"\bjk\b": "just kidding",
            r"\bwdym\b": "what do you mean"
        }

        for k, v in slang_map.items():
            text = re.sub(k, v, text, flags=re.IGNORECASE)

    # Cleanup spacing & punctuation
    text = re.sub(r"\s+", " ", text).strip()
    
    # Ensure space after punctuation if missing (e.g., "Hello.How are you")
    text = re.sub(r'([?.!,])(?=[A-Za-z])', r'\1 ', text)

    if not text:
        return "Hmm?"

    text = text.lstrip()
    
    # Capitalize first letter
    return text[0].upper() + text[1:]


def _looks_like_system_reply(text: str) -> bool:
    lower = (text or "").lower()
    markers = (
        "services:",
        "system status:",
        "system check",
        "diagnostics",
        "cpu:",
        "ram:",
        "gpu:",
        "battery:",
        "uptime",
        "top ram hogs",
    )
    return sum(1 for marker in markers if marker in lower) >= 2


def _summarize_system_speech(text: str) -> str:
    lower = text.lower()
    states = {
        "Ollama": "ollama: ok" in lower,
        "TTS": "tts: ok" in lower,
        "Backend": "backend: ok" in lower,
    }
    down = [name for name, ok in states.items() if not ok]
    if down:
        verb = "is" if len(down) == 1 else "are"
        items = ", ".join(down)
        return f"Quick status, Boss. {items} {verb} having trouble."
    return "All systems look good, Boss."


def prepare_tts_text(text: str, max_chars: int = 360) -> str:
    text = postprocess_reply(text, clean_for_tts=False)
    if not text:
        return ""

    if _looks_like_system_reply(text):
        return _summarize_system_speech(text)

    text = text.translate(_SMART_PUNCT_TRANSLATION)
    text = re.sub(r"[`#]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([?.!,])", r"\1", text)
    text = re.sub(r"([?.!,])(?=[A-Za-z])", r"\1 ", text)

    if len(text) > max_chars:
        trimmed = text[:max_chars]
        sentence_breaks = [trimmed.rfind(p) for p in ".!?"]
        best_break = max(sentence_breaks)
        if best_break >= max_chars // 2:
            text = trimmed[:best_break + 1].strip()
        else:
            text = trimmed.rsplit(" ", 1)[0].rstrip(" ,")
            if text and text[-1] not in ".!?":
                text += "."

    return text
