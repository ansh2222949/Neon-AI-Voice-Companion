import random
import time
from typing import Optional, Dict


def _clamp01(x: float) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return 0.5


def _pick(rng: random.Random, items: list[str]) -> str:
    return items[rng.randrange(0, len(items))]


def add_lived_in_personality(
    reply: str,
    status: Dict,
    *,
    user_input: str,
    seconds_since_last_user_msg: Optional[float] = None,
    signature_phrase: Optional[str] = None,
    banter_mode: str = "balanced",
    allow: bool = True,
) -> str:
    """
    Adds tiny "alive" touches without changing meaning.
    Rules:
    - Never runs for empty replies
    - Never adds emojis/markdown (TTS + postprocess safety)
    - Must be non-spammy: low probability, short, and only when allowed
    """
    if not allow:
        return reply
    if not reply or not reply.strip():
        return reply

    # Deterministic-ish per turn so it doesn't flicker wildly if retried.
    seed = int(time.time() // 7)  # changes ~every 7 seconds
    rng = random.Random(seed)

    emotion = (status or {}).get("emotion", "calm") or "calm"
    affection = float((status or {}).get("affection", 50.0) or 50.0)
    intensity = _clamp01((status or {}).get("intensity", 0.5))
    banter_mode = (banter_mode or "balanced").strip().lower()

    # Keep it subtle. Higher affection = slightly more "present".
    base_chance = 0.10 + (max(0.0, affection - 50.0) / 100.0) * 0.08  # 10% → 18%
    if intensity > 0.75:
        base_chance -= 0.03
    if base_chance <= 0.0 or rng.random() > base_chance:
        return reply

    lower_in = (user_input or "").strip().lower()
    # Don't decorate super-short commands like "ok", "yes", etc.
    if len(lower_in) <= 2:
        return reply

    # Time-gap acknowledgement (rare, only if there was a real gap)
    if seconds_since_last_user_msg is not None and seconds_since_last_user_msg > 120 and rng.random() < 0.4:
        gap_line = _pick(
            rng,
            [
                "There you are.",
                "Back in one piece, good.",
                "Alright. I'm here.",
            ],
        )
        # Only prepend if reply doesn't already start similarly.
        if not reply.lower().startswith(("there you", "back", "alright")):
            return f"{gap_line} {reply}"

    # Curious mode: add one focused follow-up question sometimes (best-friend vibe).
    if banter_mode in {"curious", "balanced"} and affection >= 45 and rng.random() < (0.22 if banter_mode == "curious" else 0.12):
        q = _pick(
            rng,
            [
                "What do you actually want out of this?",
                "What's the real goal here, Boss?",
                "Okay, quick one: what matters most to you right now?",
                "Be honest. What's the part you're not saying out loud?",
            ],
        )
        # Avoid stacking if reply already contains a question.
        if "?" not in reply:
            if reply.endswith((".", "!", "?")):
                reply = f"{reply} {q}"
            else:
                reply = f"{reply}. {q}"

    # Roaster mode: light tease (never mean), only when relationship allows it.
    if banter_mode in {"roaster", "balanced"} and affection >= 60 and emotion not in {"mad", "angry"} and rng.random() < (0.20 if banter_mode == "roaster" else 0.10):
        roast = _pick(
            rng,
            [
                "You're chaos, but you're my kind of chaos.",
                "You say that like you didn't already know the answer.",
                "Bold move. Questionable timing. I respect it.",
                "You're adorable when you pretend you're not overthinking.",
            ],
        )
        # Keep roast short and append as a single line.
        if reply.endswith((".", "!", "?")):
            reply = f"{reply} {roast}"
        else:
            reply = f"{reply}. {roast}"

    # Mood-flavored micro-tag lines (short, no extra questions)
    if emotion in {"warm", "playful", "happy", "excited", "amused", "curious"}:
        tag = _pick(
            rng,
            [
                "Talk to me.",
                "Keep going.",
                "I'm listening.",
            ],
        )
        # Add as a short closer if not already ending with punctuation-heavy flourish.
        if reply.endswith((".", "!", "?")):
            return f"{reply} {tag}"
        return f"{reply}. {tag}"

    if emotion in {"mad", "angry", "annoyed", "frustrated", "irritated"}:
        # Still minimal; do not escalate.
        tag = _pick(
            rng,
            [
                "Make it quick.",
                "Say it straight.",
            ],
        )
        if reply.endswith((".", "!", "?")):
            return f"{reply} {tag}"
        return f"{reply}. {tag}"

    if emotion in {"bored", "tired", "sad", "stressed", "anxious", "worried"}:
        tag = _pick(
            rng,
            [
                "Slow down. I'm with you.",
                "One thing at a time.",
                "I'm here. Keep it simple.",
            ],
        )
        if reply.endswith((".", "!", "?")):
            return f"{reply} {tag}"
        return f"{reply}. {tag}"

    # Baseline
    # Prefer stable signature when available (makes her feel consistent).
    if signature_phrase and isinstance(signature_phrase, str):
        tag = signature_phrase.strip()
    else:
        tag = _pick(rng, ["Alright.", "Got you."])
    if reply.endswith((".", "!", "?")):
        return f"{reply} {tag}"
    return f"{reply}. {tag}"

