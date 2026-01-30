import re

def postprocess_reply(text: str, clean_for_tts: bool = True) -> str:
    """
    Advanced Text Cleanup Pipeline.
    Ensures output is clean, readable, and safe for TTS engines.
    """
    if not text:
        return ""

    # --- STEP 1: SAFETY CUT-OFF (Anti-Hallucination) ---
    stop_triggers = ["User:", "System:", "### Response:", "### Instruction:"]
    for trigger in stop_triggers:
        if trigger in text:
            text = text.split(trigger)[0]

    # --- STEP 2: REMOVE SYSTEM ARTIFACTS ---
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(Context:.*?\)", "", text)

    # --- STEP 3A: ACTION REMOVAL (ASTERISKED) ---
    # *smirks*, *laughs*, etc.
    text = re.sub(r"\*[^*]+\*", "", text)

    # --- STEP 3B: ACTION REMOVAL (BARE WORDS) ✅ FIX ---
    # rolls eyes, sighs, smirks (without asterisks)
    text = re.sub(
        r"\b(rolls eyes|rolls eye|sighs|smirks|giggles|laughs|eye roll|eyeroll)\b",
        "",
        text,
        flags=re.IGNORECASE
    )

    # --- STEP 4: CLEAN FOR TTS ---
    if clean_for_tts:
        # Remove emojis / weird symbols
        text = re.sub(r"[^\w\s,!.?']", "", text)

        # Expand common abbreviations
        text = text.replace(" idc ", " I don't care ")
        text = text.replace(" idk ", " I don't know ")
        text = text.replace(" rn ", " right now ")

    # --- STEP 5: GRAMMAR & PUNCTUATION REPAIR ---
    text = re.sub(r'\s+([?.!,"])', r'\1', text)
    text = re.sub(r'\.(?=[A-Z])', '. ', text)

    # --- STEP 6: FINAL POLISH ---
    text = re.sub(r"\s+", " ", text).strip()

    if text:
        text = text[0].upper() + text[1:]

    return text
