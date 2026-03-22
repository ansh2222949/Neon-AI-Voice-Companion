"""Quick test for command_flavor.py"""
import sys, os
sys.path.insert(0, "d:\\neon")
os.chdir("d:\\neon")

from brain.command_flavor import flavor_command_response

tests = [
    ("WARM open_app", "open_app", "Opened YouTube.", "open youtube",
     {"emotion": "playful", "intensity": 0.6, "affection": 72}),
    ("BASE search_google", "search_google", "Opened Google search for 'anime'.", "search google for anime",
     {"emotion": "calm", "intensity": 0.5, "affection": 50}),
    ("COLD open_app", "open_app", "Opened Chrome.", "open chrome",
     {"emotion": "mad", "intensity": 0.8, "affection": 30}),
    ("WARM play_music", "play_music", "Playing top YouTube result for 'lofi beats'.", "play lofi beats",
     {"emotion": "happy", "intensity": 0.7, "affection": 80}),
    ("ERROR", "open_app", "'Discord' not found on system.", "open discord",
     {"emotion": "calm", "intensity": 0.5, "affection": 55}),
    ("WARM search_youtube", "search_youtube", "Opened YouTube search for 'funny cats'.", "search youtube for funny cats",
     {"emotion": "excited", "intensity": 0.7, "affection": 75}),
]

all_ok = True
for label, action, raw, user, status in tests:
    result = flavor_command_response(action, raw, user, status)
    print(f"[{label}]")
    print(f"  Raw:     {raw}")
    print(f"  Flavored: {result}")
    if not result or not result.strip():
        print(f"  *** FAIL: empty result!")
        all_ok = False
    if result == raw:
        print(f"  *** WARN: result unchanged from raw (flavor may not be applying)")
    print()

print("ALL TESTS PASSED!" if all_ok else "SOME TESTS FAILED!")
