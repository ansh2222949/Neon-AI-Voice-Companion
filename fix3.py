import os

with open(r"D:\neon\brain\system_controller.py", "r", encoding="utf-8") as f:
    content = f.read()

old_up = """            elif action == "up":
                if has_nircmd:
                    subprocess.run(["nircmd", "changesysvolume", "5000"], check=True)
                else:
                    subprocess.run(["powershell", "-c",
                        "(New-Object -ComObject WScript.Shell).SendKeys([char]175)"],
                        check=True, capture_output=True)
                return {"status": "success", "message": "Volume increased.", "risk": self.RISK_LEVELS[act]}"""

new_up = """            elif action == "up":
                step = int(level * 65535 / 100) if level > 0 else 5000
                if has_nircmd:
                    subprocess.run(["nircmd", "changesysvolume", str(step)], check=True)
                else:
                    loops = max(1, level // 2) if level > 0 else 1
                    subprocess.run(["powershell", "-c",
                        f"1..{loops} | % {{ (New-Object -ComObject WScript.Shell).SendKeys([char]175) }}"],
                        check=True, capture_output=True)
                msg = f"Volume increased by {level}%." if level > 0 else "Volume increased."
                return {"status": "success", "message": msg, "risk": self.RISK_LEVELS[act]}"""

old_down = """            elif action == "down":
                if has_nircmd:
                    subprocess.run(["nircmd", "changesysvolume", "-5000"], check=True)
                else:
                    subprocess.run(["powershell", "-c",
                        "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"],
                        check=True, capture_output=True)
                return {"status": "success", "message": "Volume decreased.", "risk": self.RISK_LEVELS[act]}"""

new_down = """            elif action == "down":
                step = int(level * 65535 / 100) if level > 0 else 5000
                if has_nircmd:
                    subprocess.run(["nircmd", "changesysvolume", str(-step)], check=True)
                else:
                    loops = max(1, level // 2) if level > 0 else 1
                    subprocess.run(["powershell", "-c",
                        f"1..{loops} | % {{ (New-Object -ComObject WScript.Shell).SendKeys([char]174) }}"],
                        check=True, capture_output=True)
                msg = f"Volume decreased by {level}%." if level > 0 else "Volume decreased."
                return {"status": "success", "message": msg, "risk": self.RISK_LEVELS[act]}"""

content = content.replace(old_up, new_up)
content = content.replace(old_down, new_down)

with open(r"D:\neon\brain\system_controller.py", "w", encoding="utf-8", newline="") as f:
    f.write(content)

print("DONE")
