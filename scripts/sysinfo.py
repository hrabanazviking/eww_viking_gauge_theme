#!/usr/bin/env python3
"""Emit a single JSON object with all the data eww needs for the gungnir widget."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

# === per-CPU usage (8 physical cores) =========================================
def cpu_percentages(cores: int = 8) -> tuple[list[float], float]:
    """Return per-core % + overall avg. Uses /proc/stat snapshot with cached prev."""
    cache = Path("/tmp/eww-cpu-prev.json")
    def snapshot() -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("cpu") and line[3:4].isdigit():
                    parts = line.split()
                    out[parts[0]] = [int(x) for x in parts[1:]]
        return out

    prev = json.loads(cache.read_text()) if cache.exists() else {}
    cur = snapshot()
    cache.write_text(json.dumps(cur))

    per: list[float] = []
    for i in range(cores):
        key = f"cpu{i}"
        if key in prev and key in cur:
            p = prev[key]; c = cur[key]
            d_total = sum(c) - sum(p)
            d_idle = (c[3] + c[4]) - (p[3] + p[4])
            pct = (100.0 * (d_total - d_idle) / d_total) if d_total > 0 else 0
        else:
            pct = 0
        per.append(round(pct, 1))
    avg = round(sum(per) / len(per), 1) if per else 0
    return per, avg


# === Memory ===================================================================
def memory_info() -> dict[str, float]:
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, _, rest = line.partition(":")
            info[k.strip()] = int(rest.strip().split()[0])  # kB
    total_kb = info["MemTotal"]
    available_kb = info["MemAvailable"]
    used_kb = total_kb - available_kb
    swap_total_kb = info["SwapTotal"]
    swap_free_kb = info["SwapFree"]
    swap_used_kb = swap_total_kb - swap_free_kb
    return {
        "ram_used_gb": round(used_kb / 1024 / 1024, 1),
        "ram_total_gb": round(total_kb / 1024 / 1024, 1),
        "ram_pct": round(100 * used_kb / total_kb, 1) if total_kb else 0,
        "swap_used_gb": round(swap_used_kb / 1024 / 1024, 1),
        "swap_total_gb": round(swap_total_kb / 1024 / 1024, 1),
        "swap_pct": round(100 * swap_used_kb / swap_total_kb, 1) if swap_total_kb else 0,
    }


# === Disk =====================================================================
def disk_info() -> dict[str, float]:
    s = os.statvfs("/")
    total = s.f_blocks * s.f_frsize
    avail = s.f_bavail * s.f_frsize
    used = total - avail
    return {
        "disk_used_gb": round(used / 1024**3, 1),
        "disk_total_gb": round(total / 1024**3, 1),
        "disk_pct": round(100 * used / total, 1) if total else 0,
    }


# === CPU frequency + temp =====================================================
def cpu_freq_temp() -> tuple[float, float]:
    # average current freq across all cpuN (in MHz)
    freqs = []
    for p in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_cur_freq"):
        try:
            freqs.append(int(p.read_text()) / 1000)  # kHz → MHz
        except Exception:
            pass
    freq = round(sum(freqs) / len(freqs)) if freqs else 0

    temp = 0.0
    if shutil.which("sensors"):
        try:
            r = subprocess.run(["sensors"], capture_output=True, text=True, timeout=2)
            m = re.search(r"Tctl:\s*\+?(\d+\.?\d*)°C", r.stdout)
            if m:
                temp = float(m.group(1))
        except Exception:
            pass
    return freq, temp


# === Uptime ===================================================================
def uptime_short() -> str:
    with open("/proc/uptime") as f:
        secs = int(float(f.read().split()[0]))
    h, rem = divmod(secs, 3600)
    m, _ = divmod(rem, 60)
    d, h = divmod(h, 24)
    if d > 0:
        return f"{d}d {h:02d}h {m:02d}m"
    return f"{h:02d}h {m:02d}m"


# === Top processes ============================================================
def top_processes(by: str, n: int = 5) -> list[dict]:
    sort_key = "-%cpu" if by == "cpu" else "-%mem"
    try:
        r = subprocess.run(
            ["ps", "-eo", f"comm,{('%cpu' if by == 'cpu' else '%mem')}", "--sort", sort_key, "--no-headers"],
            capture_output=True, text=True, timeout=2,
        )
        out = []
        for line in r.stdout.splitlines()[:n]:
            parts = line.rsplit(maxsplit=1)
            if len(parts) == 2:
                name = parts[0].strip()[:18]
                try:
                    pct = float(parts[1])
                except ValueError:
                    pct = 0.0
                out.append({"name": name, "pct": pct})
        return out
    except Exception:
        return []


# === Assemble =================================================================
per, avg = cpu_percentages()
data = {
    "cpu": per,
    "cpu_avg": avg,
}
freq, temp = cpu_freq_temp()
data["freq_mhz"] = freq
data["temp_c"] = temp
data["uptime"] = uptime_short()
data.update(memory_info())
data.update(disk_info())
data["top_cpu"] = top_processes("cpu")
data["top_ram"] = top_processes("ram")
print(json.dumps(data))
