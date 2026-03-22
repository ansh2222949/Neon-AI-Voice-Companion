import os
import webbrowser
import time
from pathlib import Path
import sys
from urllib.parse import quote_plus
import subprocess
import shutil
import re

import requests

# 🚀 Import your new Smart App Opener
from brain.smart_open_app import open_app as smart_launcher 

# Selenium & Webdriver Manager imports
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    _SELENIUM_OK = True
except ImportError:
    print("[WARN] Missing dependencies. Run: pip install selenium webdriver-manager")
    webdriver = None
    By = Keys = Options = Service = ChromeDriverManager = WebDriverWait = EC = None
    _SELENIUM_OK = False

class SystemController:
    # 1️⃣ Risk Classification Map
    RISK_LEVELS = {
        "open_app": "low",
        "search_google": "low",
        "search_youtube": "low",
        "play_music": "low",
        "system_status": "low",
        "set_personality": "low",
        "volume_control": "low",
        "brightness_control": "low",
        "take_screenshot": "low",
        "lock_screen": "medium",
        "toggle_connectivity": "medium",
        "create_file": "medium",
        "delete_file": "high",
        "power_control": "high",
        "send_whatsapp_message": "high"
    }

    def __init__(self, require_confirmation=True):
        self.safe_root = os.path.abspath("D:/neon_workspace/")
        os.makedirs(self.safe_root, exist_ok=True)
        
        self.require_confirmation = require_confirmation 
        
        # 2️⃣ WhatsApp Session Optimization (Persistent Driver)
        self.driver = None 
        
        self._log("SYSTEM_START", f"Controller initialized. Safe root: {self.safe_root}")
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        print(f"[SYSTEM] Controller running. Safe root: {self.safe_root} | Guardrails: {'ON' if self.require_confirmation else 'OFF'}")

    # 3️⃣ Exception-Safe Logging
    def _log(self, action: str, msg: str):
        try:
            log_entry = f"{time.ctime()} | [{action.upper()}] | {msg}\n"
            with open("system.log", "a") as f:
                f.write(log_entry)
        except Exception as e:
            # Fail silently on logging errors so the agent doesn't crash
            print(f"[WARN] [LOGGING ERROR] Could not write to log: {str(e)}")

    # 1️⃣ Dynamic Permission Checker
    def _check_permission(self, action_name: str) -> bool:
        if not self.require_confirmation:
            return True
        
        # Block only high-risk actions if confirmation is required
        if self.RISK_LEVELS.get(action_name) == "high":
            return False
            
        return True

    def _is_safe_path(self, filename: str) -> str:
        clean_name = os.path.basename(filename) 
        return os.path.join(self.safe_root, clean_name)

    def _sanitize_filename(self, filename: str) -> str:
        raw = os.path.basename(str(filename or "").strip().strip("'\""))
        tokens = re.findall(r"[A-Za-z0-9._-]+", raw)

        candidate = ""
        for token in tokens:
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\.[A-Za-z0-9]{1,8}", token):
                candidate = token
                break

        if not candidate:
            words = [
                word.lower()
                for word in re.findall(r"[A-Za-z0-9]+", raw)
                if word.lower() not in {
                    "create", "make", "new", "file", "called", "named", "this",
                    "a", "an", "the", "for", "please", "me", "my",
                }
            ]
            stem = "_".join(words[:3]) if words else "note"
            candidate = f"{stem}.txt"

        stem, ext = os.path.splitext(candidate)
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("._-") or "note"
        ext = re.sub(r"[^A-Za-z0-9.]+", "", ext.lower())[:10]
        if not ext:
            ext = ".txt"
        if not ext.startswith("."):
            ext = "." + ext
        return f"{stem[:48]}{ext}"

    # ---------------------------------------------------------
    # 🚀 ACTION METHODS (4️⃣ Normalized Returns Applied)
    # ---------------------------------------------------------

    def open_app(self, app_name: str, target: str = "auto") -> dict:
        action = "open_app"
        if not self._check_permission(action):
            return {"status": "blocked", "message": f"Confirmation required to open {app_name}", "risk": self.RISK_LEVELS[action]}
            
        self._log(action, f"Requested to open: {app_name}")
        target = (target or "auto").strip().lower()
        mobile_target = target == "mobile"
        desktop_target = target == "desktop"
        headless = os.getenv("NEON_HEADLESS", "0").strip() == "1"

        if headless and desktop_target:
            return {
                "status": "error",
                "message": "Desktop requested, but I'm running in mobile/server mode. Say 'mobile' to open it on your phone, or run Neon locally for desktop actions.",
                "risk": self.RISK_LEVELS[action],
            }

        # If asked to open on mobile (or running headless on server), return an action
        # the mobile app can execute.
        if mobile_target or headless:
            key = (app_name or "").strip().lower()
            # Clean common filler the LLM might include
            for w in ["open", "launch", "start", "run", "please", "for me", "in mobile", "on mobile", "mobile", "my"]:
                key = key.replace(w, " ")
            key = " ".join(key.split())

            url_map = {
                "youtube": "https://youtube.com",
                "yt": "https://youtube.com",
                "youtube music": "https://music.youtube.com",
                "youtubemusic": "https://music.youtube.com",
                "google": "https://google.com",
                "gmail": "https://mail.google.com",
                "maps": "https://maps.google.com",
                "spotify": "https://open.spotify.com",
                "chatgpt": "https://chatgpt.com",
                "chat gpt": "https://chatgpt.com",
            }
            # App deep-links with web fallback
            deep_links = {
                "whatsapp": {"url": "whatsapp://", "fallback_url": "https://wa.me/"},
                "whatapp": {"url": "whatsapp://", "fallback_url": "https://wa.me/"},
                "wa": {"url": "whatsapp://", "fallback_url": "https://wa.me/"},
                "instagram": {"url": "instagram://app", "fallback_url": "https://instagram.com"},
                "insta": {"url": "instagram://app", "fallback_url": "https://instagram.com"},
            }

            if key in {"camera", "cam"}:
                return {
                    "status": "success",
                    "message": "Opening camera on mobile.",
                    "action": {"type": "open_camera"},
                    "risk": self.RISK_LEVELS[action],
                }
            if key in {"gallery", "photos", "photo", "images", "pics", "pictures"}:
                return {
                    "status": "success",
                    "message": "Opening gallery on mobile.",
                    "action": {"type": "open_gallery"},
                    "risk": self.RISK_LEVELS[action],
                }

            if key in deep_links:
                return {
                    "status": "success",
                    "message": f"Opening {key} on mobile.",
                    "action": {"type": "open_url", **deep_links[key]},
                    "risk": self.RISK_LEVELS[action],
                }

            url = url_map.get(key)
            if url:
                return {
                    "status": "success",
                    "message": f"Opening {key} on mobile.",
                    "action": {"type": "open_url", "url": url},
                    "risk": self.RISK_LEVELS[action],
                }
            return {
                "status": "error",
                "message": f"I can open: YouTube, YouTube Music, Google, Gmail, Maps, Spotify, ChatGPT, WhatsApp, Instagram, Camera, Gallery. You asked for '{app_name}'.",
                "risk": self.RISK_LEVELS[action],
            }

        result = smart_launcher(app_name)
        return {"status": "success", "message": result, "risk": self.RISK_LEVELS[action]}

    def search_google(self, query: str, target: str = "auto") -> dict:
        action = "search_google"
        self._log(action, f"Query: '{query}' | Target: {target}")
        target = (target or "auto").strip().lower()
        mobile_target = target == "mobile"
        desktop_target = target == "desktop"
        headless = os.getenv("NEON_HEADLESS", "0").strip() == "1"
        if headless and desktop_target:
            return {
                "status": "error",
                "message": "Desktop requested, but I'm running in mobile/server mode. Say 'mobile' to open it on your phone, or run Neon locally for desktop actions.",
                "risk": self.RISK_LEVELS[action],
            }
        if query and query.strip():
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            resp = {
                "status": "success",
                "message": f"Opened Google search for '{query}'.",
                "risk": self.RISK_LEVELS[action],
            }
            if headless or mobile_target:
                resp["action"] = {"type": "open_url", "url": url}
            else:
                webbrowser.open(url)
            return resp
        return {"status": "error", "message": "Search query was empty.", "risk": self.RISK_LEVELS[action]}

    def search_youtube(self, query: str, target: str = "auto") -> dict:
        action = "search_youtube"
        self._log(action, f"Query: '{query}' | Target: {target}")
        target = (target or "auto").strip().lower()
        mobile_target = target == "mobile"
        desktop_target = target == "desktop"
        headless = os.getenv("NEON_HEADLESS", "0").strip() == "1"
        if headless and desktop_target:
            return {
                "status": "error",
                "message": "Desktop requested, but I'm running in mobile/server mode. Say 'mobile' to open it on your phone, or run Neon locally for desktop actions.",
                "risk": self.RISK_LEVELS[action],
            }
        if query and query.strip():
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            resp = {
                "status": "success",
                "message": f"Opened YouTube search for '{query}'.",
                "risk": self.RISK_LEVELS[action],
            }
            if headless or mobile_target:
                resp["action"] = {"type": "open_url", "url": url}
            else:
                webbrowser.open(url)
            return resp
        return {"status": "error", "message": "Search query was empty.", "risk": self.RISK_LEVELS[action]}

    def play_music(self, query: str = "", platform: str = "spotify", autoplay: bool = True, target: str = "auto") -> dict:
        action = "play_music"
        self._log(action, f"Query: '{query}' | Platform: {platform} | Autoplay: {autoplay} | Target: {target}")

        platform = (platform or "spotify").strip().lower()
        q = (query or "").strip()
        headless = os.getenv("NEON_HEADLESS", "0").strip() == "1"
        target = (target or "auto").strip().lower()
        mobile_target = target == "mobile"
        desktop_target = target == "desktop"

        if headless and desktop_target:
            return {
                "status": "error",
                "message": "Desktop requested, but I'm running in mobile/server mode. Say 'mobile' to play it on your phone, or run Neon locally for desktop actions.",
                "risk": self.RISK_LEVELS[action],
            }

        def _yt_dlp_first_watch_url(search_query: str) -> str | None:
            """
            Returns a https://www.youtube.com/watch?v=... URL for the top search result
            if yt-dlp is installed, otherwise None.
            """
            if not search_query:
                return None
            if shutil.which("yt-dlp") is None:
                return None
            try:
                # ytsearch1: returns the first result id without scraping ourselves
                completed = subprocess.run(
                    ["yt-dlp", "--get-id", f"ytsearch1:{search_query}"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                video_id = (completed.stdout or "").strip().splitlines()[0].strip() if completed.returncode == 0 else ""
                if not video_id:
                    return None
                return f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
            except Exception:
                return None

        def _youtube_first_watch_url(search_query: str) -> str | None:
            """
            Lightweight fallback: fetch YouTube search HTML and extract the first videoId.
            This avoids extra dependencies, and works on most networks.
            """
            if not search_query:
                return None
            try:
                url = "https://www.youtube.com/results?search_query=" + quote_plus(search_query)
                r = requests.get(
                    url,
                    timeout=10,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                      "Chrome/122.0.0.0 Safari/537.36",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
                if r.status_code != 200:
                    return None

                # YouTube embeds JSON blobs containing "videoId":"<id>"
                m = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', r.text)
                if not m:
                    return None
                video_id = m.group(1)
                return f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
            except Exception:
                return None

        # If no query, just open the platform home.
        if platform in {"youtube", "yt", "youtube music", "youtubemusic"}:
            if q:
                # If possible, resolve and open the TOP result directly.
                if autoplay:
                    top_url = _yt_dlp_first_watch_url(q)
                    if top_url:
                        resp = {
                            "status": "success",
                            "message": f"Playing top YouTube result for '{q}'.",
                            "risk": self.RISK_LEVELS[action],
                        }
                        if headless or mobile_target:
                            resp["action"] = {"type": "open_url", "url": top_url}
                        else:
                            webbrowser.open(top_url)
                        return resp

                    # No yt-dlp: try simple HTML extraction.
                    top_url = _youtube_first_watch_url(q)
                    if top_url:
                        resp = {
                            "status": "success",
                            "message": f"Playing top YouTube result for '{q}'.",
                            "risk": self.RISK_LEVELS[action],
                        }
                        if headless or mobile_target:
                            resp["action"] = {"type": "open_url", "url": top_url}
                        else:
                            webbrowser.open(top_url)
                        return resp

                url = "https://music.youtube.com/search?q=" + quote_plus(q)
                resp = {
                    "status": "success",
                    "message": f"Opened YouTube Music search for '{q}'.",
                    "risk": self.RISK_LEVELS[action],
                }
                if headless or mobile_target:
                    resp["action"] = {"type": "open_url", "url": url}
                else:
                    webbrowser.open(url)
                return resp
            url = "https://music.youtube.com"
            resp = {"status": "success", "message": "Opened YouTube Music.", "risk": self.RISK_LEVELS[action]}
            if headless or mobile_target:
                resp["action"] = {"type": "open_url", "url": url}
            else:
                webbrowser.open(url)
            return resp

        # Default: Spotify
        if q:
            url = "https://open.spotify.com/search/" + quote_plus(q)
            resp = {"status": "success", "message": f"Opened Spotify search for '{q}'.", "risk": self.RISK_LEVELS[action]}
            if headless or mobile_target:
                resp["action"] = {"type": "open_url", "url": url}
            else:
                webbrowser.open(url)
            return resp
        url = "https://open.spotify.com"
        resp = {"status": "success", "message": "Opened Spotify.", "risk": self.RISK_LEVELS[action]}
        if headless or mobile_target:
            resp["action"] = {"type": "open_url", "url": url}
        else:
            webbrowser.open(url)
        return resp

    def system_status(self) -> dict:
        action = "system_status"

        def _check(name: str, url: str, timeout: float = 1.5) -> dict:
            try:
                r = requests.get(url, timeout=timeout)
                ok = 200 <= r.status_code < 400
                return {"ok": ok, "status_code": r.status_code}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        # Ollama
        ollama = _check("ollama", "http://localhost:11434/api/tags", timeout=1.5)

        # TTS (GPT-SoVITS) — no universal health endpoint; try docs and root.
        tts_docs = _check("tts_docs", "http://127.0.0.1:9880/docs", timeout=1.5)
        tts_root = _check("tts_root", "http://127.0.0.1:9880/", timeout=1.5)
        tts_ok = tts_docs.get("ok") or tts_root.get("ok")

        # Backend (uvicorn in launcher) — try /docs and / (safe)
        backend_docs = _check("backend_docs", "http://127.0.0.1:9000/docs", timeout=1.5)
        backend_root = _check("backend_root", "http://127.0.0.1:9000/", timeout=1.5)
        backend_ok = backend_docs.get("ok") or backend_root.get("ok")

        # Service report
        report = {
            "ollama": ollama,
            "tts": {"ok": bool(tts_ok), "docs": tts_docs, "root": tts_root},
            "backend": {"ok": bool(backend_ok), "docs": backend_docs, "root": backend_root},
        }

        def _mark(v: bool) -> str:
            return "OK" if v else "DOWN"

        service_summary = (
            f"Ollama: {_mark(bool(ollama.get('ok')))} | "
            f"TTS: {_mark(bool(tts_ok))} | "
            f"Backend: {_mark(bool(backend_ok))}"
        )

        # ── HARDWARE INFO ────────────────────────────────────────────────────
        hw_summary = ""
        try:
            from core.sysinfo import get_human_report, get_system_snapshot
            hw_summary = get_human_report()
            report["hardware"] = get_system_snapshot()
        except Exception as e:
            hw_summary = f"(Hardware info unavailable: {e})"

        down = [
            name
            for name, ok in {
                "Ollama": bool(ollama.get("ok")),
                "TTS": bool(tts_ok),
                "Backend": bool(backend_ok),
            }.items()
            if not ok
        ]
        if down:
            verb = "is" if len(down) == 1 else "are"
            message = f"{', '.join(down)} {verb} having trouble."
        else:
            message = "All systems look good."

        self._log(action, f"{message}\n{service_summary}\n{hw_summary}")
        return {"status": "success", "message": message, "details": report, "risk": self.RISK_LEVELS[action]}

    def create_file(self, filename: str) -> dict:
        action = "create_file"
        if not self._check_permission(action):
            return {"status": "blocked", "message": f"Confirmation required to create '{filename}'.", "risk": self.RISK_LEVELS[action]}

        safe_name = self._sanitize_filename(filename)
        full_path = self._is_safe_path(safe_name)
        try:
            with open(full_path, 'w') as f:
                f.write("# File created by Neon AI\n")
            self._log(action, f"Created {safe_name} (from input: {filename})")
            return {"status": "success", "message": f"File '{safe_name}' created safely in workspace.", "risk": self.RISK_LEVELS[action]}
        except Exception as e:
            self._log("error", f"Failed to create {safe_name}: {str(e)}")
            return {"status": "error", "message": f"Error creating file: {str(e)}", "risk": self.RISK_LEVELS[action]}

    def delete_file(self, filename: str) -> dict:
        action = "delete_file"
        if not self._check_permission(action):
            return {"status": "blocked", "message": f"Confirmation required to delete '{filename}'.", "risk": self.RISK_LEVELS[action]}

        safe_name = self._sanitize_filename(filename)
        full_path = self._is_safe_path(safe_name)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                self._log(action, f"Deleted {safe_name} (from input: {filename})")
                return {"status": "success", "message": f"File '{safe_name}' permanently deleted.", "risk": self.RISK_LEVELS[action]}
            except Exception as e:
                self._log("error", f"Failed to delete {safe_name}: {str(e)}")
                return {"status": "error", "message": f"Error deleting file: {str(e)}", "risk": self.RISK_LEVELS[action]}
        return {"status": "error", "message": f"File '{safe_name}' not found.", "risk": self.RISK_LEVELS[action]}

    # 📱 WHATSAPP AUTOMATION
    def send_whatsapp_message(self, contact_name: str, message: str) -> dict:
        action = "send_whatsapp_message"
        if not self._check_permission(action):
            return {"status": "blocked", "message": f"Confirmation required to send WhatsApp to {contact_name}.", "risk": self.RISK_LEVELS[action]}

        if not _SELENIUM_OK:
            return {
                "status": "error",
                "message": "WhatsApp automation isn't available. Install dependencies: pip install selenium webdriver-manager",
                "risk": self.RISK_LEVELS[action],
            }

        # 5️⃣ Injection Protection
        contact_name = contact_name.replace("\n", " ").replace("\r", "").strip()
        message = message.replace("\n", " ").replace("\r", "").strip()
        
        self._log(action, f"Initiated send to {contact_name}")
        
        try:
            # 2️⃣ Persistent Browser Session Initialization
            if not self.driver:
                print("📱 [SYSTEM] Booting up WhatsApp Web session...")
                chrome_options = Options()
                # chrome_options.add_argument("--user-data-dir=C:/Users/YourUser/AppData/Local/Google/Chrome/User Data") 
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.driver.get("https://web.whatsapp.com")
            
            wait = WebDriverWait(self.driver, 45) 
            
            search_box_xpath = '//div[@contenteditable="true"][@title="Search input textbox" or @data-tab="3"]'
            message_box_xpath = '//div[@contenteditable="true"][@title="Type a message" or @data-tab="10"]'

            search_box = wait.until(EC.presence_of_element_located((By.XPATH, search_box_xpath)))
            search_box.clear()
            search_box.send_keys(contact_name)
            time.sleep(1) 
            search_box.send_keys(Keys.ENTER)
            
            message_box = wait.until(EC.presence_of_element_located((By.XPATH, message_box_xpath)))
            message_box.send_keys(message)
            message_box.send_keys(Keys.ENTER)
            
            self._log(action, f"Success: Message sent to {contact_name}")
            return {"status": "success", "message": f"WhatsApp message sent to {contact_name}.", "risk": self.RISK_LEVELS[action]}
            
        except Exception as e:
            self._log("error", f"WhatsApp failed for {contact_name}: {str(e)}")
            return {"status": "error", "message": f"WhatsApp automation failed: {str(e)}", "risk": self.RISK_LEVELS[action]}

    # ── 🎭 PERSONALITY MODE SWITCHING ──────────────────────────────────────
    def set_personality(self, mode: str) -> dict:
        """Switch Neon's personality mode at runtime."""
        action = "set_personality"
        valid_modes = {"balanced", "roaster", "curious"}
        mode = (mode or "balanced").strip().lower()
        
        # Fuzzy match common aliases
        aliases = {
            "roast": "roaster", "roasty": "roaster", "teasing": "roaster",
            "tease": "roaster", "savage": "roaster", "spicy": "roaster",
            "chill": "balanced", "normal": "balanced", "default": "balanced",
            "calm": "balanced", "reset": "balanced",
            "curious": "curious", "question": "curious", "ask": "curious",
        }
        mode = aliases.get(mode, mode)
        
        if mode not in valid_modes:
            return {
                "status": "error",
                "message": f"Unknown mode '{mode}'. Choose: balanced, roaster, or curious.",
                "risk": self.RISK_LEVELS[action],
            }
        
        self._log(action, f"Personality mode changed to: {mode}")
        return {
            "status": "success",
            "message": f"Personality switched to {mode} mode.",
            "mode": mode,
            "risk": self.RISK_LEVELS[action],
        }

    # ── 🔊 VOLUME CONTROL ──────────────────────────────────────────────────
    def volume_control(self, action: str = "get", level: int = -1) -> dict:
        """Control system volume: mute, unmute, up, down, set to specific level."""
        act = "volume_control"
        action = (action or "get").strip().lower()
        try:
            level = int(level)
        except (TypeError, ValueError):
            level = -1
        self._log(act, f"Volume action: {action}, level: {level}")

        import shutil as _sh
        has_nircmd = _sh.which("nircmd") is not None

        try:
            if action == "mute":
                if has_nircmd:
                    subprocess.run(["nircmd", "mutesysvolume", "1"], check=True)
                else:
                    subprocess.run(["powershell", "-c",
                        "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"],
                        check=True, capture_output=True)
                return {"status": "success", "message": "Volume muted.", "risk": self.RISK_LEVELS[act]}

            elif action == "unmute":
                if has_nircmd:
                    subprocess.run(["nircmd", "mutesysvolume", "0"], check=True)
                else:
                    subprocess.run(["powershell", "-c",
                        "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"],
                        check=True, capture_output=True)
                return {"status": "success", "message": "Volume unmuted.", "risk": self.RISK_LEVELS[act]}

            elif action == "up":
                step = int(level * 65535 / 100) if level > 0 else 5000
                if has_nircmd:
                    subprocess.run(["nircmd", "changesysvolume", str(step)], check=True)
                else:
                    loops = max(1, level // 2) if level > 0 else 1
                    subprocess.run(["powershell", "-c",
                        f"1..{loops} | % {{ (New-Object -ComObject WScript.Shell).SendKeys([char]175) }}"],
                        check=True, capture_output=True)
                msg = f"Volume increased by {level}%." if level > 0 else "Volume increased."
                return {"status": "success", "message": msg, "risk": self.RISK_LEVELS[act]}

            elif action == "down":
                step = int(level * 65535 / 100) if level > 0 else 5000
                if has_nircmd:
                    subprocess.run(["nircmd", "changesysvolume", str(-step)], check=True)
                else:
                    loops = max(1, level // 2) if level > 0 else 1
                    subprocess.run(["powershell", "-c",
                        f"1..{loops} | % {{ (New-Object -ComObject WScript.Shell).SendKeys([char]174) }}"],
                        check=True, capture_output=True)
                msg = f"Volume decreased by {level}%." if level > 0 else "Volume decreased."
                return {"status": "success", "message": msg, "risk": self.RISK_LEVELS[act]}

            elif action == "set" and 0 <= level <= 100:
                nircmd_val = int(level * 65535 / 100)
                if has_nircmd:
                    subprocess.run(["nircmd", "setsysvolume", str(nircmd_val)], check=True)
                else:
                    ps_cmd = f"""$wshell = New-Object -ComObject WScript.Shell; \
                        Add-Type -TypeDefinition 'using System.Runtime.InteropServices; \
                        public class Vol {{ [DllImport(""winmm.dll"")] \
                        public static extern int waveOutSetVolume(IntPtr hwo, uint dwVolume); }}'; \
                        $v = [int]({level}/100.0*0xFFFF); [Vol]::waveOutSetVolume([IntPtr]::Zero, $v -bor ($v -shl 16))"""
                    subprocess.run(["powershell", "-c", ps_cmd], capture_output=True)
                return {"status": "success", "message": f"Volume set to {level}%.", "risk": self.RISK_LEVELS[act]}

            elif action == "get":
                return {"status": "success", "message": "Use system_status to check audio info.", "risk": self.RISK_LEVELS[act]}

            else:
                return {"status": "error", "message": f"Unknown volume action '{action}'. Use: mute, unmute, up, down, or set.", "risk": self.RISK_LEVELS[act]}

        except Exception as e:
            return {"status": "error", "message": f"Volume control failed: {e}", "risk": self.RISK_LEVELS[act]}

    # ── 🔆 BRIGHTNESS CONTROL ──────────────────────────────────────────────
    def brightness_control(self, action: str = "get", level: int = -1) -> dict:
        """Control screen brightness: up, down, set to specific level."""
        act = "brightness_control"
        action = (action or "get").strip().lower()
        try:
            level = int(level)
        except (TypeError, ValueError):
            level = -1
        self._log(act, f"Brightness action: {action}, level: {level}")

        try:
            if action == "set" and 0 <= level <= 100:
                ps_cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"
                subprocess.run(["powershell", "-c", ps_cmd], check=True, capture_output=True)
                return {"status": "success", "message": f"Brightness set to {level}%.", "risk": self.RISK_LEVELS[act]}

            elif action == "up":
                ps_cmd = """$cur = (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness; \
                    $new = [Math]::Min(100, $cur + 20); \
                    (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, $new)"""
                subprocess.run(["powershell", "-c", ps_cmd], check=True, capture_output=True)
                return {"status": "success", "message": "Brightness increased.", "risk": self.RISK_LEVELS[act]}

            elif action == "down":
                ps_cmd = """$cur = (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness; \
                    $new = [Math]::Max(0, $cur - 20); \
                    (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, $new)"""
                subprocess.run(["powershell", "-c", ps_cmd], check=True, capture_output=True)
                return {"status": "success", "message": "Brightness decreased.", "risk": self.RISK_LEVELS[act]}

            elif action == "get":
                ps_cmd = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
                result = subprocess.run(["powershell", "-c", ps_cmd], capture_output=True, text=True)
                val = result.stdout.strip()
                return {"status": "success", "message": f"Current brightness is {val}%.", "risk": self.RISK_LEVELS[act]}

            else:
                return {"status": "error", "message": f"Unknown brightness action '{action}'. Use: up, down, set, or get.", "risk": self.RISK_LEVELS[act]}

        except Exception as e:
            return {"status": "error", "message": f"Brightness control failed: {e}. This may not work on desktop monitors.", "risk": self.RISK_LEVELS[act]}

    # ── 📸 SCREENSHOT ──────────────────────────────────────────────────────
    def take_screenshot(self) -> dict:
        """Capture a screenshot and save to workspace."""
        act = "take_screenshot"
        self._log(act, "Taking screenshot")

        import shutil as _sh
        has_nircmd = _sh.which("nircmd") is not None
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        full_path = os.path.join(self.safe_root, filename)

        try:
            if has_nircmd:
                subprocess.run(["nircmd", "savescreenshot", full_path], check=True)
            else:
                # PowerShell fallback using .NET
                ps_cmd = f"""Add-Type -AssemblyName System.Windows.Forms; \
                    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; \
                    $bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height); \
                    $graphics = [System.Drawing.Graphics]::FromImage($bitmap); \
                    $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size); \
                    $bitmap.Save('{full_path}'); \
                    $graphics.Dispose(); $bitmap.Dispose()"""
                subprocess.run(["powershell", "-c", ps_cmd], check=True, capture_output=True)

            self._log(act, f"Screenshot saved: {filename}")
            return {"status": "success", "message": f"Screenshot saved as {filename}.", "risk": self.RISK_LEVELS[act]}

        except Exception as e:
            return {"status": "error", "message": f"Screenshot failed: {e}", "risk": self.RISK_LEVELS[act]}

    # ── 🔒 LOCK SCREEN ─────────────────────────────────────────────────────
    def lock_screen(self) -> dict:
        """Lock the computer screen."""
        act = "lock_screen"
        if not self._check_permission(act):
            return {"status": "blocked", "message": "Confirmation required to lock screen.", "risk": self.RISK_LEVELS[act]}

        self._log(act, "Locking screen")

        try:
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.user32.LockWorkStation()
            elif sys.platform == "darwin":
                subprocess.run(["pmset", "displaysleepnow"], check=True)
            else:
                subprocess.run(["loginctl", "lock-session"], check=True)

            return {"status": "success", "message": "Screen locked.", "risk": self.RISK_LEVELS[act]}

        except Exception as e:
            return {"status": "error", "message": f"Lock failed: {e}", "risk": self.RISK_LEVELS[act]}

    # ── ⚡ POWER CONTROL ────────────────────────────────────────────────────
    def power_control(self, action: str = "sleep") -> dict:
        """Shutdown, restart, or sleep the computer."""
        act = "power_control"
        if not self._check_permission(act):
            return {"status": "blocked", "message": f"Confirmation required to {action}.", "risk": self.RISK_LEVELS[act]}

        action = (action or "sleep").strip().lower()
        self._log(act, f"Power action: {action}")

        try:
            if sys.platform == "win32":
                if action == "shutdown":
                    subprocess.run(["shutdown", "/s", "/t", "5"], check=True)
                    return {"status": "success", "message": "Shutting down in 5 seconds.", "risk": self.RISK_LEVELS[act]}
                elif action == "restart":
                    subprocess.run(["shutdown", "/r", "/t", "5"], check=True)
                    return {"status": "success", "message": "Restarting in 5 seconds.", "risk": self.RISK_LEVELS[act]}
                elif action == "sleep":
                    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True)
                    return {"status": "success", "message": "Going to sleep.", "risk": self.RISK_LEVELS[act]}
                elif action == "cancel":
                    subprocess.run(["shutdown", "/a"], check=True)
                    return {"status": "success", "message": "Shutdown cancelled.", "risk": self.RISK_LEVELS[act]}
                else:
                    return {"status": "error", "message": f"Unknown power action '{action}'. Use: shutdown, restart, sleep, or cancel.", "risk": self.RISK_LEVELS[act]}
            else:
                if action == "shutdown":
                    subprocess.run(["shutdown", "-h", "now"], check=True)
                elif action == "restart":
                    subprocess.run(["shutdown", "-r", "now"], check=True)
                elif action == "sleep":
                    subprocess.run(["systemctl", "suspend"], check=True)
                else:
                    return {"status": "error", "message": f"Unknown power action '{action}'.", "risk": self.RISK_LEVELS[act]}
                return {"status": "success", "message": f"Power action: {action}.", "risk": self.RISK_LEVELS[act]}

        except Exception as e:
            return {"status": "error", "message": f"Power control failed: {e}", "risk": self.RISK_LEVELS[act]}

    # ── 📡 CONNECTIVITY TOGGLE ─────────────────────────────────────────────
    def toggle_connectivity(self, target: str = "wifi", state: str = "toggle") -> dict:
        """Enable, disable, or toggle WiFi / Bluetooth."""
        act = "toggle_connectivity"
        if not self._check_permission(act):
            return {"status": "blocked", "message": f"Confirmation required to change {target}.", "risk": self.RISK_LEVELS[act]}

        target = (target or "wifi").strip().lower()
        state = (state or "toggle").strip().lower()
        self._log(act, f"Connectivity: {target} -> {state}")

        adapter_map = {
            "wifi": "Wi-Fi",
            "wi-fi": "Wi-Fi",
            "bluetooth": "Bluetooth",
            "bt": "Bluetooth",
        }
        adapter_name = adapter_map.get(target)
        if not adapter_name:
            return {"status": "error", "message": f"Unknown target '{target}'. Use: wifi or bluetooth.", "risk": self.RISK_LEVELS[act]}

        try:
            if sys.platform == "win32":
                if state == "on" or state == "enable":
                    ps_cmd = f'Enable-NetAdapter -Name "{adapter_name}" -Confirm:$false'
                    subprocess.run(["powershell", "-c", ps_cmd], check=True, capture_output=True)
                    return {"status": "success", "message": f"{adapter_name} enabled.", "risk": self.RISK_LEVELS[act]}
                elif state == "off" or state == "disable":
                    ps_cmd = f'Disable-NetAdapter -Name "{adapter_name}" -Confirm:$false'
                    subprocess.run(["powershell", "-c", ps_cmd], check=True, capture_output=True)
                    return {"status": "success", "message": f"{adapter_name} disabled.", "risk": self.RISK_LEVELS[act]}
                elif state == "toggle":
                    ps_cmd = f"""$a = Get-NetAdapter -Name '{adapter_name}' -ErrorAction SilentlyContinue; \
                        if ($a.Status -eq 'Up') {{ Disable-NetAdapter -Name '{adapter_name}' -Confirm:$false; 'disabled' }} \
                        else {{ Enable-NetAdapter -Name '{adapter_name}' -Confirm:$false; 'enabled' }}"""
                    result = subprocess.run(["powershell", "-c", ps_cmd], capture_output=True, text=True)
                    new_state = result.stdout.strip()
                    return {"status": "success", "message": f"{adapter_name} {new_state}.", "risk": self.RISK_LEVELS[act]}
                else:
                    return {"status": "error", "message": f"Unknown state '{state}'. Use: on, off, or toggle.", "risk": self.RISK_LEVELS[act]}
            else:
                # Linux: nmcli for WiFi, bluetoothctl for BT
                if target in {"wifi", "wi-fi"}:
                    if state in {"on", "enable"}:
                        subprocess.run(["nmcli", "radio", "wifi", "on"], check=True)
                    elif state in {"off", "disable"}:
                        subprocess.run(["nmcli", "radio", "wifi", "off"], check=True)
                    else:
                        result = subprocess.run(["nmcli", "radio", "wifi"], capture_output=True, text=True)
                        current = result.stdout.strip()
                        new = "off" if current == "enabled" else "on"
                        subprocess.run(["nmcli", "radio", "wifi", new], check=True)
                else:
                    if state in {"on", "enable"}:
                        subprocess.run(["bluetoothctl", "power", "on"], check=True)
                    elif state in {"off", "disable"}:
                        subprocess.run(["bluetoothctl", "power", "off"], check=True)
                    else:
                        subprocess.run(["bluetoothctl", "power", "on"], check=True)
                return {"status": "success", "message": f"{adapter_name} {state}.", "risk": self.RISK_LEVELS[act]}

        except Exception as e:
            return {"status": "error", "message": f"Connectivity toggle failed: {e}", "risk": self.RISK_LEVELS[act]}

    # Helper to cleanly close the browser when shutting down Neon
    def close_whatsapp_session(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self._log("system", "Closed WhatsApp browser session.")
