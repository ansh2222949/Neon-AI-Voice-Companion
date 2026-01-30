import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# --- AUTO-SETUP (Safe Check) ---
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    # Quietly download without spamming console
    nltk.download('vader_lexicon', quiet=True)

class EmotionEngine:
    def __init__(self, debug_mode: bool = False):
        self.sia = SentimentIntensityAnalyzer()
        self.debug = debug_mode
        
        # --- STATE MACHINE ---
        self.status = {
            "emotion": "calm",
            "intensity": 0.5,
            "affection": 50.0
        }
        
        self.last_input = "" 

        # --- OPTIMIZED TRIGGERS (Sets for O(1) Speed) ---
        self.keywords = {
            "love":  {"love", "cute", "shona", "jaan", "babu", "mast", "kadak", "sexy", "sweet"},
            "hate":  {"hate", "stupid", "idiot", "pagal", "bakwaas", "bakar", "kutti", "shut up"},
            "sorry": {"sorry", "maaf", "apology", "my bad", "galti"},
            "funny": {"lol", "lmao", "haha", "rofl", "xd", "hehe"},
            "bored": {"hmm", "k", "ok", "acha", "thik", "oh", "accha", "yup"}
        }

    def _log(self, message: str):
        """Internal logger that respects debug flag"""
        if self.debug:
            print(f"[EMOTION] {message}")

    def get_sentiment(self, text: str) -> float:
        """Calculates Hybrid Score with Conflict Resolution"""
        score = self.sia.polarity_scores(text)["compound"]
        words = set(text.lower().split()) # Tokenize once

        # Check intersections (Fastest method)
        has_love = not words.isdisjoint(self.keywords["love"])
        has_hate = not words.isdisjoint(self.keywords["hate"])
        has_funny = not words.isdisjoint(self.keywords["funny"])

        # --- CONFLICT RESOLUTION ---
        # Agar Hate aur Love dono hain, to negative bias thoda kam hoga, par positive nahi hoga.
        if has_hate and has_love:
            score -= 0.2  # Confused/Toxic emotion
        elif has_hate:
            score -= 0.5  # Strong Negative Bias
        elif has_love:
            score += 0.4  # Strong Positive Bias
            
        if has_funny:
            score += 0.2

        return max(-1.0, min(1.0, score))

    def process_input(self, text: str):
        text = text.strip()
        if not text: return

        # 1. AFFECTION DECAY (Entropy/Realism)
        # Relationship requires maintenance. Decay 0.5% per turn.
        self.status["affection"] *= 0.995 

        raw_score = self.get_sentiment(text)
        
        # ================================
        # 2. ADVANCED INTENSITY (Momentum)
        # ================================
        target_intensity = 0.3
        
        # Detection Logic
        if text.isupper(): target_intensity += 0.3
        if "!" in text:    target_intensity += 0.2
        if len(text.split()) > 8: target_intensity += 0.2
        if abs(raw_score) > 0.5:  target_intensity += 0.2

        # Boredom/Repetition Check
        is_repetitive = text.lower() == self.last_input.lower()
        is_boring_word = text.lower() in self.keywords["bored"]
        
        if is_repetitive or is_boring_word:
            target_intensity = 0.1
            self._log(f"Boredom Triggered: '{text}'")

        # Linear Interpolation (Smooth Transition)
        # 70% Old, 30% New
        self.status["intensity"] = (self.status["intensity"] * 0.7) + (target_intensity * 0.3)
        self.status["intensity"] = max(0.1, min(1.0, self.status["intensity"]))

        # ================================
        # 3. AFFECTION DYNAMICS (Trust)
        # ================================
        aff_change = 0.0

        if raw_score > 0.3:  aff_change = 2.0
        if raw_score < -0.3: aff_change = -5.0

        # Forgiveness Mechanic
        # Check intersection safely
        words = set(text.lower().split())
        if not words.isdisjoint(self.keywords["sorry"]):
            if self.status["emotion"] in ["angry", "mad"]:
                aff_change = 8.0  # Big boost (Redemption)
                self._log("Forgiveness Granted (Angry -> Neutral)")
            else:
                aff_change = 2.0

        self.status["affection"] = max(0.0, min(100.0, self.status["affection"] + aff_change))

        # ================================
        # 4. STATE MACHINE (Sticky Moods)
        # ================================
        current_mood = self.status["emotion"]
        
        # Sticky Anger Logic
        if current_mood in ["angry", "mad"] and raw_score < 0.4:
            # Requires strong positive input to break anger
            pass 
        elif current_mood == "bored" and self.status["intensity"] < 0.25:
            # Requires energy spike to break boredom
            pass 
        else:
            # Normal State Transitions
            if raw_score >= 0.6:
                self.status["emotion"] = "excited" if self.status["intensity"] > 0.7 else "happy"
            elif raw_score <= -0.5:
                self.status["emotion"] = "mad" if self.status["intensity"] > 0.7 else "annoyed"
            elif raw_score > 0.2:
                # Flirty requires trust > 60
                self.status["emotion"] = "flirty" if self.status["affection"] > 60 else "playful"
            elif self.status["intensity"] < 0.2:
                self.status["emotion"] = "bored"
            else:
                self.status["emotion"] = "calm"

        self.last_input = text
        self._log(f"State Updated: {self.status['emotion']} | Aff: {self.status['affection']:.1f}")

    def get_state(self):
        return self.status.copy()