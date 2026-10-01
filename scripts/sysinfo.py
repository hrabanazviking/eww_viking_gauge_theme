#!/usr/bin/env python3
"""Emit a single JSON object with all the data eww needs for the gungnir widget."""
from __future__ import annotations

import json
import logging
import tempfile
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

log = logging.getLogger("eww.sysinfo")
PROC_ROOT = Path(os.getenv("EWW_PROC_ROOT", "/proc"))
CACHE_ROOT = Path(os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "eww-viking"


def _atomic_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(data, stream)
    temporary.replace(path)


# === per-CPU usage (8 physical cores) =========================================
def cpu_percentages(cores: int = 8) -> tuple[list[float], float]:
    """Return per-core % + overall avg. Uses /proc/stat snapshot with cached prev."""
    cache = CACHE_ROOT / "cpu-prev.json"
    def snapshot() -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        with (PROC_ROOT / "stat").open() as f:
            for line in f:
                if line.startswith("cpu") and line[3:4].isdigit():
                    parts = line.split()
                    out[parts[0]] = [int(x) for x in parts[1:]]
        return out

    try:
        prev = json.loads(cache.read_text())
        if not isinstance(prev, dict):
            prev = {}
    except (OSError, ValueError):
        prev = {}
    cur = snapshot()
    try:
        _atomic_cache(cache, cur)
    except OSError as exc:
        log.warning("CPU cache unavailable: %s", exc)

    per: list[float] = []
    for i in range(cores):
        key = f"cpu{i}"
        if key in prev and key in cur and isinstance(prev[key], list) and len(prev[key]) >= 5 and all(isinstance(v, int) for v in prev[key]):
            p = prev[key]; c = cur[key]
            d_total = sum(c) - sum(p)
            d_idle = (c[3] + c[4]) - (p[3] + p[4])
            pct = (100.0 * (d_total - d_idle) / d_total) if d_total > 0 else 0
        else:
            pct = 0
        per.append(round(max(0, min(100, pct)), 1))
    avg = round(sum(per) / len(per), 1) if per else 0
    return per, avg


# === Memory ===================================================================
def memory_info() -> dict[str, float]:
    info = {}
    with (PROC_ROOT / "meminfo").open() as f:
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
    with (PROC_ROOT / "uptime").open() as f:
        secs = int(float(f.read().split()[0]))
    h, rem = divmod(secs, 3600)
    m, _ = divmod(rem, 60)
    d, h = divmod(h, 24)
    if d > 0:
        return f"{d}d {h:02d}h {m:02d}m"
    return f"{h:02d}h {m:02d}m"


# === GPU (nvidia-smi) =========================================================
def gpu_info() -> dict:
    """Return GPU stats via nvidia-smi. Empty/zero values if unavailable."""
    fallback = {
        "gpu_available": False, "gpu_name": "no gpu",
        "gpu_util_pct": 0, "gpu_vram_used_gb": 0, "gpu_vram_total_gb": 0,
        "gpu_vram_pct": 0, "gpu_temp_c": 0, "gpu_power_w": 0,
    }
    if not shutil.which("nvidia-smi"):
        return fallback
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,utilization.gpu,memory.used,memory.total,"
             "temperature.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return fallback
        line = r.stdout.strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            return fallback
        def _n(s, t=float, d=0):
            try:
                value = t(s)
                return value if math.isfinite(value) else d
            except (ValueError, TypeError):
                return d
        name = re.sub(r"NVIDIA\s+GeForce\s+", "", parts[0])
        name = re.sub(r"\s+with\s+Max-Q\s+Design", " Max-Q", name)
        util = _n(parts[1], int)
        mem_used = _n(parts[2], float)
        mem_total = _n(parts[3], float)
        temp = _n(parts[4], int)
        power = _n(parts[5], float)
        return {
            "gpu_available": True,
            "gpu_name": name,
            "gpu_util_pct": util,
            "gpu_vram_used_gb": round(mem_used / 1024, 1),
            "gpu_vram_total_gb": round(mem_total / 1024, 1),
            "gpu_vram_pct": round(100 * mem_used / mem_total, 1) if mem_total else 0,
            "gpu_temp_c": temp,
            "gpu_power_w": round(power),
        }
    except Exception:
        return fallback


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
def collect() -> dict:
    defaults = Path(__file__).with_name("sysinfo.defaults.json")
    data = json.loads(defaults.read_text())
    for collector in (memory_info, disk_info, gpu_info):
        try:
            data.update(collector())
        except Exception as exc:
            log.warning("%s unavailable: %s", getattr(collector, "__name__", "metric"), exc)
    try:
        data["cpu"], data["cpu_avg"] = cpu_percentages(cores=len(data["cpu"]))
    except Exception as exc:
        log.warning("CPU usage unavailable: %s", exc)
    try:
        data["freq_mhz"], data["temp_c"] = cpu_freq_temp()
        data["uptime"] = uptime_short()
    except Exception as exc:
        log.warning("CPU metadata unavailable: %s", exc)
    for kind in ("cpu", "ram"):
        rows = top_processes(kind)
        data["top_" + kind] = (rows + data["top_" + kind])[0:len(data["top_" + kind])]
    return data


if __name__ == "__main__":
    print(json.dumps(collect(), allow_nan=False))
