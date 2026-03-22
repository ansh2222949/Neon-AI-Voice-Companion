import os

with open(r"D:\neon\brain\system_controller.py", "r", encoding="utf-8") as f:
    content = f.read()

old_pm1 = """                    if top_url:
                        if (not headless) and (not mobile_target):
                            webbrowser.open(top_url)
                        return {
                            "status": "success",
                            "message": f"Playing top YouTube result for '{q}'.",
                            "action": {"type": "open_url", "url": top_url},
                            "risk": self.RISK_LEVELS[action],
                        }"""

new_pm1 = """                    if top_url:
                        resp = {
                            "status": "success",
                            "message": f"Playing top YouTube result for '{q}'.",
                            "risk": self.RISK_LEVELS[action],
                        }
                        if headless or mobile_target:
                            resp["action"] = {"type": "open_url", "url": top_url}
                        else:
                            webbrowser.open(top_url)
                        return resp"""

old_pm2 = """                url = "https://music.youtube.com/search?q=" + quote_plus(q)
                if (not headless) and (not mobile_target):
                    webbrowser.open(url)
                return {
                    "status": "success",
                    "message": f"Opened YouTube Music search for '{q}'.",
                    "action": {"type": "open_url", "url": url},
                    "risk": self.RISK_LEVELS[action],
                }"""

new_pm2 = """                url = "https://music.youtube.com/search?q=" + quote_plus(q)
                resp = {
                    "status": "success",
                    "message": f"Opened YouTube Music search for '{q}'.",
                    "risk": self.RISK_LEVELS[action],
                }
                if headless or mobile_target:
                    resp["action"] = {"type": "open_url", "url": url}
                else:
                    webbrowser.open(url)
                return resp"""

old_pm3 = """            url = "https://music.youtube.com"
            if (not headless) and (not mobile_target):
                webbrowser.open(url)
            return {"status": "success", "message": "Opened YouTube Music.", "action": {"type": "open_url", "url": url}, "risk": self.RISK_LEVELS[action]}"""

new_pm3 = """            url = "https://music.youtube.com"
            resp = {"status": "success", "message": "Opened YouTube Music.", "risk": self.RISK_LEVELS[action]}
            if headless or mobile_target:
                resp["action"] = {"type": "open_url", "url": url}
            else:
                webbrowser.open(url)
            return resp"""

old_pm4 = """        if q:
            url = "https://open.spotify.com/search/" + quote_plus(q)
            if (not headless) and (not mobile_target):
                webbrowser.open(url)
            return {"status": "success", "message": f"Opened Spotify search for '{q}'.", "action": {"type": "open_url", "url": url}, "risk": self.RISK_LEVELS[action]}"""

new_pm4 = """        if q:
            url = "https://open.spotify.com/search/" + quote_plus(q)
            resp = {"status": "success", "message": f"Opened Spotify search for '{q}'.", "risk": self.RISK_LEVELS[action]}
            if headless or mobile_target:
                resp["action"] = {"type": "open_url", "url": url}
            else:
                webbrowser.open(url)
            return resp"""

old_pm5 = """        url = "https://open.spotify.com"
        if (not headless) and (not mobile_target):
            webbrowser.open(url)
        return {"status": "success", "message": "Opened Spotify.", "action": {"type": "open_url", "url": url}, "risk": self.RISK_LEVELS[action]}"""

new_pm5 = """        url = "https://open.spotify.com"
        resp = {"status": "success", "message": "Opened Spotify.", "risk": self.RISK_LEVELS[action]}
        if headless or mobile_target:
            resp["action"] = {"type": "open_url", "url": url}
        else:
            webbrowser.open(url)
        return resp"""

content = content.replace(old_pm1, new_pm1)
content = content.replace(old_pm2, new_pm2)
content = content.replace(old_pm3, new_pm3)
content = content.replace(old_pm4, new_pm4)
content = content.replace(old_pm5, new_pm5)

with open(r"D:\neon\brain\system_controller.py", "w", encoding="utf-8", newline="") as f:
    f.write(content)
print("DONE")
