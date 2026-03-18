import sys
import time
import os
import colorama
import itertools
from colorama import Fore, Style
from concurrent.futures import ThreadPoolExecutor

# =========================
# NEON CORE
# =========================
try:
    from brain.llm import NeonBrain
    from voice.set_model import set_models
    from voice.set_reference import set_reference
    from voice.speak import speak, configure_voice_style
    from voice.hear import listen
except ImportError as e:
    print(f"[ERROR] Import Error: {e}")
    sys.exit(1)

# UI Setup
colorama.init(autoreset=True)

# GLOBAL SETTINGS
TYPING_ENABLED = True
VOICE_ENABLED = True
STOP_REQUESTED = False

# --- HELPER FUNCTIONS ---

def status(msg: str, color=Fore.YELLOW):
    """Prints a clear, standardized status update."""
    print(f"{color}[STATUS] {msg}{Style.RESET_ALL}")

def animated_thinking(future, msg="Thinking"):
    """Non-blocking spinner that keeps UI alive while brain computes."""
    spinner = itertools.cycle(['|', '/', '-', '\\'])
    while not future.done():
        sys.stdout.write(f'\r{Fore.CYAN}[STATUS] {msg} {next(spinner)}{Style.RESET_ALL}')
        sys.stdout.flush()
        time.sleep(0.1)
    # Safely clear the line without fragile ANSI codes
    sys.stdout.write(f'\r{" " * (len(msg) + 15)}\r')

def print_commands():
    """Displays the help menu."""
    print(f"""{Fore.YELLOW}
    ╔════════════════════════════════════╗
    ║           NEON COMMANDS            ║
    ╠════════════════════════════════════╣
    ║  [Enter]  → Speak (Voice Input)    ║
    ║  v        → Toggle Voice ON/OFF    ║
    ║  t        → Toggle Typing Effect   ║
    ║  cls      → Clear Screen           ║
    ║  stop     → Stop / Cancel Output   ║
    ║  help     → Show This Menu         ║
    ║  exit     → Quit System            ║
    ╚════════════════════════════════════╝
    {Style.RESET_ALL}""")

def type_effect(text: str, delay: float = 0.02):
    """Typing effect with global toggle support."""
    global STOP_REQUESTED
    
    if not TYPING_ENABLED:
        print(text)
        return

    if len(text) > 150: delay = 0.005
    
    for ch in text:
        if STOP_REQUESTED:
            break # Bail out if user yelled stop
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()

# --- MAIN LOOP ---

def main():
    global TYPING_ENABLED, VOICE_ENABLED, STOP_REQUESTED

    print(f"{Fore.CYAN}Initializing Neon Neural Core...")

    # 1️⃣ INIT SYSTEM
    try:
        brain = NeonBrain()
        status("Brain Online", Fore.GREEN)
    except Exception as e:
        status(f"Brain Init Failed: {e}", Fore.RED)
        return

    status("Initializing Voice System...", Fore.BLUE)
    try:
        set_models()
        set_reference()
        # Apply persisted voice style preference (if present)
        prefs = getattr(brain, "memory", None)
        style = None
        try:
            style = (prefs.state.get("prefs") or {}).get("voice_style") if prefs else None
        except Exception:
            style = None
        configure_voice_style(style or "default")
        status("Voice System Online", Fore.GREEN)
    except Exception:
        status("Voice Disabled (Driver Error)", Fore.RED)
        VOICE_ENABLED = False

    # 2️⃣ WELCOME
    print_commands()
    
    # Boot Greeting (Safe Attribute Check)
    if getattr(brain, "_boot_memory", None):
        boot_msg = brain.chat("*User comes online.*")
        if boot_msg:
            print(f"{Fore.MAGENTA}Neon: ", end="")
            type_effect(boot_msg)
            if VOICE_ENABLED: speak(boot_msg)

    # 3️⃣ CHAT LOOP
    last_input = None
    last_voice_time = 0
    executor = ThreadPoolExecutor(max_workers=2)
    
    try:
        while True:
            STOP_REQUESTED = False # Reset flag on new loop
            
            print(f"\n{Fore.CYAN}You > {Style.RESET_ALL}", end="")
            user_input = input().strip()

            # --- VOICE INPUT HANDLER (With Debounce) ---
            if user_input == "":
                if time.time() - last_voice_time < 2.0:
                    status("Mic cooldown active. Wait a second.", Fore.YELLOW)
                    continue
                
                last_voice_time = time.time()
                
                if VOICE_ENABLED:
                    status("Listening...", Fore.YELLOW)
                    voice_text = listen()
                    
                    if not voice_text:
                        status("Didn't catch that.", Fore.RED)
                        continue
                    
                    user_input = voice_text
                    print(f"{Fore.CYAN}You (Voice): {Fore.WHITE}{user_input}")
                else:
                    status("Voice is OFF. Type 'v' to enable.", Fore.RED)
                    continue

            # --- MIC SELF-HEARING CHECK (Strengthened) ---
            if user_input.lower() == (last_input or "").strip().lower():
                continue
            last_input = user_input

            # --- COMMANDS ---
            cmd = user_input.lower()
            
            if cmd in ["exit", "quit", "bye"]:
                status("Shutting down...", Fore.RED)
                if VOICE_ENABLED: speak("Bye boss.")
                break

            elif cmd == "help":
                print_commands()
                continue

            elif cmd == "cls":
                os.system("cls" if os.name == "nt" else "clear")
                print_commands()
                continue

            elif cmd == "v":
                VOICE_ENABLED = not VOICE_ENABLED
                status(f"Voice Output {'ENABLED' if VOICE_ENABLED else 'DISABLED'}", 
                       Fore.GREEN if VOICE_ENABLED else Fore.RED)
                if VOICE_ENABLED: speak("Voice online.")
                continue

            elif cmd == "t":
                TYPING_ENABLED = not TYPING_ENABLED
                status(f"Typing Effect {'ENABLED' if TYPING_ENABLED else 'DISABLED'}", Fore.CYAN)
                continue
            
            elif cmd == "stop":
                STOP_REQUESTED = True
                status("Output flagged to stop.", Fore.RED)
                continue

            # --- THINKING PHASE (Background Threaded) ---
            future = executor.submit(brain.chat, user_input)
            animated_thinking(future, "Thinking")
            reply = future.result()

            # --- OUTPUT PHASE ---
            if reply and not STOP_REQUESTED:
                print(f"{Fore.MAGENTA}Neon: {Fore.WHITE}", end="")
                type_effect(reply)

                if VOICE_ENABLED and not STOP_REQUESTED:
                    status("Speaking...", Fore.BLUE)
                    if reply.strip() and reply.strip() not in ["...", "Hmm."]:
                        speak(reply) # Needs internal STOP_REQUESTED check to cancel mid-sentence
                    # Clear speaking status safely
                    sys.stdout.write(f'\r{" " * 30}\r')

    except KeyboardInterrupt:
        print("\nForce Quit.")

    finally:
        executor.shutdown(wait=False)
        if 'brain' in locals():
            # Save memory before exit
            if hasattr(brain, 'memory') and hasattr(brain, 'engine'):
                brain.memory.save(brain.engine.get_state())
                status("Memory Saved.", Fore.GREEN)

if __name__ == "__main__":
    main()