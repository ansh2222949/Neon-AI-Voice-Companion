import os

with open(r"D:\neon\brain\system_controller.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace search_google
old_sg = """        if query and query.strip():
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            if (not headless) and (not mobile_target):
                webbrowser.open(url)
            return {
                "status": "success",
                "message": f"Opened Google search for '{query}'.",
                "action": {"type": "open_url", "url": url},
                "risk": self.RISK_LEVELS[action],
            }"""

new_sg = """        if query and query.strip():
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
            return resp"""

content = content.replace(old_sg, new_sg)

# Replace search_youtube
old_sy = """        if query and query.strip():
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            if (not headless) and (not mobile_target):
                webbrowser.open(url)
            return {
                "status": "success",
                "message": f"Opened YouTube search for '{query}'.",
                "action": {"type": "open_url", "url": url},
                "risk": self.RISK_LEVELS[action],
            }"""

new_sy = """        if query and query.strip():
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
            return resp"""

content = content.replace(old_sy, new_sy)

with open(r"D:\neon\brain\system_controller.py", "w", encoding="utf-8", newline="") as f:
    f.write(content)
print("DONE")
