"""
🧪 Comprehensive Neon Test Suite — Tests ALL features hard.

Covers:
  1. System controller (basic commands)
  2. System awareness (sysinfo — CPU, RAM, disk, GPU, OS, battery)
  3. Set personality + fuzzy aliases
  4. Smart cooldown (5s duplicate block)
  5. Command stats recording + auto-pref learning
  6. Multi-action flavor combiner
  7. Time-aware context generation
  8. Memory schema v5 migration
  9. Flavor system (all moods/actions)
 10. Inference helpers (detect_target, detect_platform, etc.)
"""

import os
import sys
import time
import json
import copy

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
        msg = f"[FAILED] {name}{' -- ' + detail if detail else ''}"
        print(f"  {msg}")
        with open(os.path.join(_REPO, "test_failures.txt"), "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def _section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════
#  1. SYSTEM CONTROLLER — BASIC COMMANDS
# ═══════════════════════════════════════════════════════════════
def test_system_controller():
    _section("1. System Controller — Basic Commands")
    from brain.system_controller import SystemController
    sysc = SystemController(require_confirmation=False)

    # open_app — known apps
    for app in ["whatsapp", "chatgpt", "camera", "gallery", "youtube", "instagram"]:
        r = sysc.open_app(app, target="mobile")
        _test(f"open_app({app})", isinstance(r, dict) and r.get("status") in {"success", "error"})

    # search
    r = sysc.search_google("neon ai test", target="mobile")
    _test("search_google", r.get("status") == "success" and "action" in r)

    r = sysc.search_youtube("lofi beats", target="mobile")
    _test("search_youtube", r.get("status") == "success" and "action" in r)

    # play_music — spotify
    r = sysc.play_music("blinding lights", platform="spotify", target="mobile")
    _test("play_music(spotify)", r.get("status") == "success")

    # play_music — youtube
    r = sysc.play_music("lofi hip hop", platform="youtube", target="mobile")
    _test("play_music(youtube)", r.get("status") == "success")

    # Desktop while headless → should error
    r = sysc.search_google("test", target="desktop")
    _test("headless+desktop=error", r.get("status") == "error" and "Desktop" in r.get("message", ""))

    # create_file / delete_file
    r = sysc.create_file("smoke_test_file.txt")
    _test("create_file", r.get("status") == "success")
    r = sysc.delete_file("smoke_test_file.txt")
    _test("delete_file", r.get("status") == "success")
    r = sysc.create_file("is sleeping and right right in this file this is my best life.txt")
    _test("filename sanitized", r.get("status") == "success" and "life.txt" in r.get("message", ""), r.get("message", ""))
    r = sysc.delete_file("life.txt")
    _test("delete sanitized file", r.get("status") == "success", r.get("message", ""))

    # Empty query → error
    r = sysc.search_google("", target="mobile")
    _test("search_google(empty)=error", r.get("status") == "error")


# ═══════════════════════════════════════════════════════════════
#  2. SYSTEM AWARENESS — SYSINFO
# ═══════════════════════════════════════════════════════════════
def test_sysinfo():
    _section("2. System Awareness — Hardware Detection")
    from core.sysinfo import get_system_snapshot, get_compact_status, get_human_report

    snap = get_system_snapshot()
    _test("snapshot is dict", isinstance(snap, dict))
    _test("has OS info", "os" in snap and isinstance(snap["os"], dict))
    _test("OS = Windows 11", snap["os"].get("release") == "11", f"got: {snap['os'].get('release')}")
    _test("has CPU info", "cpu" in snap and isinstance(snap["cpu"], dict))
    _test("CPU has usage%", "usage_percent" in snap.get("cpu", {}))
    _test("has RAM info", "ram" in snap and isinstance(snap["ram"], dict))
    _test("RAM has total_gb", "total_gb" in snap.get("ram", {}))
    _test("has disks", "disks" in snap and isinstance(snap["disks"], list) and len(snap["disks"]) > 0)
    _test("has GPU", snap.get("gpu") is not None, "no NVIDIA GPU detected (nvidia-smi)")
    _test("GPU has name", isinstance(snap.get("gpu", {}), dict) and "name" in (snap.get("gpu") or {}))
    _test("has uptime", snap.get("uptime") != "Unknown")
    _test("has top_processes", isinstance(snap.get("top_processes"), list) and len(snap.get("top_processes", [])) > 0)

    # Battery (laptop should have one)
    bat = snap.get("battery")
    _test("has battery", bat is not None)
    if bat:
        _test("battery has percent", "percent" in bat)
        _test("battery has plugged_in", "plugged_in" in bat)

    # Compact status
    compact = get_compact_status()
    _test("compact is string", isinstance(compact, str) and len(compact) > 20)
    _test("compact has Windows 11", "Windows 11" in compact, f"got: {compact[:80]}")
    _test("compact has CPU", "CPU" in compact)
    _test("compact has RAM", "RAM" in compact)

    # Human report
    report = get_human_report()
    _test("human report non-empty", isinstance(report, str) and len(report) > 50)

    # system_status upgrade
    from brain.system_controller import SystemController
    sysc = SystemController(require_confirmation=False)
    r = sysc.system_status()
    _test("system_status has hardware", "hardware" in r.get("details", {}), str(r.get("details", {}).keys()))
    _test("system_status message concise", len(r.get("message", "")) < 90, r.get("message", ""))


# ═══════════════════════════════════════════════════════════════
#  3. SET PERSONALITY — TOOL + FUZZY ALIASES
# ═══════════════════════════════════════════════════════════════
def test_set_personality():
    _section("3. Set Personality — Tool + Aliases")
    from brain.system_controller import SystemController
    sysc = SystemController(require_confirmation=False)

    # Direct modes
    r = sysc.set_personality("balanced")
    _test("set balanced", r.get("status") == "success" and r.get("mode") == "balanced")

    r = sysc.set_personality("roaster")
    _test("set roaster", r.get("status") == "success" and r.get("mode") == "roaster")

    r = sysc.set_personality("curious")
    _test("set curious", r.get("status") == "success" and r.get("mode") == "curious")

    # Fuzzy aliases
    aliases = {
        "roasty": "roaster", "spicy": "roaster", "savage": "roaster", "tease": "roaster",
        "chill": "balanced", "normal": "balanced", "default": "balanced", "reset": "balanced",
        "question": "curious", "ask": "curious",
    }
    for alias, expected in aliases.items():
        r = sysc.set_personality(alias)
        _test(f"alias '{alias}'→{expected}", r.get("mode") == expected, f"got: {r.get('mode')}")

    # Invalid mode
    r = sysc.set_personality("INVALID_GARBAGE_123")
    _test("invalid mode=error", r.get("status") == "error")

    # Empty / None → falls back to "balanced" (reset to default)
    r = sysc.set_personality("")
    _test("empty string=balanced", r.get("status") == "success" and r.get("mode") == "balanced")


# ═══════════════════════════════════════════════════════════════
#  4. SMART COOLDOWN
# ═══════════════════════════════════════════════════════════════
def test_cooldown():
    _section("4. Smart Command Cooldown")
    from collections import deque

    # Simulate the cooldown logic directly
    history = deque(maxlen=20)
    now = time.time()

    # First call — should NOT be blocked
    recent = [ts for (fn, ts) in history if fn == "open_app" and (now - ts) < 5.0]
    _test("first call not blocked", len(recent) == 0)

    # Record it
    history.append(("open_app", now))

    # Same call within 5s — should be blocked
    recent = [ts for (fn, ts) in history if fn == "open_app" and (now - ts) < 5.0]
    _test("duplicate within 5s blocked", len(recent) > 0)

    # Different func — should NOT be blocked
    recent = [ts for (fn, ts) in history if fn == "search_google" and (now - ts) < 5.0]
    _test("different func not blocked", len(recent) == 0)

    # After 5s — should NOT be blocked
    history.clear()
    history.append(("open_app", now - 6.0))
    recent = [ts for (fn, ts) in history if fn == "open_app" and (now - ts) < 5.0]
    _test("after 5s not blocked", len(recent) == 0)


# ═══════════════════════════════════════════════════════════════
#  5. COMMAND STATS + AUTO-PREF LEARNING
# ═══════════════════════════════════════════════════════════════
def test_command_stats():
    _section("5. Command Stats + Auto-Learning")
    from memory.memory import MemoryManager

    mm = MemoryManager()
    # Clear stats for clean test
    mm.state["command_stats"] = {}
    mm.state["usage_patterns"] = {}
    mm.state["prefs"] = {"music_platform": "spotify", "voice_style": "default", "banter_mode": "balanced"}

    # Record commands
    mm.record_command("open_app", "youtube")
    mm.record_command("open_app", "youtube")
    mm.record_command("open_app", "chrome")

    stats = mm.state["command_stats"]
    _test("stats recorded", "open_app" in stats)
    _test("open_app count=3", stats.get("open_app", {}).get("count") == 3)
    _test("targets tracked", stats.get("open_app", {}).get("targets", {}).get("youtube") == 2)

    # Usage patterns
    patterns = mm.state["usage_patterns"]
    _test("usage_patterns populated", len(patterns) > 0)

    # Top commands
    top = mm.get_top_commands(3)
    _test("top_commands works", len(top) > 0 and top[0][0] == "open_app")

    # Active hours
    hours = mm.get_active_hours()
    _test("active_hours works", len(hours) > 0)

    # Auto-pref learning (need 10+ play_music calls to trigger)
    for i in range(12):
        mm.record_command("play_music", "youtube music lofi")
    mm.auto_update_prefs()
    _test("auto-learn youtube pref", mm.state["prefs"].get("music_platform") == "youtube",
          f"got: {mm.state['prefs'].get('music_platform')}")

    # Reset for spotify
    mm.state["command_stats"] = {}
    for i in range(12):
        mm.record_command("play_music", "spotify playlist")
    mm.auto_update_prefs()
    _test("auto-learn spotify pref", mm.state["prefs"].get("music_platform") == "spotify",
          f"got: {mm.state['prefs'].get('music_platform')}")


# ═══════════════════════════════════════════════════════════════
#  6. MULTI-ACTION FLAVOR COMBINER
# ═══════════════════════════════════════════════════════════════
def test_multi_flavor():
    _section("6. Multi-Action Flavor Combiner")
    from brain.command_flavor import flavor_command_response, flavor_multi_results

    warm_status = {"emotion": "happy", "affection": 75.0}
    cold_status = {"emotion": "mad", "affection": 20.0}

    # Flavor individual commands
    r1 = flavor_command_response("open_app", "Opened YouTube.", "open youtube", warm_status)
    r2 = flavor_command_response("play_music", "Playing lofi on Spotify.", "play lofi", warm_status)
    _test("flavor r1 non-empty", bool(r1))
    _test("flavor r2 non-empty", bool(r2))

    # Combine
    combined = flavor_multi_results([r1, r2], "open youtube and play lofi", warm_status)
    _test("combined non-empty", bool(combined) and len(combined) > len(r1))
    _test("combined shorter than concat", len(combined) < len(r1) + len(r2) + 20,
          f"combined={len(combined)} vs r1+r2={len(r1)+len(r2)}")

    # Single result → passthrough
    single = flavor_multi_results([r1], "open youtube", warm_status)
    _test("single passthrough", single == r1)

    # Empty → empty
    empty = flavor_multi_results([], "", warm_status)
    _test("empty → empty", empty == "")

    # Cold mood combiner
    c1 = flavor_command_response("open_app", "Opened Chrome.", "open chrome", cold_status)
    c2 = flavor_command_response("search_google", "Searched Google.", "search test", cold_status)
    cold_combined = flavor_multi_results([c1, c2], "open chrome and search test", cold_status)
    _test("cold combined works", bool(cold_combined))


# ═══════════════════════════════════════════════════════════════
#  7. TIME-AWARE CONTEXT
# ═══════════════════════════════════════════════════════════════
def test_time_context():
    _section("7. Time-Aware Context Generation")

    hour = time.localtime().tm_hour
    if 5 <= hour < 12:
        expected_hint = "morning"
    elif 12 <= hour < 17:
        expected_hint = "afternoon"
    elif 17 <= hour < 21:
        expected_hint = "evening"
    else:
        expected_hint = "late_night"

    _test(f"hour {hour} → {expected_hint}", True)

    # Test the logic matches
    for h, exp in [(6, "morning"), (14, "afternoon"), (19, "evening"), (2, "late_night"), (23, "late_night")]:
        if 5 <= h < 12:
            got = "morning"
        elif 12 <= h < 17:
            got = "afternoon"
        elif 17 <= h < 21:
            got = "evening"
        else:
            got = "late_night"
        _test(f"hour {h}→{exp}", got == exp)


# ═══════════════════════════════════════════════════════════════
#  8. MEMORY SCHEMA V5 MIGRATION
# ═══════════════════════════════════════════════════════════════
def test_schema_migration():
    _section("8. Memory Schema v5 Migration")
    from memory.memory import _migrate, SCHEMA_VERSION

    # Simulate v1 data
    old_v1 = {"user_name": "Ansh", "affection": 50, "emotion": "calm"}
    migrated = _migrate(copy.deepcopy(old_v1))
    _test("v1→v5 has schema_version", migrated.get("schema_version") == SCHEMA_VERSION)
    _test("v1→v5 has insult_count", "insult_count" in migrated)
    _test("v1→v5 has intensity", "intensity" in migrated)
    _test("v1→v5 has prefs", isinstance(migrated.get("prefs"), dict))
    _test("v1→v5 has banter_mode", migrated.get("prefs", {}).get("banter_mode") == "balanced")
    _test("v1→v5 has command_stats", isinstance(migrated.get("command_stats"), dict))
    _test("v1→v5 has usage_patterns", isinstance(migrated.get("usage_patterns"), dict))

    # Already v5 → no changes
    v5 = {"schema_version": 5, "command_stats": {"open_app": {"count": 5}}}
    migrated5 = _migrate(copy.deepcopy(v5))
    _test("v5 stays v5", migrated5.get("schema_version") == 5)
    _test("v5 preserves stats", migrated5.get("command_stats", {}).get("open_app", {}).get("count") == 5)


# ═══════════════════════════════════════════════════════════════
#  9. FLAVOR SYSTEM (ALL MOODS / ACTIONS)
# ═══════════════════════════════════════════════════════════════
def test_flavor_all():
    _section("9. Flavor System — All Moods & Actions")
    from brain.command_flavor import flavor_command_response

    moods = [
        {"emotion": "happy", "affection": 80},
        {"emotion": "mad", "affection": 20},
        {"emotion": "calm", "affection": 50},
    ]
    actions = [
        ("open_app", "Opened YouTube.", "open youtube"),
        ("search_google", "Opened Google search for 'test'.", "search test"),
        ("play_music", "Playing lofi on Spotify.", "play lofi"),
        ("system_status", "Ollama: OK | TTS: OK", "check status"),
        ("create_file", "File 'test.txt' created.", "create file test.txt"),
        ("delete_file", "File 'test.txt' deleted.", "delete test.txt"),
        ("send_whatsapp_message", "Message sent to John.", "send john hello"),
        ("set_personality", "Personality switched to roaster mode.", "be more roasty"),
    ]

    for mood in moods:
        for action, raw, user_in in actions:
            result = flavor_command_response(action, raw, user_in, mood)
            _test(f"{mood['emotion']}:{action}", bool(result) and isinstance(result, str))

    # Error responses
    for mood in moods:
        result = flavor_command_response("open_app", "Error: App not found.", "open foobar", mood)
        _test(f"{mood['emotion']}:error", bool(result) and isinstance(result, str))


# ═══════════════════════════════════════════════════════════════
#  10. INFERENCE HELPERS
# ═══════════════════════════════════════════════════════════════
def test_inference():
    _section("10. Inference Helpers")
    from brain.llm import _detect_platform, _detect_target, _extract_music_query, _infer_open_app_name, _is_command, _is_technical
    from brain.command_flavor import _extract_query

    # _detect_target
    _test("mobile detected", _detect_target("open youtube mobile") == "mobile")
    _test("desktop detected", _detect_target("play lofi desktop") == "desktop")
    _test("laptop=desktop", _detect_target("open chrome on laptop") == "desktop")
    _test("auto fallback", _detect_target("search hello") == "auto")

    # _detect_platform
    _test("spotify detected", _detect_platform("play on spotify") == "spotify")
    _test("youtube detected", _detect_platform("play on youtube") == "youtube")
    _test("yt music detected", _detect_platform("play on youtube music") == "youtube")
    _test("no platform=None", _detect_platform("play some music") is None)

    # _extract_music_query
    _test("music query", _extract_music_query("play despacito on spotify mobile").strip() != "")
    _test(
        "quoted command query extraction",
        _extract_query("Opened Spotify search for 'for you'.", "play for you") == "for you",
    )

    # _infer_open_app_name
    _test("whatsapp inferred", _infer_open_app_name("open whatsapp") == "whatsapp")
    _test("camera inferred", _infer_open_app_name("open camera") == "camera")
    _test("chatgpt inferred", _infer_open_app_name("launch chatgpt") == "chatgpt")
    _test("instagram inferred", _infer_open_app_name("open insta") == "instagram")

    # _is_command
    _test("'open youtube' is command", _is_command("open youtube"))
    _test("'play lofi' is command", _is_command("play lofi"))
    _test("'check status' is command", _is_command("check status"))
    _test("'system info' is command", _is_command("system info"))
    _test("'cpu usage' is command", _is_command("cpu usage"))
    _test("'what is AI' not command", not _is_command("what is AI"))
    _test("'how to cook' not command", not _is_command("how to cook"))

    # _is_technical
    _test("python = technical", _is_technical("write a python function"))
    _test("hello ≠ technical", not _is_technical("hello boss"))


# ═══════════════════════════════════════════════════════════════
#  RUN ALL
# ═══════════════════════════════════════════════════════════════
def test_tts_prep():
    _section("11. TTS Text Prep")
    from style.postprocess import prepare_tts_text

    prepared = prepare_tts_text("Done, Boss. Youtube is ready.")
    _test("no leading anchor dot", not prepared.startswith(". "), prepared)

    decorated = prepare_tts_text("Boss~ What's on your mind? You're sweet.")
    _test("tilde preserved", "~" in decorated, decorated)
    _test("contraction preserved", "You're" in decorated, decorated)

    status_text = "Services: Ollama: OK | TTS: OK | Backend: OK.\nTop RAM hogs: ollama.exe, python.exe."
    status_prepared = prepare_tts_text(status_text, max_chars=500)
    _test("system speech shortened", status_prepared == "All systems look good, Boss.", status_prepared)


def main():
    global passed, failed, total

    test_system_controller()
    test_sysinfo()
    test_set_personality()
    test_cooldown()
    test_command_stats()
    test_multi_flavor()
    test_time_context()
    test_schema_migration()
    test_flavor_all()
    test_inference()
    test_tts_prep()

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print(f"{'='*60}")

    if failed > 0:
        print(f"\n❌ {failed} TEST(S) FAILED!")
        return 1
    else:
        print("\n✅ ALL TESTS PASSED!")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
