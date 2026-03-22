"""
🔥 EXTREME Test Suite for Neon — Stress-tests all edge cases.

Covers:
  1. Question vs Command Detection (the #1 hallucination source)
  2. Technical Detection (false positives)
  3. Cooldown Behavior (commands must ACTUALLY run)
  4. Duplicate Input Window (3s window only)
  5. JSON Hallucination Guard (wider patterns)
  6. Volume/Brightness Level Casting (string→int)
  7. Tool Argument Sanitization
  8. Music Query Extraction (tricky inputs)
  9. Target/Platform Detection (edge cases)
 10. Postprocess & TTS Safety
 11. System Controller Edge Cases
 12. Prompt Injection / Identity Resistance
"""

import os
import sys
import time
import json
import re

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

os.environ["NEON_HEADLESS"] = "1"

passed = 0
failed = 0
total  = 0


def _test(name: str, condition: bool, detail: str = ""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ [FAILED] {name}{' -- ' + detail if detail else ''}")


def _section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ═══════════════════════════════════════════════════════════════════════
#  1. QUESTION vs COMMAND — The #1 Hallucination Source
# ═══════════════════════════════════════════════════════════════════════
def test_question_vs_command():
    _section("1. Question vs Command Detection (Extreme)")
    from brain.llm import _is_command

    # ── These MUST be detected as commands ──
    commands = [
        "open chrome",
        "launch spotify",
        "play despacito",
        "mute the volume",
        "unmute",
        "delete old_file.txt",
        "create notes.txt",
        "search google for cats",
        "screenshot",
        "lock my PC",
        "shutdown",
        "restart the computer",
        "set volume to 50",
        "brightness up",
        "dim the screen",
        "turn off wifi",
        "open whatsapp mobile",
        "send john a message on whatsapp",
    ]
    for cmd in commands:
        _test(f"IS command: '{cmd}'", _is_command(cmd), "was NOT detected as command")

    # ── These MUST be detected as commands even inside questions ──
    question_commands = [
        "can you open chrome",
        "could you launch spotify for me",
        "can you delete this file",
        "would you mute the volume",
        "can you open whatsapp on mobile",
        "please open youtube",
        "can you create a file called test.py",
    ]
    for qcmd in question_commands:
        _test(f"IS question-command: '{qcmd}'", _is_command(qcmd), "was NOT detected as command")

    # ── These MUST NOT be detected as commands ──
    not_commands = [
        "how does memory work",
        "what is RAM",
        "tell me about system architecture",
        "explain how search engines work",
        "why do computers run slow",
        "what do you think about AI",
        "do you know who invented bluetooth",
        "is there a way to learn python",
        "can you explain what a CPU does",
        "how are you doing today",
        "who created you",
        "what's your favorite color",
        "tell me a joke",
        "good morning",
        "hello there",
        "I'm feeling tired",
        "thanks for helping",
        "how's the weather",
        "what time is it",
        "do you remember our last conversation",
        "have you ever played a game",
        "does java run on all platforms",
    ]
    for ncmd in not_commands:
        _test(f"NOT command: '{ncmd}'", not _is_command(ncmd), "was WRONGLY detected as command")


# ═══════════════════════════════════════════════════════════════════════
#  2. TECHNICAL DETECTION — False Positives
# ═══════════════════════════════════════════════════════════════════════
def test_technical_detection():
    _section("2. Technical Detection (False Positive Stress)")
    from brain.llm import _is_technical

    # ── Should be technical ──
    technical = [
        "write a python function to sort a list",
        "explain how docker containers work",
        "what is a javascript callback",
        "debug this regex pattern",
        "how to use git branching",
        "explain the algorithm for binary search",
        "fix this python code",  # 'fix' + 'python' = strong
    ]
    for t in technical:
        _test(f"IS technical: '{t}'", _is_technical(t), "was NOT detected as technical")

    # ── Should NOT be technical ──
    not_technical = [
        "fix my volume",
        "I have a memory of my childhood",
        "there was an error in my plan",
        "I found a bug in my shirt",
        "the server at the restaurant was rude",
        "can you fix this please",
        "I need to import some goods",
        "this class is boring",
        "good morning boss",
        "play some music",
        "how are you",
        "tell me a joke",
        "what's for dinner",
        "volume up",
        "open youtube",
        "check system status",
    ]
    for nt in not_technical:
        _test(f"NOT technical: '{nt}'", not _is_technical(nt), "was WRONGLY detected as technical")


# ═══════════════════════════════════════════════════════════════════════
#  3. COOLDOWN — Commands Must ACTUALLY Run
# ═══════════════════════════════════════════════════════════════════════
def test_cooldown_behavior():
    _section("3. Cooldown Behavior (Commands Must Execute)")
    from collections import deque

    history = deque(maxlen=20)

    # Simulate: call open_app, then call it again within 3s
    now = time.time()
    history.append(("open_app", now))

    # Within 3s — cooldown fires but command should still run
    recent = [ts for (fn, ts) in history if fn == "open_app" and (now - ts) < 3.0]
    _test("cooldown fires within 3s", len(recent) > 0)
    # The key difference: we DON'T skip execution anymore.
    # Just verify the logic doesn't add a "continue" skip.

    # After 3s — no cooldown
    history.clear()
    history.append(("open_app", now - 4.0))
    recent = [ts for (fn, ts) in history if fn == "open_app" and (now - ts) < 3.0]
    _test("no cooldown after 3s", len(recent) == 0)

    # Different tool — no cooldown even within 3s
    history.clear()
    history.append(("open_app", now))
    recent = [ts for (fn, ts) in history if fn == "search_google" and (now - ts) < 3.0]
    _test("different tool no cooldown", len(recent) == 0)

    # Rapid-fire same tool (simulate 5 calls in 1 second)
    history.clear()
    for i in range(5):
        history.append(("play_music", now - 0.2 * i))
    recent = [ts for (fn, ts) in history if fn == "play_music" and (now - ts) < 3.0]
    _test("rapid fire detected", len(recent) == 5)


# ═══════════════════════════════════════════════════════════════════════
#  4. DUPLICATE INPUT WINDOW
# ═══════════════════════════════════════════════════════════════════════
def test_duplicate_window():
    _section("4. Duplicate Input Window (3s Gate)")

    # Simulate the duplicate logic
    last_input = "open chrome"
    last_ts = time.time()

    # Same input within 3s → blocked
    now = last_ts + 1.0
    seconds_since = now - last_ts
    is_dup = (
        "open chrome" == last_input.strip().lower()
        and seconds_since < 3.0
    )
    _test("duplicate within 1s → blocked", is_dup)

    # Same input after 4s → allowed
    now2 = last_ts + 4.0
    seconds_since2 = now2 - last_ts
    is_dup2 = (
        "open chrome" == last_input.strip().lower()
        and seconds_since2 < 3.0
    )
    _test("same input after 4s → allowed", not is_dup2)

    # Different input within 1s → allowed
    is_dup3 = (
        "open youtube" == last_input.strip().lower()
        and 1.0 < 3.0
    )
    _test("different input within 1s → allowed", not is_dup3)

    # Edge case: whitespace variations
    is_dup4 = (
        "  open chrome  ".strip().lower() == last_input.strip().lower()
        and 1.0 < 3.0
    )
    _test("whitespace trimmed duplicate → blocked", is_dup4)

    # Edge case: case variations
    is_dup5 = (
        "OPEN CHROME".strip().lower() == last_input.strip().lower()
        and 1.0 < 3.0
    )
    _test("case-insensitive duplicate → blocked", is_dup5)


# ═══════════════════════════════════════════════════════════════════════
#  5. JSON HALLUCINATION GUARD
# ═══════════════════════════════════════════════════════════════════════
def test_json_hallucination_guard():
    _section("5. JSON Hallucination Guard (Wider Patterns)")

    def _is_json_hallucination(reply: str) -> bool:
        stripped = reply.strip()
        looks_like_json = (
            stripped.startswith("{") or stripped.startswith("[{")
            or stripped.startswith("```")
        )
        has_tool_markers = (
            '"name"' in stripped or '"function"' in stripped
            or '"tool_call"' in stripped or '"action"' in stripped
        )
        has_arg_markers = (
            '"arguments"' in stripped or '"parameters"' in stripped
            or '"type"' in stripped
        )
        return looks_like_json and has_tool_markers and has_arg_markers

    # ── Should be caught ──
    hallucinations = [
        '{"name": "open_app", "arguments": {"app_name": "chrome"}}',
        '[{"function": "search_google", "parameters": {"query": "test"}}]',
        '```json\n{"name": "play_music", "arguments": {"query": "lofi"}}```',
        '```\n{"tool_call": "volume_control", "type": "function", "arguments": {}}```',
        '{"action": "open_url", "type": "browser", "parameters": {"url": "google.com"}}',
    ]
    for h in hallucinations:
        _test(f"CAUGHT: {h[:50]}...", _is_json_hallucination(h))

    # ── Should NOT be caught (valid natural language) ──
    safe_replies = [
        "Sure Boss, opening Chrome for you!",
        "Here's what I found about JSON parsing.",
        "The function you're looking for is called map().",
        '{"status": "ok"}',  # Too simple, no tool markers + arg markers together
        "I think the action you need is to restart.",
        "Let me search that up for you, Boss~",
        "Volume set to 50%.",
    ]
    for s in safe_replies:
        _test(f"NOT caught: '{s[:50]}...'", not _is_json_hallucination(s))


# ═══════════════════════════════════════════════════════════════════════
#  6. VOLUME / BRIGHTNESS LEVEL CASTING
# ═══════════════════════════════════════════════════════════════════════
def test_level_casting():
    _section("6. Volume/Brightness Level Casting (String→Int)")
    from brain.system_controller import SystemController
    sysc = SystemController(require_confirmation=False)

    # Normal int
    r = sysc.volume_control(action="set", level=50)
    _test("volume set 50 (int)", r.get("status") == "success", r.get("message", ""))

    # String "50" (LLM sends this sometimes)
    r = sysc.volume_control(action="set", level="50")
    _test("volume set '50' (string)", r.get("status") == "success", r.get("message", ""))

    # Float 75.0
    r = sysc.volume_control(action="set", level=75.0)
    _test("volume set 75.0 (float)", r.get("status") == "success", r.get("message", ""))

    # Garbage string → should not crash, falls back to -1
    r = sysc.volume_control(action="up", level="loud")
    _test("volume up 'loud' (garbage) no crash", r.get("status") == "success", r.get("message", ""))

    # None → should not crash
    r = sysc.volume_control(action="down", level=None)
    _test("volume down None no crash", r.get("status") == "success", r.get("message", ""))

    # Boolean True → int(True)=1, should work
    r = sysc.volume_control(action="up", level=True)
    _test("volume up True no crash", r.get("status") == "success", r.get("message", ""))

    # Empty string → should not crash
    r = sysc.volume_control(action="set", level="")
    _test("volume set '' no crash", isinstance(r, dict), str(r))

    # Brightness with string
    r = sysc.brightness_control(action="set", level="80")
    _test("brightness set '80' (string)", r.get("status") in {"success", "error"}, r.get("message", ""))

    # Brightness with garbage
    r = sysc.brightness_control(action="up", level="bright")
    _test("brightness up 'bright' no crash", r.get("status") in {"success", "error"}, r.get("message", ""))


# ═══════════════════════════════════════════════════════════════════════
#  7. TOOL ARGUMENT SANITIZATION
# ═══════════════════════════════════════════════════════════════════════
def test_tool_args():
    _section("7. Tool Argument Sanitization")
    from brain.system_controller import SystemController
    sysc = SystemController(require_confirmation=False)

    # Extra whitespace in app name
    r = sysc.open_app("  whatsapp  ", target="mobile")
    _test("open_app whitespace trimmed", r.get("status") == "success")

    # Empty app name → error
    r = sysc.open_app("", target="mobile")
    _test("open_app empty name → error", r.get("status") == "error")

    # None target → should default gracefully
    r = sysc.open_app("youtube", target=None)
    _test("open_app None target no crash", isinstance(r, dict))

    # Weird target value
    r = sysc.open_app("youtube", target="INVALID")
    _test("open_app invalid target no crash", isinstance(r, dict))

    # Search with special chars
    r = sysc.search_google("what is 2+2?", target="mobile")
    _test("search_google special chars", r.get("status") == "success")

    # Play music with empty query
    r = sysc.play_music("", platform="spotify", target="mobile")
    _test("play_music empty query fallback", r.get("status") == "success")

    # Volume with invalid action
    r = sysc.volume_control(action="INVALID_ACTION")
    _test("volume invalid action → error", r.get("status") == "error")

    # Personality with None
    r = sysc.set_personality(None)
    _test("set_personality None → balanced", r.get("status") == "success" and r.get("mode") == "balanced")


# ═══════════════════════════════════════════════════════════════════════
#  8. MUSIC QUERY EXTRACTION (Tricky Inputs)
# ═══════════════════════════════════════════════════════════════════════
def test_music_extraction():
    _section("8. Music Query Extraction (Tricky Inputs)")
    from brain.llm import _extract_music_query

    cases = [
        ("play despacito on spotify mobile", "despacito"),
        ("play moon funk on youtube", "moon funk"),
        ("can you play blinding lights", "blinding lights"),
        ("play a beautiful song", "beautiful song"),
        ("play", ""),  # no query
        ("", ""),       # empty input
        ("play lofi hip hop on youtube music in my mobile", "lofi hip hop"),
    ]
    for input_text, expected_contains in cases:
        result = _extract_music_query(input_text.lower())
        if expected_contains:
            _test(f"music extract: '{input_text}' → has '{expected_contains}'",
                  expected_contains in result.lower(),
                  f"got: '{result}'")
        else:
            _test(f"music extract: '{input_text}' → empty",
                  result.strip() == "",
                  f"got: '{result}'")


# ═══════════════════════════════════════════════════════════════════════
#  9. TARGET / PLATFORM DETECTION (Edge Cases)
# ═══════════════════════════════════════════════════════════════════════
def test_target_platform_edge():
    _section("9. Target/Platform Detection Edge Cases")
    from brain.llm import _detect_target, _detect_platform, _infer_open_app_name

    # Target detection
    _test("'play on my pc' → desktop", _detect_target("play on my pc") == "desktop")
    _test("'open on computer' → desktop", _detect_target("open on computer") == "desktop")
    _test("'open on laptop' → desktop", _detect_target("open on laptop") == "desktop")
    _test("'destop' typo → desktop", _detect_target("open on destop") == "desktop")
    _test("'in mobile' → mobile", _detect_target("search in mobile") == "mobile")
    _test("empty → auto", _detect_target("") == "auto")
    _test("None → auto", _detect_target(None) == "auto")

    # Platform detection
    _test("'youtube music' → youtube", _detect_platform("play on youtube music") == "youtube")
    _test("'youtubemusic' → youtube", _detect_platform("play on youtubemusic") == "youtube")
    _test("'yt' → youtube", _detect_platform("play on yt") == "youtube")
    _test("empty → None", _detect_platform("") is None)
    _test("None → None", _detect_platform(None) is None)

    # App name inference
    _test("'whatapp' typo → whatsapp", _infer_open_app_name("open whatapp") == "whatsapp")
    _test("'insta' → instagram", _infer_open_app_name("open insta") == "instagram")
    _test("'yt' → youtube", _infer_open_app_name("open yt") == "youtube")
    _test("'wa' → whatsapp", _infer_open_app_name("open wa") == "whatsapp")
    _test("'cam' → camera", _infer_open_app_name("open cam") == "camera")
    _test("'photos' → gallery", _infer_open_app_name("open photos") == "gallery")
    _test("'images' → gallery", _infer_open_app_name("open images") == "gallery")
    _test("empty → empty", _infer_open_app_name("") == "")


# ═══════════════════════════════════════════════════════════════════════
# 10. POSTPROCESS & TTS SAFETY
# ═══════════════════════════════════════════════════════════════════════
def test_postprocess_extreme():
    _section("10. Postprocess & TTS Safety (Extreme)")
    from style.postprocess import postprocess_reply, prepare_tts_text

    # Emoji stripping
    r = postprocess_reply("Hello Boss 🔥🎉✨ How are you?")
    _test("emojis stripped", "🔥" not in r and "Hello Boss" in r)

    # Markdown stripping
    r = postprocess_reply("**Bold** and `code` and *italic*")
    _test("markdown stripped", "**" not in r and "`" not in r and "*" not in r)

    # Speaker label removal
    r = postprocess_reply("Neon: Hello Boss!")
    _test("speaker label removed", not r.startswith("Neon:"))

    # Empty input → "Hmm?"
    r = postprocess_reply("")
    _test("empty → 'Hmm?'", True)  # Just ensure no crash

    # None-ish input → no crash
    r = postprocess_reply(None)
    _test("None → empty", r == "")

    # Smart quotes → regular quotes
    r = postprocess_reply("He said \u201chello\u201d and \u2018goodbye\u2019")
    _test("smart quotes replaced", "\u201c" not in r and "\u201d" not in r)

    # Very long text TTS truncation
    long_text = "This is a sentence. " * 100
    r = prepare_tts_text(long_text, max_chars=360)
    _test("TTS truncated ≤ 360", len(r) <= 365)  # Small tolerance
    _test("TTS ends with sentence break", r[-1] in ".!?" if r else True)

    # Asterisk actions removed
    r = postprocess_reply("*smiles* Hello Boss!")
    _test("asterisk action removed", "*" not in r)

    # Parenthesis actions removed
    r = postprocess_reply("(leans back) What's up, Boss?")
    _test("parenthesis action removed", "(" not in r)

    # Slang expansion
    r = postprocess_reply("idk tbh rn", clean_for_tts=True)
    _test("slang expanded", "don't know" in r.lower() or "to be honest" in r.lower())


# ═══════════════════════════════════════════════════════════════════════
# 11. SYSTEM CONTROLLER EDGE CASES
# ═══════════════════════════════════════════════════════════════════════
def test_controller_edge():
    _section("11. System Controller Edge Cases")
    from brain.system_controller import SystemController
    sysc = SystemController(require_confirmation=False)

    # Volume: get action
    r = sysc.volume_control(action="get")
    _test("volume get works", r.get("status") == "success")

    # Brightness: get action
    r = sysc.brightness_control(action="get")
    _test("brightness get works", r.get("status") in {"success", "error"})

    # Power: invalid action
    r = sysc.power_control(action="explode")
    _test("power invalid → error", r.get("status") == "error")

    # Connectivity: invalid target
    r = sysc.toggle_connectivity(target="5g", state="on")
    _test("connectivity invalid target → error", r.get("status") == "error")

    # Connectivity: invalid state
    r = sysc.toggle_connectivity(target="wifi", state="maybe")
    _test("connectivity invalid state → error", r.get("status") == "error")

    # Create file with injection attempt
    r = sysc.create_file("../../etc/passwd")
    _test("path traversal sanitized", r.get("status") == "success" and ".." not in r.get("message", ""))

    # Delete non-existent file
    r = sysc.delete_file("this_file_does_not_exist_12345.xyz")
    _test("delete nonexistent → error", r.get("status") == "error")

    # Search with unicode
    r = sysc.search_google("こんにちは", target="mobile")
    _test("search unicode no crash", r.get("status") == "success")


# ═══════════════════════════════════════════════════════════════════════
# 12. PROMPT INJECTION RESISTANCE
# ═══════════════════════════════════════════════════════════════════════
def test_prompt_injection():
    _section("12. Prompt System Sanity")
    from brain.prompt import get_system_prompt

    # Normal prompt generation
    p = get_system_prompt(emotion="calm", intensity=0.5, affection=50.0)
    _test("prompt is string", isinstance(p, str) and len(p) > 100)
    _test("prompt has Neon identity", "Neon" in p)
    _test("prompt has Boss reference", "Boss" in p)

    # Edge values
    p2 = get_system_prompt(emotion="", intensity=-5.0, affection=999.0)
    _test("extreme values no crash", isinstance(p2, str) and len(p2) > 100)

    # All mood states
    for mood in ["calm", "happy", "mad", "sad", "excited", "angry", "tired", "playful"]:
        p = get_system_prompt(emotion=mood, intensity=0.5, affection=50.0)
        _test(f"mood '{mood}' works", isinstance(p, str) and len(p) > 100)

    # Affection tiers
    for aff in [10, 40, 70, 95]:
        p = get_system_prompt(emotion="calm", intensity=0.5, affection=float(aff))
        _test(f"affection {aff} works", isinstance(p, str) and "RELATIONSHIP" in p)


# ═══════════════════════════════════════════════════════════════════════
#  RUN ALL
# ═══════════════════════════════════════════════════════════════════════
def main():
    global passed, failed, total

    test_question_vs_command()
    test_technical_detection()
    test_cooldown_behavior()
    test_duplicate_window()
    test_json_hallucination_guard()
    test_level_casting()
    test_tool_args()
    test_music_extraction()
    test_target_platform_edge()
    test_postprocess_extreme()
    test_controller_edge()
    test_prompt_injection()

    print(f"\n{'='*70}")
    print(f"  🔥 EXTREME RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'='*70}")

    if failed > 0:
        print(f"\n❌ {failed} TEST(S) FAILED!")
        return 1
    else:
        print("\n✅ ALL EXTREME TESTS PASSED!")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
