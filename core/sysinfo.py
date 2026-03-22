"""
Neon System Awareness — Live hardware & OS info for self-aware responses.

Gathers CPU, RAM, disk, GPU, battery, OS, uptime, and top processes
so Neon can comment on Boss's system status naturally.

Usage:
    from core.sysinfo import get_system_snapshot, get_compact_status
"""

import os
import platform
import time
from typing import Dict, Any, Optional

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


# ─────────────────────────────────────────────────────────────────────────────
# 🖥️  SYSTEM SNAPSHOT — full hardware + OS report
# ─────────────────────────────────────────────────────────────────────────────

def get_system_snapshot() -> Dict[str, Any]:
    """Gathers a comprehensive system snapshot."""
    info: Dict[str, Any] = {}

    # ── OS INFO ──────────────────────────────────────────────────────────────
    os_release = platform.release()
    os_version = platform.version()
    # Fix: Python's platform.release() returns "10" on Windows 11.
    # Windows 11 has build number >= 22000.
    if platform.system() == "Windows" and os_release == "10":
        try:
            build = int(os_version.split(".")[-1]) if os_version else 0
            if build >= 22000:
                os_release = "11"
        except (ValueError, IndexError):
            pass

    info["os"] = {
        "system": platform.system(),
        "release": os_release,
        "version": os_version,
        "machine": platform.machine(),
        "hostname": platform.node(),
    }

    # ── CPU ───────────────────────────────────────────────────────────────────
    info["cpu"] = {
        "processor": platform.processor() or "Unknown",
        "cores_physical": os.cpu_count(),
    }
    if _PSUTIL:
        try:
            info["cpu"]["usage_percent"] = psutil.cpu_percent(interval=None)
            info["cpu"]["cores_logical"] = psutil.cpu_count(logical=True)
            info["cpu"]["freq_mhz"] = round(psutil.cpu_freq().current, 0) if psutil.cpu_freq() else None
        except Exception:
            pass

    # ── RAM ───────────────────────────────────────────────────────────────────
    if _PSUTIL:
        try:
            mem = psutil.virtual_memory()
            info["ram"] = {
                "total_gb": round(mem.total / (1024**3), 1),
                "used_gb": round(mem.used / (1024**3), 1),
                "available_gb": round(mem.available / (1024**3), 1),
                "usage_percent": mem.percent,
            }
        except Exception:
            info["ram"] = {"error": "Could not read RAM info"}
    else:
        info["ram"] = {"error": "psutil not installed"}

    # ── DISK ──────────────────────────────────────────────────────────────────
    if _PSUTIL:
        try:
            disks = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append({
                        "drive": part.mountpoint,
                        "total_gb": round(usage.total / (1024**3), 1),
                        "free_gb": round(usage.free / (1024**3), 1),
                        "usage_percent": usage.percent,
                    })
                except (PermissionError, OSError):
                    continue
            info["disks"] = disks
        except Exception:
            info["disks"] = []
    else:
        info["disks"] = []

    # ── GPU (NVIDIA via nvidia-smi) ───────────────────────────────────────────
    info["gpu"] = _get_gpu_info()

    # ── BATTERY ───────────────────────────────────────────────────────────────
    if _PSUTIL:
        try:
            bat = psutil.sensors_battery()
            if bat:
                info["battery"] = {
                    "percent": bat.percent,
                    "plugged_in": bat.power_plugged,
                    "time_left_mins": round(bat.secsleft / 60) if bat.secsleft > 0 else None,
                }
            else:
                info["battery"] = None  # Desktop, no battery
        except Exception:
            info["battery"] = None
    else:
        info["battery"] = None

    # ── UPTIME ────────────────────────────────────────────────────────────────
    if _PSUTIL:
        try:
            boot = psutil.boot_time()
            uptime_s = time.time() - boot
            hours = int(uptime_s // 3600)
            mins = int((uptime_s % 3600) // 60)
            info["uptime"] = f"{hours}h {mins}m"
        except Exception:
            info["uptime"] = "Unknown"
    else:
        info["uptime"] = "Unknown"

    # ── TOP PROCESSES (by memory) ─────────────────────────────────────────────
    if _PSUTIL:
        try:
            procs = []
            for p in psutil.process_iter(["name", "memory_percent", "cpu_percent"]):
                try:
                    pi = p.info
                    if pi.get("memory_percent") and pi["memory_percent"] > 1.0:
                        procs.append({
                            "name": pi["name"],
                            "ram_pct": round(pi["memory_percent"], 1),
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            procs.sort(key=lambda x: x["ram_pct"], reverse=True)
            info["top_processes"] = procs[:5]
        except Exception:
            info["top_processes"] = []
    else:
        info["top_processes"] = []

    return info


def _get_gpu_info() -> Optional[Dict[str, Any]]:
    """Try to get NVIDIA GPU info via nvidia-smi."""
    import subprocess
    import shutil
    if not shutil.which("nvidia-smi"):
        return None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 6:
            return {
                "name": parts[0],
                "vram_total_mb": int(parts[1]),
                "vram_used_mb": int(parts[2]),
                "vram_free_mb": int(parts[3]),
                "gpu_usage_percent": int(parts[4]),
                "temp_c": int(parts[5]),
            }
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 📋  COMPACT STATUS — one-liner for system prompt injection
# ─────────────────────────────────────────────────────────────────────────────

def get_compact_status() -> str:
    """Returns a compact one-line system status for injecting into prompts."""
    snap = get_system_snapshot()
    parts = []

    # OS
    os_info = snap.get("os", {})
    parts.append(f"OS: {os_info.get('system', '?')} {os_info.get('release', '')}")

    # CPU
    cpu = snap.get("cpu", {})
    cpu_usage = cpu.get("usage_percent")
    if cpu_usage is not None:
        parts.append(f"CPU: {cpu_usage}%")

    # RAM
    ram = snap.get("ram", {})
    if "usage_percent" in ram:
        parts.append(f"RAM: {ram['used_gb']}/{ram['total_gb']}GB ({ram['usage_percent']}%)")

    # GPU
    gpu = snap.get("gpu")
    if gpu:
        parts.append(f"GPU: {gpu['name']} {gpu['vram_used_mb']}/{gpu['vram_total_mb']}MB {gpu['temp_c']}°C")

    # Disk (main drive only)
    disks = snap.get("disks", [])
    if disks:
        d = disks[0]
        parts.append(f"Disk: {d['free_gb']}GB free ({d['usage_percent']}% used)")

    # Battery
    bat = snap.get("battery")
    if bat:
        plug = "⚡" if bat.get("plugged_in") else "🔋"
        parts.append(f"Battery: {bat['percent']}% {plug}")

    # Uptime
    uptime = snap.get("uptime")
    if uptime and uptime != "Unknown":
        parts.append(f"Uptime: {uptime}")

    return " | ".join(parts)


def get_human_report() -> str:
    """Returns a detailed multi-line system report for voice output."""
    snap = get_system_snapshot()
    lines = []

    # OS
    os_info = snap.get("os", {})
    lines.append(f"Running {os_info.get('system', 'Unknown')} {os_info.get('release', '')} on {os_info.get('hostname', 'this machine')}.")

    # CPU
    cpu = snap.get("cpu", {})
    proc = cpu.get("processor", "Unknown CPU")
    cores = cpu.get("cores_logical") or cpu.get("cores_physical") or "?"
    usage = cpu.get("usage_percent")
    freq = cpu.get("freq_mhz")
    cpu_line = f"CPU: {proc}, {cores} cores"
    if freq:
        cpu_line += f" at {int(freq)} MHz"
    if usage is not None:
        cpu_line += f", currently at {usage}%"
    lines.append(cpu_line + ".")

    # RAM
    ram = snap.get("ram", {})
    if "total_gb" in ram:
        lines.append(f"RAM: {ram['used_gb']}GB used out of {ram['total_gb']}GB ({ram['usage_percent']}% full).")

    # GPU
    gpu = snap.get("gpu")
    if gpu:
        lines.append(
            f"GPU: {gpu['name']}, VRAM {gpu['vram_used_mb']}MB/{gpu['vram_total_mb']}MB, "
            f"usage {gpu['gpu_usage_percent']}%, temp {gpu['temp_c']}°C."
        )

    # Disks
    disks = snap.get("disks", [])
    for d in disks[:3]:
        lines.append(f"Drive {d['drive']}: {d['free_gb']}GB free of {d['total_gb']}GB ({d['usage_percent']}% used).")

    # Battery
    bat = snap.get("battery")
    if bat:
        plug = "plugged in" if bat.get("plugged_in") else "on battery"
        time_left = f", ~{bat['time_left_mins']} minutes left" if bat.get("time_left_mins") else ""
        lines.append(f"Battery: {bat['percent']}%, {plug}{time_left}.")

    # Uptime
    uptime = snap.get("uptime")
    if uptime and uptime != "Unknown":
        lines.append(f"System uptime: {uptime}.")

    # Top processes
    procs = snap.get("top_processes", [])
    if procs:
        proc_names = ", ".join(
            f"{os.path.splitext(p['name'])[0]} ({p['ram_pct']}%)"
            for p in procs[:3]
        )
        lines.append(f"Top RAM hogs: {proc_names}.")

    return " ".join(lines)
