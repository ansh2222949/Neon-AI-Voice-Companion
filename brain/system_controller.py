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
        "create_file": "medium",
        "delete_file": "high",
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
            if (not headless) and (not mobile_target):
                webbrowser.open(url)
            return {
                "status": "success",
                "message": f"Opened Google search for '{query}'.",
                "action": {"type": "open_url", "url": url},
                "risk": self.RISK_LEVELS[action],
            }
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
            if (not headless) and (not mobile_target):
                webbrowser.open(url)
            return {
                "status": "success",
                "message": f"Opened YouTube search for '{query}'.",
                "action": {"type": "open_url", "url": url},
                "risk": self.RISK_LEVELS[action],
            }
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
                        if (not headless) and (not mobile_target):
                            webbrowser.open(top_url)
                        return {
                            "status": "success",
                            "message": f"Playing top YouTube result for '{q}'.",
                            "action": {"type": "open_url", "url": top_url},
                            "risk": self.RISK_LEVELS[action],
                        }

                    # No yt-dlp: try simple HTML extraction.
                    top_url = _youtube_first_watch_url(q)
                    if top_url:
                        if (not headless) and (not mobile_target):
                            webbrowser.open(top_url)
                        return {
                            "status": "success",
                            "message": f"Playing top YouTube result for '{q}'.",
                            "action": {"type": "open_url", "url": top_url},
                            "risk": self.RISK_LEVELS[action],
                        }

                url = "https://music.youtube.com/search?q=" + quote_plus(q)
                if (not headless) and (not mobile_target):
                    webbrowser.open(url)
                return {
                    "status": "success",
                    "message": f"Opened YouTube Music search for '{q}'.",
                    "action": {"type": "open_url", "url": url},
                    "risk": self.RISK_LEVELS[action],
                }
            webbrowser.open("https://music.youtube.com")
            url = "https://music.youtube.com"
            if (not headless) and (not mobile_target):
                webbrowser.open(url)
            return {"status": "success", "message": "Opened YouTube Music.", "action": {"type": "open_url", "url": url}, "risk": self.RISK_LEVELS[action]}

        # Default: Spotify
        if q:
            url = "https://open.spotify.com/search/" + quote_plus(q)
            if (not headless) and (not mobile_target):
                webbrowser.open(url)
            return {"status": "success", "message": f"Opened Spotify search for '{q}'.", "action": {"type": "open_url", "url": url}, "risk": self.RISK_LEVELS[action]}
        url = "https://open.spotify.com"
        if (not headless) and (not mobile_target):
            webbrowser.open(url)
        return {"status": "success", "message": "Opened Spotify.", "action": {"type": "open_url", "url": url}, "risk": self.RISK_LEVELS[action]}

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

        report = {
            "ollama": ollama,
            "tts": {"ok": bool(tts_ok), "docs": tts_docs, "root": tts_root},
            "backend": {"ok": bool(backend_ok), "docs": backend_docs, "root": backend_root},
        }

        # Human-friendly summary string (for the tool result)
        def _mark(v: bool) -> str:
            return "OK" if v else "DOWN"

        summary = (
            f"Ollama: {_mark(bool(ollama.get('ok')))} | "
            f"TTS: {_mark(bool(tts_ok))} | "
            f"Backend: {_mark(bool(backend_ok))}"
        )

        self._log(action, summary)
        return {"status": "success", "message": summary, "details": report, "risk": self.RISK_LEVELS[action]}

    def create_file(self, filename: str) -> dict:
        action = "create_file"
        if not self._check_permission(action):
            return {"status": "blocked", "message": f"Confirmation required to create '{filename}'.", "risk": self.RISK_LEVELS[action]}

        full_path = self._is_safe_path(filename)
        try:
            with open(full_path, 'w') as f:
                f.write("# File created by Neon AI\n")
            self._log(action, f"Created {filename}")
            return {"status": "success", "message": f"File '{filename}' created safely in workspace.", "risk": self.RISK_LEVELS[action]}
        except Exception as e:
            self._log("error", f"Failed to create {filename}: {str(e)}")
            return {"status": "error", "message": f"Error creating file: {str(e)}", "risk": self.RISK_LEVELS[action]}

    def delete_file(self, filename: str) -> dict:
        action = "delete_file"
        if not self._check_permission(action):
            return {"status": "blocked", "message": f"Confirmation required to delete '{filename}'.", "risk": self.RISK_LEVELS[action]}

        full_path = self._is_safe_path(filename)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                self._log(action, f"Deleted {filename}")
                return {"status": "success", "message": f"File '{filename}' permanently deleted.", "risk": self.RISK_LEVELS[action]}
            except Exception as e:
                self._log("error", f"Failed to delete {filename}: {str(e)}")
                return {"status": "error", "message": f"Error deleting file: {str(e)}", "risk": self.RISK_LEVELS[action]}
        return {"status": "error", "message": f"File '{filename}' not found.", "risk": self.RISK_LEVELS[action]}

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

    # Helper to cleanly close the browser when shutting down Neon
    def close_whatsapp_session(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self._log("system", "Closed WhatsApp browser session.")