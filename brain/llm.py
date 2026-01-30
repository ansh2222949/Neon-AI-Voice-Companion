import requests
from typing import List, Dict, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Custom Modules
from brain.prompt import get_system_prompt
from core.emotion import EmotionEngine
from style.postprocess import postprocess_reply
from memory.memory import MemoryManager

# --- CONFIG ---
OLLAMA_URL = "http://localhost:11434/api/chat"
CHECK_URL  = "http://localhost:11434/api/tags"
MODEL_NAME = "neon"   # ✅ FIXED (was neon-waifu)

MAX_HISTORY_PAIRS = 10
TIMEOUT = 45

class NeonBrain:
    def __init__(self):
        # 1. Core Components
        self.engine = EmotionEngine()
        self.memory = MemoryManager()
        self.history: List[Dict[str, str]] = []

        # 2. Network Session
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods={"POST", "GET"}
        )
        self.session.mount("http://", HTTPAdapter(max_retries=retries))

        # 3. Boot Checks
        self._check_connection()

        # 4. Restore Long-Term Memory
        self.boot_context = self.memory.restore(self.engine)

        # 5. Teacher Mode Triggers
        self.tech_keywords = {
            "python", "def ", "class ", "import ", "code",
            "debug", "error", "api", "json"
        }

    def _check_connection(self):
        try:
            r = self.session.get(CHECK_URL, timeout=1)
            if r.status_code == 200:
                print("✅ [NEON] Neural Link Established.")
            else:
                print("⚠️ [NEON] Ollama responding with error.")
        except requests.RequestException:
            print("⚠️ [NEON] Ollama unreachable at localhost:11434")

    def chat(self, user_input: str) -> Optional[str]:
        if not user_input or not user_input.strip():
            return None

        user_input = user_input.strip()
        lower_input = user_input.lower()

        # --- STEP 1: EMOTION UPDATE (Skip for Technical Queries) ---
        is_technical = any(k in lower_input for k in self.tech_keywords)
        if not is_technical:
            self.engine.process_input(user_input)

        status = self.engine.status

        # --- STEP 2: SYSTEM PROMPT ---
        system_prompt = get_system_prompt(
            emotion=status["emotion"],
            intensity=status["intensity"],
            affection=status["affection"]
        )

        # Inject boot context ONCE
        if self.boot_context:
            system_prompt = f"{self.boot_context}\n{system_prompt}"
            self.boot_context = None

        # --- STEP 3: CONTEXT ---
        history_slice = self.history[-(MAX_HISTORY_PAIRS * 2):]

        context_messages = [
            {"role": "system", "content": system_prompt},
            *history_slice,
            {"role": "user", "content": user_input}
        ]

        # --- STEP 4: MODEL OPTIONS ---
        options = {
            "num_ctx": 2048,
            "mirostat": 2,
            "mirostat_tau": 5.0,
            "mirostat_eta": 0.1,
            "repeat_penalty": 1.15,
            "top_k": 40,
            "top_p": 0.9
        }

        # --- STEP 5: OLLAMA CALL ---
        try:
            response = self.session.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "messages": context_messages,
                    "stream": False,
                    "options": options
                },
                timeout=TIMEOUT
            )
            response.raise_for_status()

            raw_reply = response.json().get("message", {}).get("content", "").strip()

        except requests.exceptions.Timeout:
            return "Sorry, I spaced out for a second. Can you repeat that?"

        except requests.RequestException:
            return "Something feels off on my end. Check the system."

        if not raw_reply:
            return None

        # --- STEP 6: HISTORY + SAVE ---
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": raw_reply})
        self.history = self.history[-(MAX_HISTORY_PAIRS * 2):]

        self.memory.save(self.engine.get_state(), user_input)

        # --- STEP 7: POSTPROCESS ---
        return postprocess_reply(raw_reply)

    def reset_history(self):
        """Clears short-term chat history only (RAM)."""
        self.history = []
