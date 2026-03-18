import sys
import os
import time

# Add project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from brain.llm import NeonBrain

print("[NEON] Booting up Neon Brain...")
neon = NeonBrain()
print("[OK] Neon is ready.")

# ----------------------------------------------------
# 🔥 PERSISTENT CHROME PROFILE (NO QR EVERY TIME)
# ----------------------------------------------------
chrome_options = webdriver.ChromeOptions()

# Dedicated automation profile (recommended)
profile_path = "C:/neon_whatsapp_profile"
os.makedirs(profile_path, exist_ok=True)

chrome_options.add_argument(f"user-data-dir={profile_path}")
chrome_options.add_argument("--profile-directory=Default")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)

driver.get("https://web.whatsapp.com")

print("[NEON] Waiting for WhatsApp to load...")

wait = WebDriverWait(driver, 60)

# Wait until chat panel loads (means logged in)
wait.until(
    EC.presence_of_element_located(
        (By.XPATH, "//*[@id='pane-side']")
    )
)

print("[OK] WhatsApp Ready (No QR needed after first login).")

# ----------------------------------------------------

last_processed_msg = ""
pending_messages = []
awaiting_important_reply = False
BUSY_MODE = True

print("[NEON] Monitoring chat...")

while True:
    try:
        messages = driver.find_elements(
            By.XPATH,
            "//div[contains(@class,'message-in')]//span[@dir='ltr']"
        )

        if messages:
            current_last_message = messages[-1].text.strip()

            if (
                current_last_message
                and current_last_message != last_processed_msg
            ):

                # Prevent self-reply loop
                if current_last_message.startswith("Ansh is busy"):
                    last_processed_msg = current_last_message
                    continue

                print(f"\n📩 User: {current_last_message}")
                lower_msg = current_last_message.lower()

                # ------------------------------------
                # SUMMARY COMMAND
                # ------------------------------------
                if lower_msg in [
                    "summarize messages",
                    "any important messages?",
                    "what did they say?",
                    "summary"
                ]:

                    if pending_messages:
                        summary_prompt = (
                            "Summarize these messages briefly:\n\n"
                            + "\n".join(pending_messages)
                        )
                        reply = neon.chat(summary_prompt) or "No summary available."
                        pending_messages.clear()
                    else:
                        reply = "No important messages received."

                # ------------------------------------
                # BUSY MODE
                # ------------------------------------
                elif BUSY_MODE:

                    if not awaiting_important_reply:
                        reply = "Ansh is busy right now. If this is important, please tell me."
                        awaiting_important_reply = True

                    else:
                        pending_messages.append(current_last_message)
                        reply = "Got it. I will let him know."
                        awaiting_important_reply = False

                # ------------------------------------
                # NORMAL MODE
                # ------------------------------------
                else:
                    reply = neon.chat(current_last_message) or "..."

                print(f"🤖 Neon: {reply}")

                # Wait for message box safely
                box = wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//*[@id='main']//div[@contenteditable='true' and @role='textbox']")
                    )
                )

                for line in reply.split("\n"):
                    box.send_keys(line)
                    box.send_keys(Keys.SHIFT, Keys.ENTER)

                box.send_keys(Keys.ENTER)

                last_processed_msg = current_last_message

    except NoSuchElementException:
        pass
    except Exception as e:
        print(f"[WARN] ERROR: {e}")

    time.sleep(3)