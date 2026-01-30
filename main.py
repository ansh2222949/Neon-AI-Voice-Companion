import sys
import time
import colorama
from colorama import Fore, Style

# =========================
# NEON CORE
# =========================
from brain.llm import NeonBrain

# =========================
# VOICE MODULES
# =========================
from voice.set_model import set_models
from voice.set_reference import set_reference
from voice.speak import speak
from voice.hear import listen            # 🎙️ Voice Input

# UI Setup
colorama.init(autoreset=True)

def type_effect(text: str, delay: float = 0.02):
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def main():
    print(f"{Fore.CYAN}🧠 Initializing Neon Neural Core...")

    # 1️⃣ INIT BRAIN
    try:
        brain = NeonBrain()
    except Exception as e:
        print(f"{Fore.RED}❌ Brain Init Failed: {e}")
        return

    # 2️⃣ INIT VOICE SYSTEM
    print(f"{Fore.BLUE}🔊 Initializing Voice System...")
    set_models()       # GPT + SoVITS weights
    set_reference()    # reference_clean.wav
    
    voice_enabled = True

    print(f"{Fore.GREEN}✅ System Online.")
    print(f"{Fore.YELLOW}💬 usage: Type text OR press Enter to speak (if Voice ON).\n")

    # 3️⃣ SMART GREETING
    if brain.boot_context:
        greeting = brain.chat("*User comes online.*")
        if greeting:
            print(f"{Fore.MAGENTA}Neon: ", end="")
            type_effect(greeting)
            
            if voice_enabled:
                speak(greeting)

    # 4️⃣ CHAT LOOP
    try:
        while True:
            # --- DUAL INPUT UI ---
            print(f"{Fore.CYAN}You (Type or Enter): {Style.RESET_ALL}", end="")
            user_input = input().strip()

            # --- VOICE INPUT LOGIC ---
            if user_input == "":
                if voice_enabled:
                    print(f"{Fore.YELLOW}🎤 Listening... {Style.RESET_ALL}", end="\r")
                    voice_text = listen()
                    
                    if not voice_text:
                        print(f"{Fore.RED}❌ Didn't catch that.{Style.RESET_ALL}")
                        continue
                    
                    user_input = voice_text
                    print(f"{Fore.CYAN}You (Voice): {Fore.WHITE}{user_input}")
                else:
                    print(f"{Fore.RED}⚠️ Voice is OFF. Type or toggle 'v'.")
                    continue

            # --- COMMANDS ---
            if user_input.lower() in ["exit", "quit", "bye"]:
                print(f"{Fore.MAGENTA}Neon: Bye bye! Take care.")
                if voice_enabled:
                    speak("Bye bye! Take care.")
                time.sleep(2)
                break

            if user_input.lower() == "v":
                voice_enabled = not voice_enabled
                print(f"{Fore.YELLOW}[SYSTEM] Voice: {'ON' if voice_enabled else 'OFF'}")
                continue

            # --- BRAIN PROCESSING ---
            reply = brain.chat(user_input)

            if reply:
                # 1. Print Text
                print(f"{Fore.MAGENTA}Neon: {Fore.WHITE}", end="")
                type_effect(reply)

                # 2. Speak
                if voice_enabled:
                    speak(reply)

    except KeyboardInterrupt:
        print("\n👋 Force Quit.")

    finally:
        if 'brain' in locals():
            brain.memory.save(brain.engine.get_state(), "EXIT")
            print(f"{Fore.GREEN}[SYSTEM] Memory Saved.")

if __name__ == "__main__":
    main()