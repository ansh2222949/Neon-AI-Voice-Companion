import os
import sys
from typing import Any, Dict, Optional


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _add_repo_to_path() -> None:
    root = _repo_root()
    if root not in sys.path:
        sys.path.insert(0, root)


def _assert_dict(x: Any, *, name: str) -> Dict[str, Any]:
    if not isinstance(x, dict):
        raise AssertionError(f"{name} expected dict, got {type(x).__name__}: {x!r}")
    return x


def _assert_has(d: Dict[str, Any], key: str, *, name: str) -> None:
    if key not in d:
        raise AssertionError(f"{name} missing key '{key}': {d!r}")


def _assert_action_open_url(d: Dict[str, Any], *, name: str) -> None:
    action = d.get("action")
    if not isinstance(action, dict):
        raise AssertionError(f"{name} expected action dict, got: {action!r}")
    if action.get("type") != "open_url":
        raise AssertionError(f"{name} expected action.type=='open_url', got: {action!r}")
    url = action.get("url")
    if not isinstance(url, str) or not url.strip():
        raise AssertionError(f"{name} expected non-empty action.url, got: {action!r}")


def _assert_headless_desktop_error(d: Dict[str, Any], *, name: str) -> None:
    # Headless + desktop should be blocked with a friendly error message.
    if d.get("status") != "error":
        raise AssertionError(f"{name} expected status=='error' in headless desktop, got: {d!r}")
    msg = str(d.get("message") or "")
    if "Desktop requested" not in msg:
        raise AssertionError(f"{name} expected desktop/headless warning message, got: {msg!r}")


def _safe_print_result(name: str, d: Dict[str, Any]) -> None:
    status = d.get("status")
    message = d.get("message")
    action = d.get("action")
    print(f"[SMOKE] {name}: status={status!r} message={str(message)[:120]!r} action={action!r}")


def main() -> int:
    _add_repo_to_path()

    # Force headless mode to simulate the mobile/backend environment.
    os.environ["NEON_HEADLESS"] = "1"

    from brain.system_controller import SystemController  # noqa: E402
    from brain.llm import _detect_platform, _detect_target, _extract_music_query, _infer_open_app_name  # noqa: E402

    sysc = SystemController(require_confirmation=False)

    # --- Tool method smoke tests (direct calls) ---
    tests: list[tuple[str, Dict[str, Any]]] = []

    # open_app (mobile / headless) should return open_url action for known keys
    tests.append(("open_app_mobile_whatsapp", _assert_dict(sysc.open_app("whatsapp", target="mobile"), name="open_app_mobile_whatsapp")))
    tests.append(("open_app_mobile_chatgpt", _assert_dict(sysc.open_app("chatgpt", target="mobile"), name="open_app_mobile_chatgpt")))
    tests.append(("open_app_mobile_camera", _assert_dict(sysc.open_app("camera", target="mobile"), name="open_app_mobile_camera")))
    tests.append(("open_app_mobile_gallery", _assert_dict(sysc.open_app("gallery", target="mobile"), name="open_app_mobile_gallery")))

    # search_* (mobile / headless) should return open_url action with query
    tests.append(("search_google_mobile", _assert_dict(sysc.search_google("neon ai", target="mobile"), name="search_google_mobile")))
    tests.append(("search_youtube_mobile", _assert_dict(sysc.search_youtube("lofi beats", target="mobile"), name="search_youtube_mobile")))

    # play_music (mobile / headless) should return open_url action
    tests.append(("play_music_mobile_spotify", _assert_dict(sysc.play_music("blinding lights", platform="spotify", autoplay=True, target="mobile"), name="play_music_mobile_spotify")))

    # Desktop requests while headless should error (for actions that would open desktop browser)
    tests.append(("search_google_desktop_headless", _assert_dict(sysc.search_google("test", target="desktop"), name="search_google_desktop_headless")))
    tests.append(("search_youtube_desktop_headless", _assert_dict(sysc.search_youtube("test", target="desktop"), name="search_youtube_desktop_headless")))
    tests.append(("play_music_desktop_headless", _assert_dict(sysc.play_music("test", platform="spotify", autoplay=True, target="desktop"), name="play_music_desktop_headless")))
    tests.append(("open_app_desktop_headless", _assert_dict(sysc.open_app("chrome", target="desktop"), name="open_app_desktop_headless")))

    # system_status should return a dict (service state may vary; don't assert healthy)
    tests.append(("system_status", _assert_dict(sysc.system_status(), name="system_status")))

    # Assertions
    for name, d in tests:
        _assert_has(d, "status", name=name)
        _assert_has(d, "message", name=name)
        if name.endswith("_desktop_headless"):
            _assert_headless_desktop_error(d, name=name)
        if name in {
            "open_app_mobile_whatsapp",
            "open_app_mobile_chatgpt",
            "search_google_mobile",
            "search_youtube_mobile",
            "play_music_mobile_spotify",
        }:
            _assert_action_open_url(d, name=name)
        # camera/gallery are special action types (not open_url)
        if name in {"open_app_mobile_camera", "open_app_mobile_gallery"}:
            action = d.get("action")
            if not isinstance(action, dict) or action.get("type") not in {"open_camera", "open_gallery"}:
                raise AssertionError(f"{name} expected open_camera/open_gallery action, got: {action!r}")

        _safe_print_result(name, d)

    # --- Inference helper smoke tests (pure functions) ---
    samples = [
        "play despacito on spotify mobile",
        "open whatapp mobile",
        "open whatsapp desktop",
        "play lofi on youtube music",
        "open camera mobile",
    ]
    for s in samples:
        ul = s.lower()
        inferred = {
            "text": s,
            "target": _detect_target(ul),
            "platform": _detect_platform(ul),
            "music_query": _extract_music_query(ul),
            "app_name": _infer_open_app_name(ul),
        }
        # Don't hard-fail on content here; just ensure no exceptions and types are sane.
        if inferred["target"] not in {"auto", "mobile", "desktop"}:
            raise AssertionError(f"inferred target invalid for {s!r}: {inferred!r}")
        if inferred["platform"] is not None and not isinstance(inferred["platform"], str):
            raise AssertionError(f"inferred platform invalid for {s!r}: {inferred!r}")
        if inferred["music_query"] is not None and not isinstance(inferred["music_query"], str):
            raise AssertionError(f"inferred music_query invalid for {s!r}: {inferred!r}")
        if inferred["app_name"] is not None and not isinstance(inferred["app_name"], str):
            raise AssertionError(f"inferred app_name invalid for {s!r}: {inferred!r}")
        print(f"[SMOKE] inference: {inferred}")

    print("[SMOKE] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

