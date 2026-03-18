import time
import copy
import random
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# Ensure VADER lexicon is present
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    nltk.download("vader_lexicon", quiet=True)


class EmotionEngine:
    """
    Neon Emotion Engine — v2.0

    Changelog vs v1.x:
    - FIX: target_intensity capped at 1.0 before lerp
    - FIX: bored detection now token-based + context-aware (not just "nice" → boring)
    - FIX: insult_count decays slowly (every 5 msgs), not on every non-hate message
    - FIX: simp detector only triggers on romance keywords, not compliments
    - FIX: chaos/skeptical only fires when interaction is genuinely flat, not random positive
    - FIX: apology has a forgiveness ceiling (max 2 per session within 10 mins)
    - FIX: get_state() returns deep copy — safe for serialization
    - NEW: time-based grudge decay (message gap > 5 min softens grudge)
    - NEW: streak/momentum system — consistent behavior compounds
    - NEW: negation context window ("not stupid" ≠ "stupid")
    """

    # ── KEYWORD SETS ─────────────────────────────────────────────────────────

    # Genuine romantic/clingy keywords only — not generic compliments
    _ROMANCE_KW = {
        "love you", "i love", "marry me", "date me", "be mine",
        "shona", "jaan", "babu", "my crush", "i like you",
    }

    # Compliments that boost affection but are NOT simping
    _COMPLIMENT_KW = {
        "smart", "genius", "brilliant", "talented", "amazing", "great",
        "awesome", "good job", "well done", "nice work", "impressive",
        "cute", "beautiful", "pretty",
    }

    _HATE_KW = {
        "hate", "stupid", "idiot", "pagal", "bakwaas", "dumb", "useless",
        "ugly", "bitch", "get lost", "shut up", "fuck you", "fuck off",
        "loser", "pathetic", "worst",
    }

    _SORRY_KW = {
        "sorry", "maaf", "apology", "my bad", "galti", "mb", "forgive",
        "i apologize", "i'm sorry",
    }

    _FUNNY_KW  = {"lol", "lmao", "haha", "rofl", "xd", "hehe", "💀", "dead 💀"}
    _TEASE_KW  = {"dork", "weirdo", "crazy", "psycho", "nautanki", "drama", "nerd"}

    # Words that indicate negation (for context window)
    _NEGATION = {"not", "no", "never", "didn't", "don't", "doesn't", "isn't", "wasn't", "can't"}

    # Short filler-only responses that indicate disengagement
    _FILLER_TOKENS = {"k", "ok", "okay", "acha", "thik", "oh", "han", "yup", "hmm", "hm", "yeah", "sure"}

    def __init__(self, debug_mode: bool = False):
        self.sia   = SentimentIntensityAnalyzer()
        self.debug = debug_mode

        self.status = {
            "emotion":      "calm",
            "intensity":    0.5,
            "affection":    50.0,   # 0 (enemy) → 100 (loyal)
            "grudge_score": 0.0,    # decays over time + messages
            "insult_count": 0,      # decays slowly (every 5 msgs)
        }

        # Streak tracking — consecutive positive/negative interactions
        self._pos_streak:  int   = 0
        self._neg_streak:  int   = 0
        self._msg_count:   int   = 0   # total messages since init
        self._boring_run:  int   = 0   # consecutive boring messages

        # Apology cooldown — prevents sorry spam abuse
        self._apology_count:    int   = 0
        self._apology_window_start: float = 0.0
        _APOLOGY_WINDOW_SECS  = 600   # 10 minutes
        self._APOLOGY_MAX     = 2     # max effective apologies per window

        self._last_ts:    float = time.time()
        self._last_input: str   = ""

    # ── LOGGING ──────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        if self.debug:
            print(f"[EMOTION] {msg}")

    # ── PHRASE DETECTION ─────────────────────────────────────────────────────

    def _match(self, text: str, phrase_set: set) -> bool:
        """
        Token-safe phrase matcher.
        - Multi-word phrases: substring match on full text
        - Single words: exact word boundary match (avoids "shutdown" → "shut")
        """
        t = text.lower()
        tokens = set(t.split())
        for p in phrase_set:
            if " " in p:
                if p in t:
                    return True
            else:
                if p in tokens:
                    return True
        return False

    def _negated(self, text: str, phrase_set: set) -> bool:
        """
        Returns True if ALL matching phrases in phrase_set appear
        to be negated by a preceding negation word.

        'you are not stupid' → hate word found but negated → True
        'you are stupid'     → hate word found, not negated → False
        """
        t     = text.lower().split()
        found = False

        for i, token in enumerate(t):
            for phrase in phrase_set:
                words = phrase.split()
                if t[i:i + len(words)] == words:
                    found = True
                    # Check window of 3 words before for negation
                    window = t[max(0, i - 3):i]
                    if any(neg in window for neg in self._NEGATION):
                        return True  # This occurrence is negated

        return False  # Not negated (or phrase not found at all)

    def _is_boring(self, text: str) -> bool:
        """
        True only when the ENTIRE message is filler tokens.
        'nice code' is NOT boring. 'ok' is boring.
        """
        tokens = set(text.lower().split())
        # Boring if all non-punctuation tokens are filler words
        content_tokens = {t.strip("!?.,'\"") for t in tokens if t.strip("!?.,'\"'")}
        if not content_tokens:
            return True
        return content_tokens.issubset(self._FILLER_TOKENS)

    # ── PSYCHOLOGICAL SCORING ─────────────────────────────────────────────────

    def get_psychological_score(self, text: str, current_affection: float) -> float:
        """
        Returns a compound sentiment score adjusted for:
        - Hate (with negation check)
        - Romance vs compliment distinction
        - Funny / tease modifiers
        - Streak momentum
        """
        base = self.sia.polarity_scores(text)["compound"]

        has_hate       = self._match(text, self._HATE_KW)
        hate_negated   = has_hate and self._negated(text, self._HATE_KW)
        has_romance    = self._match(text, self._ROMANCE_KW)
        has_compliment = self._match(text, self._COMPLIMENT_KW)
        has_funny      = self._match(text, self._FUNNY_KW)
        has_tease      = self._match(text, self._TEASE_KW)

        score = base

        # ── HATE HANDLING ────────────────────────────────────────────────────
        if has_hate and not hate_negated:
            if current_affection > 75:
                # High loyalty = thicker skin
                score = min(score, -0.15)
                self._log("Insult deflected (High Loyalty)")
            else:
                score -= 0.6

        # ── ROMANCE / SIMP DETECTOR ──────────────────────────────────────────
        # Only penalizes genuine romantic moves at low affection
        # Compliments ("you're smart") are handled separately — no penalty
        if has_romance:
            if current_affection < 30:
                score -= 0.4
                self._log("Romantic advance rejected (Cold relationship)")
            else:
                score += 0.3

        # ── COMPLIMENT BOOST (not penalized at low affection) ────────────────
        if has_compliment and not has_hate:
            score += 0.2

        # ── BANTER MODIFIERS ─────────────────────────────────────────────────
        if has_funny:
            score += 0.25
        if has_tease:
            score += 0.1

        # ── STREAK MOMENTUM ──────────────────────────────────────────────────
        # Consistent behavior should compound, not just individual messages
        if self._pos_streak >= 3:
            score += min(0.2, self._pos_streak * 0.05)
            self._log(f"Positive streak ×{self._pos_streak} bonus")
        if self._neg_streak >= 3:
            score -= min(0.25, self._neg_streak * 0.06)
            self._log(f"Negative streak ×{self._neg_streak} penalty")

        return max(-1.0, min(1.0, score))

    # ── MAIN UPDATE LOOP ──────────────────────────────────────────────────────

    def process_input(self, text: str) -> None:
        text = text.strip()
        if not text:
            return

        now = time.time()

        # ── TIME-BASED GRUDGE DECAY ───────────────────────────────────────────
        # FIX: grudge now softens even during silence
        gap_minutes = (now - self._last_ts) / 60.0
        if gap_minutes > 5:
            time_decay = min(self.status["grudge_score"], gap_minutes * 0.3)
            self.status["grudge_score"] = max(0.0, self.status["grudge_score"] - time_decay)
            self._log(f"Time-based grudge decay: -{time_decay:.2f} ({gap_minutes:.1f} min gap)")

        self._last_ts = now

        # ── MESSAGE-BASED DECAY ───────────────────────────────────────────────
        self.status["grudge_score"] = max(0.0, self.status["grudge_score"] - 0.15)
        self.status["intensity"]   *= 0.95  # Emotional inertia toward baseline
        self._msg_count += 1

        # insult_count decays slowly — every 5 non-hate messages, not every message
        # FIX: prevents "3 insults → 3 nice msgs → forgiven" exploit
        if self._msg_count % 5 == 0 and self.status["insult_count"] > 0:
            self.status["insult_count"] = max(0, self.status["insult_count"] - 1)
            self._log("Slow insult decay applied")

        current_aff  = self.status["affection"]
        psycho_score = self.get_psychological_score(text, current_aff)

        # ── UPDATE STREAKS ────────────────────────────────────────────────────
        if psycho_score > 0.2:
            self._pos_streak += 1
            self._neg_streak  = 0
        elif psycho_score < -0.2:
            self._neg_streak += 1
            self._pos_streak  = 0
        else:
            # Neutral — slowly erodes streaks
            self._pos_streak = max(0, self._pos_streak - 1)
            self._neg_streak = max(0, self._neg_streak - 1)

        # ── TARGET INTENSITY ──────────────────────────────────────────────────
        target_intensity = 0.3
        if text.isupper() and len(text) > 6: target_intensity += 0.4
        if "!" in text:                       target_intensity += 0.2
        if abs(psycho_score) > 0.6:           target_intensity += 0.3

        # FIX: cap before smooth update — was allowing > 1.0
        target_intensity = min(1.0, target_intensity)

        # Boredom
        boring = self._is_boring(text) or text == self._last_input
        if boring:
            self._boring_run   += 1
            target_intensity    = 0.1
        else:
            self._boring_run    = 0

        # Smooth lerp toward target
        self.status["intensity"] = min(
            1.0,
            (self.status["intensity"] * 0.6) + (target_intensity * 0.4)
        )

        # ── AFFECTION LOGIC ───────────────────────────────────────────────────
        aff_change   = 0.0
        grudge       = self.status["grudge_score"]
        has_hate     = self._match(text, self._HATE_KW)
        hate_negated = has_hate and self._negated(text, self._HATE_KW)
        is_apology   = self._match(text, self._SORRY_KW)

        if psycho_score > 0.3:  aff_change =  1.2
        if psycho_score < -0.2: aff_change = -2.5

        # Grudge & insult escalation
        if has_hate and not hate_negated and psycho_score < -0.2:
            self.status["insult_count"] = min(3, self.status["insult_count"] + 1)
            self.status["grudge_score"] += 1.5

        # Apology handling with forgiveness ceiling
        # FIX: "sorry spam" can't reset grudge infinitely
        if is_apology and grudge > 0:
            # Reset apology window if >10 mins since last
            window_elapsed = now - self._apology_window_start
            if window_elapsed > 600:
                self._apology_count        = 0
                self._apology_window_start = now

            if self._apology_count < self._APOLOGY_MAX:
                self.status["grudge_score"] = max(0.0, grudge - 3.0)
                aff_change                  = 1.0
                self._apology_count        += 1
                self._log(f"Apology accepted ({self._apology_count}/{self._APOLOGY_MAX})")
            else:
                self._log("Apology ignored — ceiling reached for this window")
                aff_change = 0.0  # Empty sorries mean nothing

        # Stability dampener — change is harder near extremes (hard-earned loyalty)
        dist_from_neutral  = abs(current_aff - 50.0)
        stability_modifier = max(0.2, 1.0 - (dist_from_neutral / 60.0))
        real_change        = aff_change * stability_modifier

        self.status["affection"] = max(0.0, min(100.0, current_aff + real_change))

        # ── MOOD STATE MACHINE ────────────────────────────────────────────────
        new_mood = "calm"

        if self.status["grudge_score"] > 4.0 or self.status["insult_count"] >= 2:
            new_mood = "mad"
        elif self.status["grudge_score"] > 0.5:
            new_mood = "annoyed"
        elif self._boring_run >= 3:
            new_mood = "bored"
        elif self.status["affection"] > 85 and psycho_score > 0.2:
            new_mood = "warm"
        elif self.status["affection"] > 60 and psycho_score > 0.1:
            new_mood = "playful"
        elif psycho_score > 0.3:
            new_mood = "happy"
        elif self.status["intensity"] < 0.2:
            new_mood = "tired"

        # FIX: Chaos skeptical — only fires when interaction is genuinely flat
        # (not during positive or active conversations)
        if (
            random.random() < 0.015
            and self.status["affection"] < 40
            and abs(psycho_score) < 0.15          # truly neutral, not just below 0.2
            and self._pos_streak == 0              # no positive momentum
            and new_mood not in {"mad", "annoyed"} # don't stack negatives
        ):
            new_mood = "skeptical"

        self.status["emotion"] = new_mood
        self._last_input       = text

        self._log(
            f"Mood: {new_mood.upper()} | "
            f"Aff: {self.status['affection']:.1f} ({real_change:+.2f}) | "
            f"Grudge: {self.status['grudge_score']:.1f} | "
            f"Streaks: +{self._pos_streak}/-{self._neg_streak}"
        )

    # ── PUBLIC API ────────────────────────────────────────────────────────────

    def get_state(self) -> dict:
        """Returns a deep copy — safe to serialize or mutate externally."""
        return copy.deepcopy(self.status)