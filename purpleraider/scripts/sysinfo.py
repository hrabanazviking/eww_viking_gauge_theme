#!/usr/bin/env python3
"""Emit a single JSON object with all the data eww needs for the gungnir widget.

purpleraider variant (ROG Flow Z13 · Kubuntu 26.10): 16 physical Zen 5 cores
(SMT siblings averaged from topology), amdgpu sysfs GPU (Radeon 8060S),
vault disk gauge, hardware temperatures, live network throughput, XDNA 2
NPU presence. Adapted from the purplelongship original.
"""
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
SYS_CPU_ROOT = Path("/sys/devices/system/cpu")
HWMON_ROOT = Path("/sys/class/hwmon")
DRM_ROOT = Path("/sys/class/drm")
CACHE_ROOT = Path(os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "eww-viking"


def _atomic_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(data, stream)
    temporary.replace(path)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def _read_int(path: Path) -> int | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


# === per-CPU usage (16 physical cores, SMT siblings averaged) ================
def _core_groups(cpu_names: list[str]) -> list[list[str]]:
    """Group logical cpu names by physical core via sysfs topology.

    Falls back to one group per logical CPU if topology is unreadable.
    """
    groups: dict[str, list[str]] = {}
    ok = True
    for name in cpu_names:
        core_id = _read_text(SYS_CPU_ROOT / name / "topology" / "core_id")
        if core_id is None:
            ok = False
            break
        groups.setdefault(core_id, []).append(name)
    if not ok or not groups:
        return [[name] for name in sorted(cpu_names, key=lambda n: int(n[3:]))]

    def sort_key(item: tuple[str, list[str]]) -> tuple[int, int]:
        core_id, members = item
        first_cpu = min(int(n[3:]) for n in members)
        return (int(core_id) if core_id.isdigit() else 1 << 30, first_cpu)

    return [members for _, members in sorted(groups.items(), key=sort_key)]


def cpu_percentages(cores: int = 16) -> tuple[list[float], float]:
    """Return per-physical-core % + overall avg. /proc/stat snapshot + cached prev."""
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

    def usable(entry) -> bool:
        return isinstance(entry, list) and len(entry) >= 5 and all(isinstance(v, int) for v in entry)

    def pct_of(key: str, p: dict, c: dict) -> float:
        if key in p and key in c and usable(p[key]) and usable(c[key]):
            pv = p[key]; cv = c[key]
            d_total = sum(cv) - sum(pv)
            d_idle = (cv[3] + cv[4]) - (pv[3] + pv[4])
            return (100.0 * (d_total - d_idle) / d_total) if d_total > 0 else 0.0
        return 0.0

    cur = snapshot()
    try:
        _atomic_cache(cache, cur)
    except OSError as exc:
        log.warning("CPU cache unavailable: %s", exc)

    logical = {name: pct_of(name, prev, cur) for name in cur}
    per: list[float] = []
    for members in _core_groups(sorted(logical, key=lambda n: int(n[3:]))):
        vals = [logical[m] for m in members if m in logical]
        if vals:
            per.append(round(max(0.0, min(100.0, sum(vals) / len(vals))), 1))
    if len(per) > cores:
        per = per[:cores]
    while len(per) < cores:
        per.append(0)
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
def _statvfs_gb(path: str) -> tuple[float, float, float]:
    s = os.statvfs(path)
    total = s.f_blocks * s.f_frsize
    avail = s.f_bavail * s.f_frsize
    used = total - avail
    return (
        round(used / 1024**3, 1),
        round(total / 1024**3, 1),
        round(100 * used / total, 1) if total else 0,
    )


def disk_info() -> dict[str, float]:
    used, total, pct = _statvfs_gb("/")
    return {"disk_used_gb": used, "disk_total_gb": total, "disk_pct": pct}


def vault_info() -> dict[str, float]:
    try:
        used, total, pct = _statvfs_gb("/mnt/vault")
    except OSError:
        return {"vault_used_gb": 0, "vault_total_gb": 1, "vault_pct": 0}
    return {"vault_used_gb": used, "vault_total_gb": total, "vault_pct": pct}


# === hwmon helpers ============================================================
def _hwmon_by_name(wanted: str) -> Path | None:
    for hw in sorted(HWMON_ROOT.glob("hwmon*")):
        if _read_text(hw / "name") == wanted:
            return hw
    return None


def _hwmon_temp_c(hw: Path | None, sensor: str = "temp1_input") -> float:
    """hwmon temps are millidegrees C; return whole degrees, 0 when missing."""
    if hw is None:
        return 0
    milli = _read_int(hw / sensor)
    return round(milli / 1000) if milli is not None else 0


def _cpu_temp_c() -> float:
    """k10temp temp1_input is Tctl on Zen parts."""
    return _hwmon_temp_c(_hwmon_by_name("k10temp"))


def temperature_info() -> dict[str, float]:
    """Flat temperature keys: GPU junction + the two NVMe drives."""
    junction = 0
    card = _amd_card()
    if card is not None:
        hw = _card_hwmon(card)
        if hw is not None and (hw / "temp2_input").exists():
            junction = _hwmon_temp_c(hw, "temp2_input")

    ssd_int = 0
    ssd_vault = 0
    for hw in sorted(HWMON_ROOT.glob("hwmon*")):
        if _read_text(hw / "name") != "nvme":
            continue
        try:
            resolved = os.path.realpath(hw / "device")
        except OSError:
            continue
        m = re.search(r"/nvme(\d+)(?:/|$)", resolved)
        if not m:
            continue
        if m.group(1) == "0":
            ssd_int = _hwmon_temp_c(hw)
        elif m.group(1) == "1":
            ssd_vault = _hwmon_temp_c(hw)
    return {
        "gpu_junction_c": junction,
        "ssd_int_temp_c": ssd_int,
        "ssd_vault_temp_c": ssd_vault,
    }


# === CPU frequency + temp =====================================================
def cpu_freq_temp() -> tuple[float, float]:
    # average current freq across all cpuN (in MHz)
    freqs = []
    for p in SYS_CPU_ROOT.glob("cpu[0-9]*/cpufreq/scaling_cur_freq"):
        try:
            freqs.append(int(p.read_text()) / 1000)  # kHz → MHz
        except Exception:
            pass
    freq = round(sum(freqs) / len(freqs)) if freqs else 0

    temp = _cpu_temp_c()
    if not temp and shutil.which("sensors"):
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


# === GPU (amdgpu sysfs — Radeon 8060S, unified memory) ========================
def _amd_card() -> Path | None:
    for card in sorted(DRM_ROOT.glob("card*")):
        if not re.fullmatch(r"card\d+", card.name):
            continue
        if _read_text(card / "device" / "vendor") == "0x1002":
            return card
    return None


def _card_hwmon(card: Path) -> Path | None:
    hw_root = card / "device" / "hwmon"
    if not hw_root.is_dir():
        return None
    for hw in sorted(hw_root.glob("hwmon*")):
        return hw
    return None


def gpu_info() -> dict:
    """GPU stats from amdgpu sysfs. VRAM keys carry the GTT (unified) pool."""
    fallback = {
        "gpu_available": False, "gpu_name": "no gpu",
        "gpu_util_pct": 0, "gpu_vram_used_gb": 0, "gpu_vram_total_gb": 0,
        "gpu_vram_pct": 0, "gpu_temp_c": 0, "gpu_power_w": 0,
    }
    card = _amd_card()
    if card is None:
        return fallback
    dev = card / "device"
    util = _read_int(dev / "gpu_busy_percent")
    gtt_used = _read_int(dev / "mem_info_gtt_used")
    gtt_total = _read_int(dev / "mem_info_gtt_total")
    if util is None and gtt_used is None and gtt_total is None:
        return fallback
    name = _read_text(dev / "product_name") or "AMD Radeon 8060S"
    temp = 0
    power = 0
    hw = _card_hwmon(card)
    if hw is not None:
        temp = _hwmon_temp_c(hw)
        micro_w = _read_int(hw / "power1_average")
        power = round(micro_w / 1_000_000) if micro_w is not None else 0
    used_b = gtt_used or 0
    total_b = gtt_total or 0
    return {
        "gpu_available": True,
        "gpu_name": name,
        "gpu_util_pct": util or 0,
        "gpu_vram_used_gb": round(used_b / 1024**3, 1),
        "gpu_vram_total_gb": round(total_b / 1024**3, 1),
        "gpu_vram_pct": round(100 * used_b / total_b, 1) if total_b else 0,
        "gpu_temp_c": temp,
        "gpu_power_w": power,
    }


# === Network (default-route iface, live throughput) ===========================
def _default_iface() -> str | None:
    try:
        lines = (PROC_ROOT / "net" / "route").read_text().splitlines()[1:]
        best: tuple[int, str] | None = None
        for line in lines:
            parts = line.split()
            if len(parts) >= 8 and parts[1] == "00000000":
                try:
                    metric = int(parts[6])
                except ValueError:
                    metric = 0
                if best is None or metric < best[0]:
                    best = (metric, parts[0])
        if best:
            return best[1]
    except OSError:
        pass
    try:
        r = subprocess.run(["ip", "route", "get", "1.1.1.1"],
                           capture_output=True, text=True, timeout=2)
        m = re.search(r"\bdev\s+(\S+)", r.stdout)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _fmt_rate(kbps: float) -> str:
    if kbps >= 1024:
        return f"{kbps / 1024:.2f} MB/s"
    if kbps >= 1:
        return f"{kbps:.1f} KB/s"
    if kbps > 0:
        return f"{kbps * 1024:.0f} B/s"
    return "0 KB/s"


def network_info() -> dict:
    out = {
        "net_iface": "-", "net_kind": "-", "net_ssid": "",
        "net_link_mbps": 0, "net_signal_pct": 0,
        "net_down_kbps": 0, "net_up_kbps": 0,
        "net_down_str": "0 KB/s", "net_up_str": "0 KB/s",
        "net_link_str": "—", "net_rx_gb": 0, "net_tx_gb": 0,
    }
    iface = _default_iface()
    if not iface:
        return out
    base = Path("/sys/class/net") / iface
    if not base.is_dir():
        return out
    out["net_iface"] = iface
    is_wifi = (base / "wireless").exists() or (base / "phy80211").exists()
    out["net_kind"] = "wifi" if is_wifi else "wired"

    if is_wifi and shutil.which("iw"):
        try:
            r = subprocess.run(["iw", "dev", iface, "link"],
                               capture_output=True, text=True, timeout=2)
            text = r.stdout
            m = re.search(r"SSID:\s*(.+)", text)
            if m:
                out["net_ssid"] = m.group(1).strip()
            m = re.search(r"tx bitrate:\s*([\d.]+)\s*MBit/s", text)
            if m:
                out["net_link_mbps"] = round(float(m.group(1)))
            m = re.search(r"signal:\s*(-?\d+)\s*dBm", text)
            if m:
                dbm = int(m.group(1))
                out["net_signal_pct"] = max(0, min(100, round((dbm + 90) / 60 * 100)))
        except Exception:
            pass
    if is_wifi and not out["net_ssid"] and shutil.which("nmcli"):
        try:
            r = subprocess.run(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
                               capture_output=True, text=True, timeout=2)
            for line in r.stdout.splitlines():
                if line.startswith("yes:"):
                    out["net_ssid"] = line.split(":", 1)[1]
                    break
        except Exception:
            pass
    if not is_wifi:
        speed = _read_int(base / "speed")
        if speed and speed > 0:
            out["net_link_mbps"] = speed
    if out["net_link_mbps"]:
        if is_wifi:
            out["net_link_str"] = f"{out['net_link_mbps']} Mb/s · SIG {out['net_signal_pct']}%"
        else:
            out["net_link_str"] = f"{out['net_link_mbps']} Mb/s"

    rx = _read_int(base / "statistics" / "rx_bytes")
    tx = _read_int(base / "statistics" / "tx_bytes")
    if rx is None or tx is None:
        return out
    out["net_rx_gb"] = round(rx / 1024**3, 1)
    out["net_tx_gb"] = round(tx / 1024**3, 1)

    cache = CACHE_ROOT / "net-prev.json"
    now = time.monotonic()
    prev = {}
    try:
        loaded = json.loads(cache.read_text())
        if isinstance(loaded, dict):
            prev = loaded
    except (OSError, ValueError):
        prev = {}
    try:
        _atomic_cache(cache, {"iface": iface, "rx": rx, "tx": tx, "t": now})
    except OSError as exc:
        log.warning("Net cache unavailable: %s", exc)
    if prev.get("iface") == iface and "rx" in prev and "tx" in prev and "t" in prev:
        dt = now - float(prev["t"])
        if dt > 0:
            down = max(0.0, (rx - int(prev["rx"])) / dt / 1024)
            up = max(0.0, (tx - int(prev["tx"])) / dt / 1024)
            out["net_down_kbps"] = round(down, 1)
            out["net_up_kbps"] = round(up, 1)
            out["net_down_str"] = _fmt_rate(down)
            out["net_up_str"] = _fmt_rate(up)
    return out


# === NPU (XDNA 2 presence only — no utilization source without XRT) ==========
def npu_info() -> dict:
    return {
        "npu_name": "AMD XDNA 2",
        "npu_present": os.path.exists("/dev/accel/accel0"),
    }


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
    for collector in (memory_info, disk_info, vault_info, gpu_info, network_info, npu_info):
        try:
            data.update(collector())
        except Exception as exc:
            log.warning("%s unavailable: %s", getattr(collector, "__name__", "metric"), exc)
    try:
        data.update(temperature_info())
    except Exception as exc:
        log.warning("Temperatures unavailable: %s", exc)
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
