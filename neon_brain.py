from brain.llm import NeonBrain

brain = NeonBrain()  # single persistent brain

def think_and_reply(prompt: str, target: str = "auto"):
    if not prompt or not prompt.strip():
        return {
            "reply": "",
            "mode": brain.engine.status.get("emotion", "calm")
        }

    try:
        reply = brain.chat(prompt, target=target)
        return {
            "reply": reply or "",
            "mode": brain.engine.status.get("emotion", "calm"),
            "action": getattr(brain, "last_action", None),
        }
    except Exception:
        return {
            "reply": "Something went wrong. Give me a second, Boss.",
            "mode": "error",
            "action": None,
        }
