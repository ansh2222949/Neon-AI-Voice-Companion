import re

def postprocess_reply(text: str, clean_for_tts: bool = True) -> str:
    if not text:
        return ""

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
    text = re.sub(r"\([^()]*\)", "", text)

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