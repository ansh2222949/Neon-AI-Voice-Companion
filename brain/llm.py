import os
import re
import sys
import json
import time
import threading
import inspect
import requests
from collections import deque
from typing import List, Dict, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── WINDOWS CONSOLE UTF-8 SAFETY ─────────────────────────────────────────────
def _ensure_utf8_console() -> None:
    """
    Windows can default to cp1252 which crashes on emoji / unicode prints.
    Reconfigure stdout/stderr to UTF-8 when possible.
    """
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # Never fail import/init due to console encoding tweaks
        pass

_ensure_utf8_console()

# ── 1. BULLETPROOF DYNAMIC IMPORTS ───────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from brain.system_controller import SystemController
except ImportError:
    from system_controller import SystemController

try:
    from prompt import get_system_prompt
except ImportError:
    from brain.prompt import get_system_prompt

try:
    from core.emotion import EmotionEngine
except ImportError:
    print("[ERROR] CRITICAL: EmotionEngine not found. Check your folder structure.")
    sys.exit(1)

try:
    from memory.memory import MemoryManager
except ImportError:
    print("[ERROR] CRITICAL: MemoryManager not found. Check your folder structure.")
    sys.exit(1)

try:
    from style.postprocess import postprocess_reply
except ImportError:
    def postprocess_reply(text): return text.strip().replace('"', '')

try:
    from brain.personality import add_lived_in_personality
except ImportError:
    def add_lived_in_personality(reply: str, status: Dict, **kwargs) -> str:
        return reply

try:
    from brain.command_flavor import flavor_command_response, flavor_multi_results
except ImportError:
    def flavor_command_response(action_name, raw_message, user_input="", emotion_status=None):
        return raw_message
    def flavor_multi_results(results, user_input="", emotion_status=None):
        return "\n".join(results) if results else ""

# ── CONFIGURATION ────────────────────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
CHECK_URL    = "http://localhost:11434/api/tags"
# Primary model (higher quality) + small model (lower latency/cost)
LARGE_MODEL_NAME = os.getenv("NEON_MODEL_LARGE", "llama3.2:3b")
SMALL_MODEL_NAME = os.getenv("NEON_MODEL_SMALL", "llama3.2:1b")
MAX_HISTORY  = 20
TIMEOUT      = 45
SLOW_WARN    = 8

# ── INTENT DETECTION ─────────────────────────────────────────────────────────
_COMMAND_RE = re.compile(
    r"\b(open|launch|start|run|execute|delete|remove|create|make|send|close|quit|kill|search|find|lookup|play|status|check|system|cpu|ram|memory|disk|gpu|battery|uptime|personality|mode|volume|mute|unmute|loud|quiet|brightness|bright|dim|screenshot|lock|shutdown|shut down|restart|reboot|sleep|hibernate|wifi|bluetooth|connect|turn off|turn on)\b",
    re.IGNORECASE,
)

# BUG FIX: Extended question patterns — the old regex only matched start-of-sentence
# which missed "can you tell me", "do you think", "is there a way", etc.
_QUESTION_RE = re.compile(
    r"^\s*(what|how|why|who|when|where|explain|tell me|can you explain|do you know|can you tell|do you think|is there|are there|could you explain|would you|should i|is it|what's|how's|why's|who's|does|did|have you|has)",
    re.IGNORECASE,
)

# Words that on their own don't necessarily mean "run a tool"
# e.g. "how does memory work" should NOT trigger system_status
_WEAK_COMMAND_WORDS = frozenset({
    "find", "check", "status", "system", "memory", "disk", "run",
    "start", "play", "search", "connect",
})

# Strong action verbs that almost always mean "do this right now"
_STRONG_COMMAND_WORDS = frozenset({
    "open", "launch", "execute", "delete", "remove", "create", "make",
    "send", "close", "quit", "kill", "mute", "unmute", "shutdown", "shut",
    "restart", "reboot", "hibernate", "lock", "screenshot", "dim", "turn",
})

def _is_command(text: str) -> bool:
    stripped = text.strip()
    # If it looks like a question, only treat it as a command if it contains
    # a STRONG action verb (e.g. "can you open chrome").
    if _QUESTION_RE.match(stripped):
        lower = stripped.lower()
        tokens = set(re.findall(r"\b\w+\b", lower))
        if tokens & _STRONG_COMMAND_WORDS:
            return True
        return False
    return bool(_COMMAND_RE.search(stripped))

# ── TECHNICAL TOPIC DETECTION ────────────────────────────────────────────────
# BUG FIX: Words like 'memory', 'fix', 'error', 'bug' were causing false
# positives—"fix my volume" or "I have a memory" would route to the large
# model and change temperature, hurting conversational quality.
_TECH_KEYWORDS_STRONG = frozenset({
    "python", "javascript", "typescript", "rust", "golang", "java", "c++", "c#",
    "function", "variable", "loop",
    "code", "debug", "api", "script", "terminal",
    "json", "xml", "yaml", "compile", "runtime", "stack",
    "git", "docker", "linux", "bash", "regex", "database", "sql",
    "library", "module", "package", "framework", "algorithm",
})
# These only count as technical when combined with another tech keyword
_TECH_KEYWORDS_WEAK = frozenset({
    "error", "bug", "fix", "memory", "server", "def", "class", "import",
})

_TECH_STARTS = ("explain", "what is", "what are", "how does", "how do", "how to")

def _is_technical(text: str) -> bool:
    lower = text.lower()
    tokens = set(re.findall(r"\b\w+\b", lower))
    has_strong = bool(tokens & _TECH_KEYWORDS_STRONG)
    has_weak = bool(tokens & _TECH_KEYWORDS_WEAK)

    if has_strong:
        return True
    # Weak keywords only count if the sentence starts with a technical preamble
    if has_weak and lower.startswith(_TECH_STARTS):
        return True
    return False

def _extract_music_query(raw_lower: str) -> str:
    """
    Best-effort extraction of the song/artist query from a natural sentence.
    Examples:
      'play moon funk on youtube mobile' -> 'moon funk'
      'can you play a beautiful moon punk in my mobile' -> 'beautiful moon punk'
    """
    if not raw_lower:
        return ""
    t = raw_lower.strip()
    # Normalize some common filler
    for w in [
        "can you", "could you", "please", "for me", "right now",
        "in my mobile", "in mobile", "on mobile", "mobile",
        "on desktop", "desktop",
        "on youtube", "youtube", "yt", "youtube music", "youtubemusic",
        "on spotify", "spotify",
    ]:
        t = t.replace(w, " ")
    # Prefer text after the word 'play'
    if "play" in t:
        t = t.split("play", 1)[1]
    # Remove leftover connectors
    for w in [" in ", " on ", " at ", " to ", " a ", " an ", " the "]:
        t = t.replace(w, " ")
    t = " ".join(t.split()).strip(" .?!,")
    return t

def _detect_target(raw_lower: str) -> str:
    if not raw_lower:
        return "auto"
    if "mobile" in raw_lower:
        return "mobile"
    if (
        "desktop" in raw_lower
        or "destop" in raw_lower
        or "pc" in raw_lower
        or "computer" in raw_lower
        or "laptop" in raw_lower
    ):
        return "desktop"
    return "auto"

def _detect_platform(raw_lower: str) -> Optional[str]:
    if not raw_lower:
        return None
    if "youtube music" in raw_lower or "youtubemusic" in raw_lower:
        return "youtube"
    if "youtube" in raw_lower or "yt" in raw_lower:
        return "youtube"
    if "spotify" in raw_lower:
        return "spotify"
    return None

def _infer_open_app_name(raw_lower: str) -> str:
    if not raw_lower:
        return ""
    t = raw_lower.lower()
    # Prefer explicit tokens first
    if "camera" in t or "cam" in t:
        return "camera"
    if "gallery" in t or "photos" in t or "photo" in t or "images" in t:
        return "gallery"
    if "whatsapp" in t or "whatapp" in t or "wa " in f"{t} ":
        return "whatsapp"
    if "instagram" in t or "insta" in t:
        return "instagram"
    if "chatgpt" in t or "chat gpt" in t:
        return "chatgpt"
    if "youtube music" in t or "youtubemusic" in t:
        return "youtube music"
    if "youtube" in t or "yt" in t:
        return "youtube"
    if "spotify" in t:
        return "spotify"
    if "gmail" in t:
        return "gmail"
    if "maps" in t:
        return "maps"
    if "google" in t:
        return "google"
    return ""

def _select_model(technical: bool, is_command: bool) -> str:
    """
    Picks which Ollama model to use.
    - Commands and technical prompts use the larger model (more reliable, tool-aware).
    - Casual conversation uses the small model (faster).
    """
    return LARGE_MODEL_NAME if (technical or is_command) else SMALL_MODEL_NAME

# ── TOOL DEFINITIONS ─────────────────────────────────────────────────────────
TOOLS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": (
                "Opens ANY application or website. "
                "Use this for 'open chrome', 'launch spotify', 'open youtube', 'start terminal'. "
                "If Boss says 'mobile', set target='mobile'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "The app or site name (e.g. 'chrome', 'youtube', 'notepad')"
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to open: 'auto' (default), 'desktop', or 'mobile'. If user says 'mobile', use 'mobile'."
                    },
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_google",
            "description": "Searches Google for a specific query. Use when explicitly asked to search the web, or as a fallback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for on Google"
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to open: 'auto' (default), 'desktop', or 'mobile'. If user says 'mobile', use 'mobile'."
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_youtube",
            "description": "Searches YouTube for a specific video or topic. Use when asked to search YouTube, or as a fallback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for on YouTube"
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to open: 'auto' (default), 'desktop', or 'mobile'. If user says 'mobile', use 'mobile'."
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": (
                "Creates a new file. ONLY call when the user gives a direct command "
                "like 'create file notes.txt' or 'make a new file called test.py'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file including extension (e.g. 'notes.txt')"
                    }
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": (
                "Deletes a file. ONLY call when the user gives a direct command "
                "like 'delete file.txt' or 'remove old_script.py'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Exact filename to delete"
                    }
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_message",
            "description": (
                "Sends a WhatsApp message. ONLY call when the user explicitly "
                "commands 'send [contact] a message saying...'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {
                        "type": "string",
                        "description": "Name of the WhatsApp contact"
                    },
                    "message": {
                        "type": "string",
                        "description": "The message content to send"
                    },
                },
                "required": ["contact_name", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": (
                "Plays music. If possible, opens and autoplays the top YouTube result; "
                "otherwise opens Spotify/YouTube Music search. "
                "Use when Boss says 'play <song/artist>' or 'play music'. "
                "If Boss says 'mobile', set target='mobile'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Song/artist/playlist to play (e.g. 'The Weeknd Blinding Lights')"
                    },
                    "platform": {
                        "type": "string",
                        "description": "Preferred platform: 'spotify' or 'youtube' (defaults to spotify)"
                    },
                    "autoplay": {
                        "type": "boolean",
                        "description": "If true, try to open and autoplay the top result (YouTube only). Defaults to true."
                    },
                    "target": {
                        "type": "string",
                        "description": "Where to play: 'auto' (default), 'desktop', or 'mobile'. If user says 'mobile', use 'mobile'."
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_status",
            "description": (
                "Checks system health: services (Ollama, TTS, backend) and "
                "hardware (CPU, RAM, disk, GPU, battery, uptime, top processes). "
                "Use when Boss asks about system status, RAM usage, CPU load, "
                "disk space, GPU temp, battery level, or 'how's my system'."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_personality",
            "description": (
                "Changes Neon's personality mode. Use when Boss says things like "
                "'be more roasty', 'chill mode', 'be curious', 'stop roasting', 'normal mode'. "
                "Modes: 'balanced' (default), 'roaster' (more teasing), 'curious' (asks follow-ups)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "Personality mode: 'balanced', 'roaster', or 'curious'. Also accepts aliases like 'roasty', 'chill', 'spicy'."
                    }
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_control",
            "description": (
                "Controls system volume. Use when Boss says 'mute', 'unmute', "
                "'volume up', 'volume down', 'set volume to 50', 'louder', 'quieter'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Volume action: 'mute', 'unmute', 'up', 'down', or 'set'"
                    },
                    "level": {
                        "type": "integer",
                        "description": "Volume level 0-100 (only used with 'set' action)"
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "brightness_control",
            "description": (
                "Controls screen brightness. Use when Boss says 'brightness up', "
                "'brightness down', 'dim the screen', 'brighter', 'set brightness to 80'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Brightness action: 'up', 'down', 'set', or 'get'"
                    },
                    "level": {
                        "type": "integer",
                        "description": "Brightness level 0-100 (only used with 'set' action)"
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": (
                "Takes a screenshot and saves to workspace. Use when Boss says "
                "'take a screenshot', 'capture screen', 'screenshot'."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lock_screen",
            "description": (
                "Locks the computer screen. Use when Boss says 'lock my PC', "
                "'lock screen', 'lock the computer'."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "power_control",
            "description": (
                "Shutdown, restart, or sleep the computer. Use when Boss explicitly says "
                "'shutdown', 'restart', 'reboot', 'sleep', or 'hibernate'. "
                "ONLY use for direct commands, not casual mentions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Power action: 'shutdown', 'restart', 'sleep', or 'cancel'"
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_connectivity",
            "description": (
                "Enable, disable, or toggle WiFi or Bluetooth. Use when Boss says "
                "'turn off wifi', 'enable bluetooth', 'toggle wifi', 'disconnect wifi'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "What to control: 'wifi' or 'bluetooth'"
                    },
                    "state": {
                        "type": "string",
                        "description": "Desired state: 'on', 'off', or 'toggle'"
                    },
                },
                "required": ["target"],
            },
        },
    },
]

# 🛡️ THE NEW FALLBACK RULE
_TOOL_RULE = (
    "\n\nTOOL USE RULE: Only invoke a tool when Boss gives a DIRECT, EXPLICIT command. "
    "General questions → answer in text. "
    "If Boss says 'open WhatsApp/Instagram/ChatGPT/Camera/Gallery', use the 'open_app' tool (NOT send_whatsapp_message). "
    "CRITICAL FALLBACK RULE: If you use the 'open_app' tool and it returns an error saying the app is not found, "
    "DO NOT panic. Politely tell Boss 'I can't find this app, it doesn't seem to exist on your system.' "
    "Then, explicitly ask: 'Should I search for it on Google or YouTube instead?'"
    "\nNEVER FAKE TOOL RESULTS: If a tool returns 'blocked' or 'confirmation required', "
    "you MUST tell Boss it needs confirmation. NEVER pretend the action completed. "
    "NEVER say 'shutting down' or 'done' if the tool did not return status='success'."
)

# ─────────────────────────────────────────────────────────────────────────────
# 🧠  NeonBrain
# ─────────────────────────────────────────────────────────────────────────────
class NeonBrain:
    def __init__(self):
        self.engine  = EmotionEngine()
        self.memory  = MemoryManager()
        # BUG FIX: Was defaulting to require_confirmation=True, which blocked
        # high-risk commands (shutdown, delete, whatsapp) with no way to
        # actually confirm — the LLM would then hallucinate success.
        self.system  = SystemController(require_confirmation=False)
        self.history: List[Dict[str, str]] = []
        self.last_action: Optional[Dict] = None

        self._last_input: str  = ""
        self._last_input_ts: float = 0.0
        self._current_user_lower: str = ""
        # Feature 5: Smart command cooldown — deque of (tool_name, timestamp)
        self._command_history: deque = deque(maxlen=20)

        self.session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
        self.session.mount("http://", HTTPAdapter(max_retries=retries))

        self._check_connection()
        boot_ctx = self.memory.restore(self.engine)
        self._boot_memory: Optional[str] = boot_ctx.get("description") if boot_ctx else None
        if self._boot_memory:
            print(f"[NEON MEMORY] {self._boot_memory}")

    def _check_connection(self) -> None:
        try:
            r = self.session.get(CHECK_URL, timeout=1)
            if r.status_code == 200:
                print("[NEON] Neural Link Established.")
            else:
                print(f"[WARN] [NEON] Ollama returned {r.status_code}")
        except requests.RequestException:
            print("[WARN] [NEON] Ollama unreachable at localhost:11434")

    def _trim_history(self) -> None:
        # FIX: Safer slice logic avoids mid-conversation breakage
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]

    def _get_history_slice(self, technical: bool) -> List[Dict]:
        limit = 6 if technical else 10
        return self.history[-limit:]

    def _build_options(self, technical: bool) -> Dict:
        return {
            "num_ctx":        3072,
            "num_predict":    256,
            "temperature":    0.2 if technical else 0.6,
            "top_k":          40,
            "top_p":          0.9,
            "repeat_penalty": 1.18,
        }

    def _messages_to_prompt(self, messages: List[Dict]) -> str:
        """
        Converts chat messages to a single prompt for Ollama /api/generate fallback.
        Keeps the system message at the top and a clear role-separated transcript.
        """
        parts: List[str] = []
        for m in messages or []:
            role = (m.get("role") or "").strip().lower()
            content = (m.get("content") or "").strip()
            if not content:
                continue
            if role == "system":
                parts.append(content)
            elif role in {"user", "assistant", "tool"}:
                name = (m.get("name") or "").strip()
                if role == "tool" and name:
                    parts.append(f"[TOOL:{name}] {content}")
                else:
                    parts.append(f"{role.upper()}: {content}")
            else:
                parts.append(content)
        parts.append("ASSISTANT:")
        return "\n\n".join(parts).strip()

    def _get_installed_models(self) -> List[str]:
        try:
            r = self.session.get(CHECK_URL, timeout=2)
            if r.status_code != 200:
                return []
            data = r.json() or {}
            models = data.get("models") or []
            names = []
            for m in models:
                name = (m.get("name") or "").strip()
                if name:
                    names.append(name)
            return names
        except Exception:
            return []

    def _pick_fallback_model(self) -> str:
        """
        If the requested model isn't installed, fall back safely:
        1) LARGE_MODEL_NAME if installed
        2) first installed model
        3) LARGE_MODEL_NAME as last resort
        """
        installed = self._get_installed_models()
        if LARGE_MODEL_NAME in installed:
            return LARGE_MODEL_NAME
        if installed:
            return installed[0]
        return LARGE_MODEL_NAME

    def _post(self, payload: Dict, label: str = "") -> Optional[Dict]:
        try:
            resp = self.session.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)

            # 404 can mean "model not found" (common when SMALL model isn't pulled).
            if resp.status_code == 404:
                body = ""
                try:
                    body = resp.text or ""
                except Exception:
                    body = ""
                if "model" in body.lower() and ("not found" in body.lower() or "does not exist" in body.lower()):
                    fallback_model = self._pick_fallback_model()
                    retry_payload = dict(payload)
                    retry_payload["model"] = fallback_model
                    retry = self.session.post(OLLAMA_URL, json=retry_payload, timeout=TIMEOUT)
                    retry.raise_for_status()
                    return retry.json()

                # Some servers might not expose /api/chat; try /api/generate fallback.
                prompt = self._messages_to_prompt(payload.get("messages") or [])
                gen_payload = {
                    "model": payload.get("model"),
                    "prompt": prompt,
                    "stream": False,
                    "options": payload.get("options") or {},
                }
                gen = self.session.post(OLLAMA_GENERATE_URL, json=gen_payload, timeout=TIMEOUT)
                gen.raise_for_status()
                gen_json = gen.json()
                return {"message": {"role": "assistant", "content": gen_json.get("response", "")}}

            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            print(f"[WARN] [NEON] Timeout during {label or 'request'}")
            return None
        except Exception as e:
            print(f"[ERROR] [NEON NET ERROR] {label}: {e}")
            return None

    def _execute_tool_calls(self, tool_calls: List[Dict], context: List[Dict], target: str = "auto") -> str:
        def _tool_result_to_text(result) -> str:
            """
            Tool methods return dicts for structured status.
            For user-facing speech, prefer the 'message' field.
            """
            if isinstance(result, dict):
                msg = result.get("message")
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()
                # Fall back to a compact representation
                status = result.get("status")
                if isinstance(status, str) and status.strip():
                    return status.strip()
                return ""
            return str(result).strip()

        # Pre-pass: if user asked for mobile and we have a YouTube search, skip redundant open_app(youtube)
        if tool_calls:
            try:
                ul = self._current_user_lower or ""
                wants_mobile = "mobile" in ul
                if wants_mobile:
                    has_yt_search = any(t.get("function", {}).get("name") == "search_youtube" for t in tool_calls)
                    if has_yt_search:
                        tool_calls = [t for t in tool_calls if not (t.get("function", {}).get("name") == "open_app" and ((t.get("function", {}).get("arguments") or {}) if isinstance(t.get("function", {}).get("arguments"), dict) else {}).get("app_name") in {"youtube", "yt"})]
            except Exception:
                pass

        results = []
        for tool in tool_calls:
            func_name = tool["function"]["name"]
            args      = tool["function"]["arguments"]
            func = getattr(self.system, func_name, None)

            # Ollama tool arguments may arrive as a JSON string.
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if not isinstance(args, dict):
                args = {}

            # Hard reroute: "open whatsapp" should never call send_whatsapp_message
            if func_name == "send_whatsapp_message":
                ul = self._current_user_lower or ""
                if ("open" in ul) and ("whatsapp" in ul or "whatapp" in ul):
                    func_name = "open_app"
                    args = {"app_name": "whatsapp", "target": _detect_target(ul)}
                    func = getattr(self.system, func_name, None)

            # Preference defaults (do not override explicit args)
            try:
                prefs = (self.memory.state.get("prefs") or {}) if getattr(self, "memory", None) else {}
            except Exception:
                prefs = {}

            # Use server-provided target; fall back to text detection
            resolved_target = target if target in {"mobile", "desktop"} else _detect_target(self._current_user_lower or "")

            if func_name == "play_music":
                # If model forgets parameters, infer from user sentence.
                if "query" not in args or not str(args.get("query") or "").strip():
                    inferred = _extract_music_query(self._current_user_lower or "")
                    if inferred:
                        args["query"] = inferred
                if "platform" not in args or not str(args.get("platform") or "").strip():
                    args["platform"] = _detect_platform(self._current_user_lower or "") or prefs.get("music_platform", "spotify")
                if "autoplay" not in args:
                    args["autoplay"] = True
                if "target" not in args:
                    args["target"] = resolved_target
                # If running headless (mobile/backend), prefer mobile unless user explicitly said desktop
                if os.getenv("NEON_HEADLESS", "0").strip() == "1" and resolved_target != "desktop":
                    if args.get("target") in {"auto", "desktop", None}:
                        args["target"] = "mobile"
            if func_name == "open_app":
                if "app_name" not in args or not str(args.get("app_name") or "").strip():
                    inferred_app = _infer_open_app_name(self._current_user_lower or "")
                    if inferred_app:
                        args["app_name"] = inferred_app
                if "target" not in args:
                    args["target"] = resolved_target
                if os.getenv("NEON_HEADLESS", "0").strip() == "1" and resolved_target != "desktop":
                    if args.get("target") in {"auto", "desktop", None}:
                        args["target"] = "mobile"
            if func_name in {"search_google", "search_youtube"}:
                if "target" not in args:
                    args["target"] = resolved_target
                if os.getenv("NEON_HEADLESS", "0").strip() == "1" and resolved_target != "desktop":
                    if args.get("target") in {"auto", "desktop", None}:
                        args["target"] = "mobile"

            print(f"   -> Executing: {func_name}({args})")

            # Feature 5: Smart cooldown check
            # BUG FIX: Old code silently skipped the command with "continue"
            # which meant the tool NEVER ran on a retry, making it look
            # like the command failed.  Now we just warn but still execute.
            now = time.time()
            recent_same = [
                ts for (fn, ts) in self._command_history
                if fn == func_name and (now - ts) < 3.0
            ]
            if recent_same:
                print(f"[NEON] Cooldown: {func_name} was called recently, running anyway.")

            if func:
                try:
                    # Drop unexpected args so tool calls can't crash TTS/voice flows
                    try:
                        sig = inspect.signature(func)
                        params = sig.parameters
                        accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
                        if (not accepts_kwargs) and args:
                            allowed = {k for k, p in params.items() if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)}
                            args = {k: v for k, v in args.items() if k in allowed}
                    except Exception:
                        pass
                    result = func(**args)
                except Exception as e:
                    result = f"Error in {func_name}: {e}"

                # BUG FIX: If tool returned 'blocked', make it very clear
                # to the LLM so it doesn't hallucinate success.
                if isinstance(result, dict) and result.get("status") == "blocked":
                    blocked_msg = result.get("message", "Action was blocked.")
                    result = {"status": "blocked", "message": f"BLOCKED: {blocked_msg} Ask Boss for confirmation before retrying."}
            else:
                result = f"Error: Tool '{func_name}' not found in SystemController."

            # Feature 5: Record in cooldown history
            self._command_history.append((func_name, now))

            # Feature 6: Record command stats for usage learning
            try:
                detail = ""
                if func_name == "open_app":
                    detail = args.get("app_name", "")
                elif func_name in {"search_google", "search_youtube", "play_music"}:
                    detail = args.get("query", "")
                elif func_name == "set_personality":
                    detail = args.get("mode", "")
                self.memory.record_command(func_name, detail)
            except Exception:
                pass

            # Feature 1: Persist personality mode change
            if func_name == "set_personality" and isinstance(result, dict):
                new_mode = result.get("mode")
                if new_mode and result.get("status") == "success":
                    try:
                        prefs = self.memory.state.get("prefs", {})
                        prefs["banter_mode"] = new_mode
                        self.memory.state["prefs"] = prefs
                    except Exception:
                        pass

            result_text = _tool_result_to_text(result) or str(result)
            if isinstance(result, dict) and isinstance(result.get("action"), dict):
                self.last_action = result.get("action")
            context.append({
                "role":    "tool",
                "content": result_text,
                "name":    func_name,
            })
            results.append(result_text)

        # Feature 6: Auto-update prefs from usage patterns
        try:
            self.memory.auto_update_prefs()
        except Exception:
            pass

        return "\n".join(results)

    def chat(self, user_input: str, target: str = "auto") -> Optional[str]:
        if not user_input or not user_input.strip():
            return None

        user_input = user_input.strip()
        lower      = user_input.lower()
        self._current_user_lower = lower
        self._current_target = target

        now = time.time()
        seconds_since_last = (now - self._last_input_ts) if self._last_input_ts else None
        # BUG FIX: Old duplicate check blocked ANY repeat of the same text
        # even if sent intentionally (e.g. "open chrome" twice in a row).
        # Now only block exact duplicates within a tight 3-second window.
        if (
            user_input.strip().lower() == self._last_input.strip().lower()
            and seconds_since_last is not None
            and seconds_since_last < 3.0
        ):
            print("[NEON] Duplicate input ignored (within 3s).")
            import random
            return random.choice([
                "I'm listening, Boss.",
                "I heard you the first time.",
                "Still here.",
            ])
        self._last_input    = user_input
        self._last_input_ts = now

        identity_triggers = ("introduce yourself", "who are you", "who are u", "what are you")
        if any(t in lower for t in identity_triggers):
            user_input = "Introduce yourself briefly."

        technical  = _is_technical(lower)
        is_command = _is_command(lower)
        chosen_model = _select_model(technical=technical, is_command=is_command)
        # Reset per-turn action
        self.last_action = None

        if not technical:
            self.engine.process_input(user_input)

        status = self.engine.status.copy()

        # FIX: Fuzzy apology check and grudge deflation
        apology_words = ("sorry", "forgive", "apology", "my bad", "apologize", "mistake")
        is_apology = any(w in lower for w in apology_words)
        
        if status["emotion"] == "mad" and status.get("grudge_score", 0) > 6.0:
            if not is_apology:
                return "..."
            else:
                self.engine.status["grudge_score"] = max(0, status.get("grudge_score", 0) - 2.0)
                status = self.engine.status.copy()

        system_prompt = get_system_prompt(
            emotion   = status["emotion"],
            intensity = status["intensity"],
            affection = status["affection"],
        ) + _TOOL_RULE

        # Preference-driven personality mode (persisted)
        try:
            prefs = (self.memory.state.get("prefs") or {}) if getattr(self, "memory", None) else {}
        except Exception:
            prefs = {}
        banter_mode = (prefs.get("banter_mode") or "balanced").strip().lower()
        if banter_mode == "roaster":
            system_prompt += (
                "\n\nPERSONALITY MODE: ROASTER BESTIE.\n"
                "- You tease Boss lightly (never cruel, never humiliating).\n"
                "- Max ONE roast line per reply.\n"
                "- After teasing, you still help.\n"
                "- You can flirt a little, but never clingy and never cringe.\n"
            )
        elif banter_mode == "curious":
            system_prompt += (
                "\n\nPERSONALITY MODE: CURIOUS BESTIE.\n"
                "- Ask ONE sharp follow-up question when it would clarify what Boss wants.\n"
                "- Keep it natural and confident.\n"
                "- You can show that you like Boss, but stay cool.\n"
            )
        else:
            system_prompt += (
                "\n\nPERSONALITY MODE: BALANCED.\n"
                "- Light banter is okay when affection allows.\n"
                "- Ask ONE follow-up question only when it meaningfully helps.\n"
            )

        if self._boot_memory:
            system_prompt += f"\n\n[MEMORY RESTORE: {self._boot_memory}]"
            self._boot_memory = None

        # Feature 3: Proactive time-aware context injection
        try:
            local = time.localtime()
            hour = local.tm_hour
            if 5 <= hour < 12:
                greeting_hint = "morning"
            elif 12 <= hour < 17:
                greeting_hint = "afternoon"
            elif 17 <= hour < 21:
                greeting_hint = "evening"
            else:
                greeting_hint = "late_night"

            session_info = ""
            if seconds_since_last and seconds_since_last > 3600:
                hrs = int(seconds_since_last // 3600)
                session_info = f" Boss was away for ~{hrs} hour{'s' if hrs > 1 else ''}."
            elif seconds_since_last and seconds_since_last < 60:
                session_info = " Boss just spoke."

            # If it's late night and Boss has been active, note it subtly
            late_night_note = ""
            if greeting_hint == "late_night" and self.memory.state.get("total_turns", 0) > 5:
                late_night_note = " It's late — you might gently check if Boss needs sleep."

            system_prompt += (
                f"\n\n[TIME CONTEXT: {hour:02d}:{local.tm_min:02d} ({greeting_hint})."
                f"{session_info}{late_night_note}]"
            )
        except Exception:
            pass

        # Inject Active Platform Context
        try:
            platform_name = "Mobile App" if target.lower() == "mobile" else "Desktop PC"
            system_prompt += f"\n\n[USER PLATFORM: Boss is currently using the {platform_name}. If asked about your current mode or capabilities, remember you are controlling the {platform_name}.]"
        except Exception:
            pass

        context: List[Dict] = [{"role": "system", "content": system_prompt}]
        context.extend(self._get_history_slice(technical))
        context.append({"role": "user", "content": user_input})

        payload: Dict = {
            "model":    chosen_model,
            "messages": context,
            "stream":   False,
            "options":  self._build_options(technical),
        }

        model_supports_tools = "llama" in chosen_model.lower() or "tool" in chosen_model.lower()
        # BUG FIX: Only attach tools when we're confident it's a command.
        # Previously the model would hallucinate tool_calls for
        # borderline inputs like "check this out" or "play it cool".
        if is_command and model_supports_tools:
            payload["tools"]       = TOOLS
            payload["tool_choice"] = "auto"
        else:
            # Explicitly exclude tools so the model can't hallucinate them
            payload.pop("tools", None)
            payload.pop("tool_choice", None)

        start_t  = time.time()
        response = self._post(payload, label="primary")

        if response is None:
            return "I can't reach my model server right now. Say 'status' and I'll tell you what's down."

        message_data = response.get("message", {})

        # FIX: Hallucination Guard - Strip tool calls if not a command
        if not is_command:
            message_data.pop("tool_calls", None)

        # FIX: Skip Follow-up for latency reduction on simple tools
        if message_data.get("tool_calls"):
            print("🛠️ [NEON] Tool Call Detected!")
            context.append(message_data) 

            tool_result = self._execute_tool_calls(message_data["tool_calls"], context, target=self._current_target)
            
            # 🎀 Flavor the dry tool output with anime girl personality
            # Feature 2: Handle multi-tool chaining
            raw_parts = [p.strip() for p in tool_result.strip().split("\n") if p.strip()]
            tool_calls_list = message_data.get("tool_calls", [])
            
            if len(raw_parts) > 1 and len(tool_calls_list) > 1:
                # Multi-action: flavor each result, then combine
                flavored_parts = []
                for i, part in enumerate(raw_parts):
                    try:
                        act_name = tool_calls_list[i]["function"]["name"]
                    except (KeyError, IndexError):
                        act_name = ""
                    flavored_parts.append(flavor_command_response(
                        action_name=act_name,
                        raw_message=part,
                        user_input=user_input,
                        emotion_status=status,
                    ))
                raw_reply = flavor_multi_results(flavored_parts, user_input, status)
            else:
                # Single action
                action_name = ""
                try:
                    action_name = tool_calls_list[0]["function"]["name"]
                except (KeyError, IndexError):
                    pass
                raw_reply = flavor_command_response(
                    action_name=action_name,
                    raw_message=tool_result.strip(),
                    user_input=user_input,
                    emotion_status=status,
                )
            
        else:
            raw_reply = message_data.get("content", "")

        elapsed = time.time() - start_t
        if elapsed > SLOW_WARN:
            print(f"[WARN] [NEON] Slow response: {elapsed:.2f}s")

        if not raw_reply:
            return None

        # Guard: if LLM emitted raw JSON instead of natural language, don't speak it.
        # BUG FIX: Old guard only caught '{' and '```json'.  The model can also
        # emit '[{', '```\n{', or just a dict-like blob.  Catch more patterns.
        stripped = raw_reply.strip()
        _looks_like_json = (
            stripped.startswith("{") or stripped.startswith("[{")
            or stripped.startswith("```")
        )
        _has_tool_markers = (
            '"name"' in stripped or '"function"' in stripped
            or '"tool_call"' in stripped or '"action"' in stripped
        )
        _has_arg_markers = (
            '"arguments"' in stripped or '"parameters"' in stripped
            or '"type"' in stripped
        )
        if _looks_like_json and _has_tool_markers and _has_arg_markers:
            print(f"[WARN] [NEON] Raw JSON reply intercepted: {stripped[:120]}")
            raw_reply = "Sorry Boss, I didn't quite catch that. Could you repeat?"

        final_reply = postprocess_reply(raw_reply)



        self.history.append({"role": "user",      "content": user_input})
        self.history.append({"role": "assistant",  "content": final_reply})
        self._trim_history()

        threading.Thread(
            target=self.memory.save,
            args=(self.engine.get_state(),),
            daemon=True,
        ).start()

        return final_reply

    def reset_history(self) -> None:
        self.history = []
        print("[MEMORY] Short-term history cleared.")