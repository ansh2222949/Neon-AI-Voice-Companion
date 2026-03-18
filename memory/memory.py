import json
import os
import time
import threading
from typing import Dict, Any, Optional

# ── PATH SETUP ────────────────────────────────────────────────────────────────
# FIX 1: Always resolved relative to this file — works from any CWD
_HERE        = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR   = os.path.join(_HERE, "state")
MEMORY_FILE  = os.path.join(MEMORY_DIR, "state.json")

# FIX 9: Schema version — increment when fields change
SCHEMA_VERSION = 4

# ── DEFAULTS ──────────────────────────────────────────────────────────────────
_DEFAULTS: Dict[str, Any] = {
    "schema_version":   SCHEMA_VERSION,
    "user_name":        "Ansh",
    "user_role":        "Boss",
    "affection":        50.0,
    "grudge_score":     0.0,
    "insult_count":     0,       # FIX 2: now persisted
    "intensity":        0.5,     # FIX 2: now persisted
    "emotion":          "calm",
    "last_interaction": None,    # None = first ever launch
    "total_turns":      0,
    # Persistent preferences (advanced / "alive" upgrades)
    "prefs": {
        "music_platform": "spotify",   # spotify | youtube
        "voice_style":    "default",   # default | calm | energetic | soft
        # Personality preference (persisted)
        # balanced: a bit of everything
        # roaster:  more teasing/banter (still kind)
        # curious:  asks one focused follow-up question more often
        "banter_mode":    "balanced",  # balanced | roaster | curious
    },
    # Persistent quirks (subtle, stable, evolves over time)
    "quirks": {
        "signature_phrase": "Got you.",
        "signature_tier":   "baseline",
    },
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

def _safe_float(value: Any, default: float) -> float:
    """FIX 8: Validates any loaded value to a clean float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _migrate(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    FIX 9: Forward-migrate old schema files.
    Add new migration blocks here as schema evolves.
    """
    version = data.get("schema_version", 1)

    if version < 2:
        # v1 → v2: added insult_count and intensity fields
        data.setdefault("insult_count", 0)
        data.setdefault("intensity",    0.5)
        data["schema_version"] = 2
        print("[MEMORY] Migrated state.json: v1 -> v2")

    if version < 3:
        # v2 → v3: add prefs + quirks
        data.setdefault("prefs", {})
        if not isinstance(data.get("prefs"), dict):
            data["prefs"] = {}
        data["prefs"].setdefault("music_platform", "spotify")
        data["prefs"].setdefault("voice_style", "default")

        data.setdefault("quirks", {})
        if not isinstance(data.get("quirks"), dict):
            data["quirks"] = {}
        data["quirks"].setdefault("signature_phrase", "Got you.")
        data["quirks"].setdefault("signature_tier", "baseline")

        data["schema_version"] = 3
        print("[MEMORY] Migrated state.json: v2 -> v3")

    if version < 4:
        # v3 -> v4: add banter_mode preference
        data.setdefault("prefs", {})
        if not isinstance(data.get("prefs"), dict):
            data["prefs"] = {}
        data["prefs"].setdefault("banter_mode", "balanced")
        data["schema_version"] = 4
        print("[MEMORY] Migrated state.json: v3 -> v4")

    return data


def _normalize_prefs(prefs: Any) -> Dict[str, Any]:
    if not isinstance(prefs, dict):
        prefs = {}
    music = str(prefs.get("music_platform", "spotify") or "spotify").strip().lower()
    if music not in {"spotify", "youtube"}:
        music = "spotify"
    voice = str(prefs.get("voice_style", "default") or "default").strip().lower()
    if voice not in {"default", "calm", "energetic", "soft"}:
        voice = "default"
    banter = str(prefs.get("banter_mode", "balanced") or "balanced").strip().lower()
    if banter not in {"balanced", "roaster", "curious"}:
        banter = "balanced"
    return {"music_platform": music, "voice_style": voice, "banter_mode": banter}


def _evolve_signature(quirks: Any, affection: float, total_turns: int) -> Dict[str, Any]:
    """
    Keeps a stable signature phrase that can evolve as affection grows.
    Evolution is rare and tier-based, so it feels consistent (not random noise).
    """
    if not isinstance(quirks, dict):
        quirks = {}

    # Tier selection by affection
    if affection >= 85:
        tier = "right_hand"
        pool = ["I'm with you.", "Say the word.", "I've got you."]
    elif affection >= 60:
        tier = "close"
        pool = ["Got you.", "Talk to me.", "Keep going."]
    elif affection >= 35:
        tier = "trusted"
        pool = ["Alright.", "Got it.", "Go on."]
    else:
        tier = "baseline"
        pool = ["Okay.", "Understood.", "Fine."]

    cur_tier = str(quirks.get("signature_tier", "baseline") or "baseline")
    cur_phrase = str(quirks.get("signature_phrase", "") or "").strip()
    if not cur_phrase:
        cur_phrase = pool[0]

    # Change phrase when tier changes, or very rarely over time
    should_rotate = (cur_tier != tier) or (total_turns > 0 and total_turns % 40 == 0)
    if should_rotate:
        # Deterministic pick per rotation point
        idx = abs(hash(f"{tier}:{total_turns}")) % len(pool)
        cur_phrase = pool[idx]

    return {"signature_phrase": cur_phrase, "signature_tier": tier}


# ─────────────────────────────────────────────────────────────────────────────
class MemoryManager:
    """
    Persistent state manager for Neon.

    Handles:
    - Safe load with schema migration
    - Atomic cross-platform save
    - Full emotion engine restore (all fields)
    - Intelligent time-gap context generation
    - Thread-safe total_turns counter
    """

    def __init__(self):
        os.makedirs(MEMORY_DIR, exist_ok=True)
        self._lock  = threading.Lock()   # FIX 5: guards total_turns + atomic write
        self.state  = self._load()

    # ── LOAD ──────────────────────────────────────────────────────────────────

    def _load(self) -> Dict[str, Any]:
        """
        Loads and validates state.json.
        Falls back to defaults on corruption.
        Enforces identity lock + schema migration.
        """
        if not os.path.exists(MEMORY_FILE):
            return dict(_DEFAULTS)

        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)

            # FIX 9: Migrate old schemas before use
            raw = _migrate(raw)

            # Merge: defaults fill any missing keys, then loaded values win
            merged = {**_DEFAULTS, **raw}

            # FIX 6: Identity lock applied cleanly post-merge
            merged["user_name"] = "Ansh"
            merged["user_role"] = "Boss"

            # FIX 8: Validate all numeric fields
            merged["affection"]    = _safe_float(merged["affection"],    50.0)
            merged["grudge_score"] = _safe_float(merged["grudge_score"],  0.0)
            merged["intensity"]    = _safe_float(merged["intensity"],     0.5)
            merged["insult_count"] = _safe_int(  merged["insult_count"],  0)
            merged["total_turns"]  = _safe_int(  merged["total_turns"],   0)

            # Validate prefs / quirks
            merged["prefs"] = _normalize_prefs(merged.get("prefs"))
            merged["quirks"] = _evolve_signature(
                merged.get("quirks"),
                affection=merged["affection"],
                total_turns=merged["total_turns"],
            )

            return merged

        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] [MEMORY] Corrupted state.json ({e}). Resetting to defaults.")
            return dict(_DEFAULTS)

    # ── SAVE ──────────────────────────────────────────────────────────────────

    def save(self, engine_status: Dict[str, Any]) -> None:
        """
        Thread-safe atomic save.
        Persists full engine state including intensity and insult_count.
        """
        with self._lock:
            # FIX 2: Save ALL engine fields, not just 3
            affection = _safe_float(engine_status.get("affection"), 50.0)
            total_turns = self.state.get("total_turns", 0) + 1
            self.state.update({
                "affection":        affection,
                "grudge_score":     _safe_float(engine_status.get("grudge_score"),  0.0),
                "intensity":        _safe_float(engine_status.get("intensity"),     0.5),
                "insult_count":     _safe_int(  engine_status.get("insult_count"),  0),
                "emotion":          engine_status.get("emotion", "calm"),
                "last_interaction": time.time(),
                # FIX 5: increment inside lock — no race condition
                "total_turns":      total_turns,
                "schema_version":   SCHEMA_VERSION,
            })

            # Keep prefs normalized and evolve quirks slowly.
            self.state["prefs"] = _normalize_prefs(self.state.get("prefs"))
            self.state["quirks"] = _evolve_signature(
                self.state.get("quirks"),
                affection=affection,
                total_turns=total_turns,
            )

            # FIX 7: os.replace() is atomic on all platforms (Linux, macOS, Windows)
            temp_file = MEMORY_FILE + ".tmp"
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(self.state, f, indent=2, ensure_ascii=False)
                os.replace(temp_file, MEMORY_FILE)
            except Exception as e:
                print(f"[ERROR] [MEMORY] Save failed: {e}")
                # Clean up orphaned temp file if it exists
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass

    # ── RESTORE ───────────────────────────────────────────────────────────────

    def restore(self, emotion_engine) -> Dict[str, Any]:
        """
        Restores full engine state and returns structured boot context.

        Restored fields: affection, grudge_score, intensity, insult_count, emotion.
        Returns a context dict that brain.py injects into the system prompt.
        """
        # FIX 2: Restore ALL fields — engine wakes up exactly as it shut down
        emotion_engine.status["affection"]    = _safe_float(self.state.get("affection"),    50.0)
        emotion_engine.status["grudge_score"] = _safe_float(self.state.get("grudge_score"),  0.0)
        emotion_engine.status["intensity"]    = _safe_float(self.state.get("intensity"),     0.5)
        emotion_engine.status["insult_count"] = _safe_int(  self.state.get("insult_count"),  0)

        last_seen = self.state.get("last_interaction")
        last_mood = self.state.get("emotion", "calm")
        grudge    = emotion_engine.status["grudge_score"]
        affection = emotion_engine.status["affection"]

        # First ever launch — no last_interaction timestamp
        if last_seen is None:
            return {
                "status":      "first_launch",
                "description": "First time meeting Ansh. No history. Start fresh.",
            }

        hours = (time.time() - last_seen) / 3600

        # Base context object
        context: Dict[str, Any] = {
            "status":      "normal",
            "hours_passed": round(hours, 2),
            "description": "Conversation continued.",
        }

        # ── GRUDGE ACTIVE (< 12 hrs, grudge still hot) ───────────────────────
        if grudge > 1.0 and hours < 12:
            # FIX 3: Restore BOTH emotion AND grudge to engine
            emotion_engine.status["emotion"] = last_mood
            # grudge_score already restored above — no double-set needed
            context.update({
                "status":      "grudge_active",
                "description": (
                    "You left during a conflict. Neon is still upset. "
                    "Do not pretend nothing happened. Expect an apology."
                ),
            })
            return context

        # ── INSTANT RESUME (< 5 mins) ────────────────────────────────────────
        if hours < 0.083:
            emotion_engine.status["emotion"] = last_mood
            context.update({
                "status":      "instant_resume",
                "description": "Session resumed within minutes. Maintain exact conversational flow.",
            })
            return context

        # ── QUICK BREAK (5 min – 6 hrs) ─────────────────────────────────────
        if hours < 6:
            context.update({
                "status":      "short_break",
                "description": f"Back after {int(hours * 60)} minutes. Brief acknowledgment, then continue.",
            })
            return context

        # ── FIX 4: SLEEP / WORK CYCLE (6–24 hrs) ────────────────────────────
        if hours < 24:
            greeting = "Welcome back, Boss." if affection >= 50 else "You're back."
            context.update({
                "status":      "new_day",
                "description": (
                    f"It's been ~{int(hours)} hours — likely sleep or work. "
                    f"{greeting} Keep it natural."
                ),
            })
            return context

        # ── EXTENDED ABSENCE (24–72 hrs) ─────────────────────────────────────
        if hours < 72:
            days = int(hours // 24)
            tone = "genuinely missed him" if affection > 70 else "noticed the absence"
            context.update({
                "status":      "extended_absence",
                "description": (
                    f"Ansh was gone for {days} day{'s' if days > 1 else ''}. "
                    f"Neon {tone}. Brief, authentic reaction — then move on."
                ),
            })
            return context

        # ── GHOSTING (> 72 hrs) ──────────────────────────────────────────────
        emotion_engine.status["intensity"] = 0.4
        if affection > 70:
            desc = "Ansh disappeared for days. Neon is hurt but won't say it directly. Expects acknowledgment."
        else:
            desc = "Ansh was gone for days. Neon is indifferent. Cool, professional."
        context.update({
            "status":      "ghosting_return",
            "description": desc,
        })
        return context

    # ── STATS ─────────────────────────────────────────────────────────────────

    def get_stats(self, engine=None) -> Dict[str, Any]:
        """
        FIX 10: Prefers live engine data — self.state values are stale between saves.
        Falls back to persisted state only if no engine provided.
        """
        live = engine.status if engine else self.state
        return {
            "Identity":    self.state["user_name"],
            "Protocol":    self.state["user_role"],
            "Affection":   round(_safe_float(live.get("affection"),    50.0), 1),
            "Grudge":      round(_safe_float(live.get("grudge_score"),  0.0), 1),
            "Intensity":   round(_safe_float(live.get("intensity"),     0.5), 2),
            "Insults":     _safe_int(live.get("insult_count"), 0),
            "Mood":        live.get("emotion", "calm"),
            "TotalTurns":  self.state.get("total_turns", 0),
        }