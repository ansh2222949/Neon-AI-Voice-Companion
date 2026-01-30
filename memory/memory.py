import json
import os
import time
from typing import Dict, Any

MEMORY_FILE = "memory/state.json"

class MemoryManager:
    def __init__(self):
       
        os.makedirs("memory", exist_ok=True)
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        """Loads state safely with auto-repair."""
        default_state = {
            "affection": 50.0,
            "emotion": "calm",
            "last_interaction": time.time(),
            "total_turns": 0,
            "user_name": "User"
        }

        if not os.path.exists(MEMORY_FILE):
            return default_state

        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**default_state, **data}
        except (json.JSONDecodeError, IOError):
            print("⚠️ [MEMORY] Save file corrupted. Resetting memory.")
            return default_state

    def save(self, emotion_state: Dict, user_input: str = ""):
        """
        Saves Emotion + Interaction Stats + Name Extraction.
        Atomic write prevents corruption.
        """
        # 1. Update Internal State
        self.state.update({
            "affection": emotion_state.get("affection", 50.0),
            "emotion": emotion_state.get("emotion", "calm"),
            "last_interaction": time.time(),
            "total_turns": self.state.get("total_turns", 0) + 1
        })

        # 2. Smart Name Extraction (Fixed)
        # Logic: "My name is [Raj Kumar]" -> Captures full name, max 25 chars
        lower_input = user_input.lower()
        if "my name is" in lower_input:
            try:
                # Split at 'my name is', take the last part, strip whitespace
                raw_name = lower_input.split("my name is")[-1].strip()
                
                # Check if name is valid (not empty)
                if raw_name and len(raw_name) < 25:
                    # Clean punctuation (optional)
                    clean_name = raw_name.replace(".", "").replace("!", "")
                    self.state["user_name"] = clean_name.title()
            except Exception:
                pass

        # 3. Atomic Write (Safe Save)
        temp_file = MEMORY_FILE + ".tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
            
            if os.path.exists(MEMORY_FILE):
                os.remove(MEMORY_FILE)
            os.rename(temp_file, MEMORY_FILE)
            
        except Exception as e:
            print(f"❌ [MEMORY] Save Failed: {e}")

    def restore(self, emotion_engine) -> str:
        """
        Injects saved state and calculates time-based context.
        """
        # Restore Emotion
        emotion_engine.status["affection"] = self.state.get("affection", 50.0)
        emotion_engine.status["emotion"] = self.state.get("emotion", "calm")
        emotion_engine.status["intensity"] = 0.5  # Reset intensity on boot

        # Calculate Time Gap
        last_seen = self.state.get("last_interaction", time.time())
        hours_passed = (time.time() - last_seen) / 3600
        
        user_name = self.state.get("user_name", "User")

        # Context Logic (Time Travel)
        if hours_passed > 168: # > 7 Days (Ghosting)
            return f"[SYSTEM CONTEXT: {user_name} returned after a week. Act distant, slightly annoyed, but curious.]"
        
        elif hours_passed > 24: # > 1 Day
            return f"[SYSTEM CONTEXT: {user_name} returned after a long time. Act surprised and missed them.]"
        
        elif hours_passed > 6: # > 6 Hours
            return f"[SYSTEM CONTEXT: {user_name} is back after a break. Be welcoming.]"
        
        elif hours_passed < 0.1: # < 6 Minutes (Instant Restart)
            return f"[SYSTEM CONTEXT: {user_name} restarted the chat instantly. Resume conversation normally.]"
        
        else:
            return f"[SYSTEM CONTEXT: Continued conversation with {user_name}.]"
            
    def get_stats(self):
        return {
            "User": self.state.get("user_name"),
            "Affection": round(self.state.get("affection"), 1),
            "Turns": self.state["total_turns"]
        }