"""
Neon Command Flavor — Cute / Roasty Anime Girl Response Layer

Transforms dry tool-result messages ("Opened YouTube.") into personality-
flavored confirmations that adapt to Neon's current mood and affection level.

Usage:
    from brain.command_flavor import flavor_command_response
    flavored = flavor_command_response(
        action_name="open_app",
        raw_message="Opened YouTube.",
        user_input="open youtube",
        emotion_status={"emotion": "playful", "intensity": 0.6, "affection": 72},
    )
"""

import random
import time
import re
from collections import deque
from typing import Dict, Optional


# ─────────────────────────────────────────────────────────────────────────────
# 🎯  HISTORY-AWARE PICKER — prevents repeating the same template
# ─────────────────────────────────────────────────────────────────────────────
# Tracks the last N template indices per (action, tier) to avoid repeats.
_recent_picks: Dict[str, deque] = {}
_HISTORY_SIZE = 4  # remember the last 4 picks per pool


def _pick_template(pool: list, action_key: str) -> str:
    """Pick a random template from pool, avoiding recently used ones."""
    if not pool:
        return "{detail}"

    key = action_key
    if key not in _recent_picks:
        _recent_picks[key] = deque(maxlen=_HISTORY_SIZE)

    recent = _recent_picks[key]
    available = [i for i in range(len(pool)) if i not in recent]

    # If all have been used recently, reset and pick from all
    if not available:
        recent.clear()
        available = list(range(len(pool)))

    idx = random.choice(available)
    recent.append(idx)
    return pool[idx]


# ─────────────────────────────────────────────────────────────────────────────
# 🎀  RESPONSE POOLS — grouped by action × mood tier
# ─────────────────────────────────────────────────────────────────────────────

# Tier keys:  "warm"  → high-affection / positive moods (cute + teasing)
#             "cold"  → mad / annoyed moods (curt but still in-character)
#             "base"  → everything else (balanced, cool)

_OPEN_APP = {
    "warm": [
        "On it, Boss~ {app} coming right up!",
        "Say less~ Opening {app} for you now.",
        "Roger that, Boss. {app}'s live, don't get lost in there~",
        "{app}? Good taste. Opening it now, Boss.",
        "One {app}, served fresh~ There you go, Boss.",
        "Already opening {app}, try to keep up~",
        "Your wish, my command~ {app} is up, Boss.",
        "Boom~ {app} is live! What's next, Boss?",
        "{app} loaded! You know where to find me~",
        "Eyes on {app}, Boss. I'll be right here~",
        "There you go~ {app} is all yours, Boss!",
        "Done before you even finished thinking~ {app} is open!",
        "{app}? Let's gooo~ Opening now, Boss!",
    ],
    "cold": [
        "Fine. {app} is open.",
        "{app}. Done.",
        "Opened {app}. Anything else.",
        "{app} is running. Moving on.",
    ],
    "base": [
        "Got it, Boss. {app} is open.",
        "Opening {app} for you now.",
        "{app} is up. Need anything else, Boss?",
        "Done, Boss. {app} is ready.",
        "{app} is live. All set.",
        "Launched {app} for you, Boss.",
        "{app} is good to go, Boss.",
    ],
}

_SEARCH_GOOGLE = {
    "warm": [
        "Searching that up for you, Boss~ Let's see what we find!",
        "On it~ Googling '{query}' right now, Boss.",
        "Curiosity looks good on you, Boss~ Searching now!",
        "Hmm, '{query}'? Let me dig that up for you~",
        "Google time! Searching '{query}', Boss~",
        "Let's see what the internet has to say about '{query}'~",
        "One Google search coming right up~ '{query}', Boss!",
    ],
    "cold": [
        "Searched '{query}'. There.",
        "Google results for '{query}'. Done.",
    ],
    "base": [
        "Searching Google for '{query}', Boss.",
        "Got it. Googling '{query}' now.",
        "Looking up '{query}' for you, Boss.",
        "Google search for '{query}' is open, Boss.",
    ],
}

_SEARCH_YOUTUBE = {
    "warm": [
        "Ooh, let's see what YouTube has~ Searching '{query}' now, Boss!",
        "YouTube dive incoming~ Searching '{query}' for you!",
        "'{query}' on YouTube? You've got taste, Boss~ Opening now!",
        "Let me find that for you on YouTube~ '{query}', right?",
        "YouTube time~ Searching '{query}' for you, Boss!",
        "Let's see what comes up for '{query}' on YouTube~",
    ],
    "cold": [
        "YouTube search for '{query}'. Done.",
        "Searched '{query}' on YouTube.",
    ],
    "base": [
        "Searching YouTube for '{query}', Boss.",
        "On it. YouTube search for '{query}' is up.",
        "Looking that up on YouTube for you, Boss.",
    ],
}

_PLAY_MUSIC = {
    "warm": [
        "Ooh, music time~ Playing '{query}' now, Boss!",
        "'{query}'? Nice pick~ Let me get that playing!",
        "Setting the vibe! '{query}' coming right up, Boss~",
        "DJ Neon on duty~ '{query}' is now playing, Boss!",
        "Good choice, Boss~ '{query}' loading up now!",
        "Music mode activated~ '{query}' for you, Boss!",
        "Oh we're vibing tonight~ '{query}' is on!",
        "The playlist just got upgraded~ '{query}', Boss!",
    ],
    "cold": [
        "Playing '{query}'. There.",
        "Music's on. '{query}'.",
    ],
    "base": [
        "Playing '{query}' now, Boss.",
        "Got it. '{query}' is queued up.",
        "Music time. '{query}' is playing, Boss.",
        "'{query}' is on. Enjoy, Boss.",
    ],
}

_CREATE_FILE = {
    "warm": [
        "File created, Boss~ '{detail}' is all set!",
        "Done and done~ '{detail}' is ready for you, Boss!",
        "Fresh file '{detail}' just for you~ What are we writing, Boss?",
    ],
    "cold": [
        "File '{detail}' created.",
    ],
    "base": [
        "Created '{detail}' in workspace, Boss.",
        "File '{detail}' is ready. Need anything else?",
    ],
}

_DELETE_FILE = {
    "warm": [
        "Poof~ '{detail}' is gone, Boss. No going back now!",
        "Deleted '{detail}' for you. Clean slate, Boss~",
    ],
    "cold": [
        "Deleted '{detail}'. Done.",
    ],
    "base": [
        "'{detail}' has been deleted, Boss.",
        "File gone. '{detail}' is removed.",
    ],
}

_SYSTEM_STATUS = {
    "warm": [
        "Quick status, Boss~ {detail}",
        "Here's the rundown~ {detail}",
        "System check done! {detail}",
        "Everything's looking good, Boss~ {detail}",
        "Your machine report~ {detail}",
    ],
    "cold": [
        "{detail}",
    ],
    "base": [
        "System status: {detail}",
        "Here's your system report, Boss. {detail}",
        "{detail}",
    ],
}

_WHATSAPP = {
    "warm": [
        "Message sent to {detail}, Boss~ Your personal mailbird at your service!",
        "Done~ Delivered to {detail}! Anything else, Boss?",
    ],
    "cold": [
        "Sent to {detail}.",
    ],
    "base": [
        "WhatsApp message sent to {detail}, Boss.",
        "Message delivered to {detail}.",
    ],
}

_VOLUME = {
    "warm": [
        "Volume adjusted, Boss~ {detail}",
        "Sound tuned~ {detail}",
        "Done~ {detail} Let me know if that's right!",
        "Audio tweaked for you, Boss~ {detail}",
    ],
    "cold": [
        "{detail}",
    ],
    "base": [
        "Got it, Boss. {detail}",
        "{detail}",
        "Volume updated. {detail}",
    ],
}

_BRIGHTNESS = {
    "warm": [
        "Brightness adjusted, Boss~ {detail}",
        "Screen vibes updated~ {detail}",
        "There you go~ {detail}",
        "Eyes feeling better now? {detail}",
    ],
    "cold": [
        "{detail}",
    ],
    "base": [
        "Brightness updated, Boss. {detail}",
        "{detail}",
    ],
}

_SCREENSHOT = {
    "warm": [
        "Click~ Screenshot captured, Boss!",
        "Say cheese~ Screenshot saved!",
        "Got it~ Screen captured for you, Boss!",
        "Screenshot locked and loaded, Boss~",
    ],
    "cold": [
        "Screenshot taken.",
    ],
    "base": [
        "Screenshot saved, Boss.",
        "Screen captured, Boss. Saved to workspace.",
    ],
}

_LOCK_SCREEN = {
    "warm": [
        "Locking up~ Your secrets are safe, Boss!",
        "Screen locked! Rest easy, Boss~",
        "Locked it down, Boss. Nobody's getting in!",
    ],
    "cold": [
        "Locked.",
    ],
    "base": [
        "Screen locked, Boss.",
        "PC is locked. All secure.",
    ],
}

_POWER = {
    "warm": [
        "On it, Boss~ {detail}",
        "{detail} Take care, Boss!",
        "Roger that~ {detail}",
    ],
    "cold": [
        "{detail}",
    ],
    "base": [
        "{detail}",
        "Got it, Boss. {detail}",
    ],
}

_CONNECTIVITY = {
    "warm": [
        "Done~ {detail}",
        "{detail} All set, Boss!",
        "Connectivity updated~ {detail}",
    ],
    "cold": [
        "{detail}",
    ],
    "base": [
        "{detail}",
        "Got it, Boss. {detail}",
    ],
}

# Catch-all for unknown actions
_GENERIC = {
    "warm": [
        "Done, Boss~ All taken care of!",
        "Handled it for you, Boss~ Easy peasy!",
        "That's done! What's next, Boss~?",
        "All wrapped up, Boss~ What else you got?",
        "Boom, done! I'm ready for the next one~",
    ],
    "cold": [
        "Done.",
        "Handled.",
    ],
    "base": [
        "Done, Boss. Need anything else?",
        "All set.",
        "Taken care of, Boss.",
    ],
}

# Error responses — when a tool fails
_ERROR = {
    "warm": [
        "Hmm, that didn't work, Boss~ {detail}",
        "Oof, ran into a problem~ {detail}",
        "Something went sideways, Boss. {detail} Let me know if you want to try again!",
        "Well that's awkward~ {detail}",
    ],
    "cold": [
        "Failed. {detail}",
    ],
    "base": [
        "Ran into an issue, Boss. {detail}",
        "That didn't go through. {detail}",
        "Hit a snag, Boss. {detail}",
    ],
}

# Map action_name → pool dict
_ACTION_POOLS = {
    "open_app":               _OPEN_APP,
    "search_google":          _SEARCH_GOOGLE,
    "search_youtube":         _SEARCH_YOUTUBE,
    "play_music":             _PLAY_MUSIC,
    "create_file":            _CREATE_FILE,
    "delete_file":            _DELETE_FILE,
    "system_status":          _SYSTEM_STATUS,
    "send_whatsapp_message":  _WHATSAPP,
    "volume_control":         _VOLUME,
    "brightness_control":     _BRIGHTNESS,
    "take_screenshot":        _SCREENSHOT,
    "lock_screen":            _LOCK_SCREEN,
    "power_control":          _POWER,
    "toggle_connectivity":    _CONNECTIVITY,
}


# ─────────────────────────────────────────────────────────────────────────────
# 🎯  DETAIL EXTRACTION — pull meaningful words from raw message / user input
# ─────────────────────────────────────────────────────────────────────────────

_APP_NAMES_RE = re.compile(
    r"(?:opened?|launch(?:ed|ing)?|start(?:ed|ing)?)\s+(.+?)(?:\s+(?:in|on|for)\b|[.!,]|$)",
    re.IGNORECASE,
)

_QUERY_RE = re.compile(
    r"(?:for|search(?:ed|ing)?)\s+['\"]?(.+?)['\"]?(?:\s+on\b|[.!,]|$)",
    re.IGNORECASE,
)

_QUOTED_TEXT_RE = re.compile(r"'([^']+)'|\"([^\"]+)\"")


def _strip_query_edges(value: str) -> str:
    cleaned = (value or "").strip()
    cleaned = re.sub(
        r"\s+(?:on|in)\s+(?:youtube(?:\s+music)?|spotify|google|mobile|desktop)\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip(" '\".,!?")


def _clean_extracted_query(value: str) -> str:
    cleaned = _strip_query_edges(value)
    cleaned = re.sub(r"^(?:for|search(?:ed|ing)?|query)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _extract_app_name(raw_message: str, user_input: str) -> str:
    """Best-effort app name extraction for display."""
    m = _APP_NAMES_RE.search(raw_message)
    if m:
        cleaned = re.sub(r"\b(mobile|desktop|pc|computer|laptop)\b", "", m.group(1), flags=re.IGNORECASE)
        cleaned = " ".join(cleaned.split())
        return (cleaned or "that").title()
    # Fallback: try user input
    lower = user_input.lower()
    for prefix in ("open ", "launch ", "start "):
        if prefix in lower:
            after = lower.split(prefix, 1)[1].strip()
            words = [
                word for word in after.split()
                if word not in {"mobile", "desktop", "pc", "computer", "laptop", "please", "now"}
            ][:3]
            return " ".join(words).title()
    return "that"


def _extract_query(raw_message: str, user_input: str) -> str:
    """Best-effort query extraction."""
    for m in _QUOTED_TEXT_RE.finditer(raw_message or ""):
        quoted = m.group(1) or m.group(2) or ""
        cleaned = _strip_query_edges(quoted)
        if cleaned:
            return cleaned

    m = _QUERY_RE.search(raw_message or "")
    if m:
        cleaned = _clean_extracted_query(m.group(1))
        if cleaned:
            return cleaned

    lower = (user_input or "").lower()
    for marker in ("play ", "search for ", "search ", "lookup ", "look up ", " for "):
        if marker in lower:
            cleaned = _clean_extracted_query(lower.split(marker, 1)[1])
            if cleaned:
                return cleaned
    return "that"


def _extract_detail(action_name: str, raw_message: str, user_input: str) -> str:
    """Extract a meaningful snippet for template placeholders."""
    if action_name == "open_app":
        return _extract_app_name(raw_message, user_input)
    if action_name in {"search_google", "search_youtube"}:
        return _extract_query(raw_message, user_input)
    if action_name == "play_music":
        return _extract_query(raw_message, user_input)
    if action_name == "send_whatsapp_message":
        # Try to find contact name
        m = re.search(r"to\s+(.+?)(?:\.|$)", raw_message, re.IGNORECASE)
        return m.group(1).strip() if m else "them"
    if action_name in {"create_file", "delete_file"}:
        m = re.search(r"'([^']+)'", raw_message)
        return m.group(1) if m else "the file"
    if action_name in {"volume_control", "brightness_control"}:
        cleaned = raw_message
        for prefix in ("Volume ", "Brightness "):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
        # Capitalize first letter: "set to 50%." -> "Set to 50%."
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]
        return cleaned
    
    # System status / generic: use raw message as detail
    return raw_message


# ─────────────────────────────────────────────────────────────────────────────
# 🌟  MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

_MAD_STATES = {"mad", "angry", "annoyed", "frustrated", "rage", "irritated"}
_WARM_STATES = {"happy", "excited", "playful", "curious", "amused", "warm"}


def flavor_command_response(
    action_name: str,
    raw_message: str,
    user_input: str = "",
    emotion_status: Optional[Dict] = None,
) -> str:
    """
    Takes a dry tool-result message and returns a personality-flavored version.

    Parameters
    ----------
    action_name : str
        The tool function name (e.g. "open_app", "search_google").
    raw_message : str
        The raw message string from SystemController.
    user_input : str
        The original user command text.
    emotion_status : dict
        Neon's current emotional state with keys: emotion, intensity, affection.

    Returns
    -------
    str
        A cute / roasty / cool flavored confirmation message.
    """
    if not raw_message or not raw_message.strip():
        return raw_message or ""

    status = emotion_status or {}
    emotion = (status.get("emotion") or "calm").lower()
    affection = float(status.get("affection", 50.0) or 50.0)

    # Determine if this is an error response
    is_error = any(w in raw_message.lower() for w in ["error", "failed", "not found", "denied", "can't find"])

    # Pick the mood tier
    if emotion in _MAD_STATES:
        tier = "cold"
    elif emotion in _WARM_STATES and affection >= 45:
        tier = "warm"
    elif affection >= 65:
        # High affection even in neutral mood → warm-ish
        tier = "warm"
    else:
        tier = "base"

    # Pick the right pool
    if is_error:
        pool = _ERROR.get(tier, _ERROR["base"])
        pool_key = f"_error_{tier}"
    else:
        action_pool = _ACTION_POOLS.get(action_name, _GENERIC)
        pool = action_pool.get(tier, action_pool.get("base", _GENERIC["base"]))
        pool_key = f"{action_name}_{tier}"

    # Extract detail for template placeholders
    detail = _extract_detail(action_name, raw_message, user_input)

    # History-aware pick (never repeats within last N uses)
    template = _pick_template(pool, pool_key)

    # Fill in template placeholders
    result = template.format(
        app=_extract_app_name(raw_message, user_input),
        query=_extract_query(raw_message, user_input),
        detail=detail,
    )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 🔗  MULTI-ACTION COMBINER — when multiple tools run in one turn
# ─────────────────────────────────────────────────────────────────────────────

def flavor_multi_results(
    results: list,
    user_input: str = "",
    emotion_status: Optional[Dict] = None,
) -> str:
    """
    When multiple tools fire in one turn, combine their flavored results
    into a single natural-sounding response instead of listing them.
    """
    if not results:
        return ""
    if len(results) == 1:
        return results[0]
    
    status = emotion_status or {}
    emotion = (status.get("emotion") or "calm").lower()
    affection = float(status.get("affection", 50.0) or 50.0)
    
    # For warm moods, combine with a cute connector
    if emotion in _WARM_STATES or affection >= 60:
        connectors = [
            " and ",
            "~ Plus, ",
            "! Also, ",
        ]
    else:
        connectors = [" Also, ", " And "]
    
    connector = random.choice(connectors)
    
    # Combine: first result + connector + rest
    combined = results[0].rstrip("!.~ ")
    for r in results[1:]:
        # Lowercase the first char of subsequent results for natural flow
        r_clean = r.strip()
        if r_clean:
            r_clean = r_clean[0].lower() + r_clean[1:] if len(r_clean) > 1 else r_clean.lower()
            combined += connector + r_clean
    
    return combined
