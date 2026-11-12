# Gungnir Gauges — purpleraider variant

Device-specific build of the Cyber-Viking eww gauges for **purpleraider**
(ASUS ROG Flow Z13, Kubuntu 26.10, KDE Wayland). Same design, structure,
and runic language as the main (purplelongship) build — only the hardware
layer underneath was rebuilt for this machine.

## What was adapted

- **CPU** — 16 physical cores (Zen 5, 16C/32T). `sysinfo.py` groups the 32
  logical CPUs by physical core via sysfs topology and averages each SMT
  sibling pair; the widget shows four rows of four core rings.
- **GPU** — the NVIDIA/`nvidia-smi` reader was replaced with amdgpu sysfs
  for the Radeon 8060S (gfx1151): `gpu_busy_percent` for utilization,
  hwmon edge temperature and package power. The second ring is labelled
  POOL and reads `mem_info_gtt_*` — on this unified-memory machine the GTT
  pool *is* the graphics memory (60.8 GiB of the shared 128 GB).
- **Memory/storage** — four big rings: RAM, SWAP, ROOT, and VAULT (the
  4 TB external Btrfs drive at `/mnt/vault`).
- **Temperatures section** (ᛋ Sowilo) — CPU (k10temp Tctl), GPU edge,
  internal NVMe, and vault NVMe, all from hwmon. The GPU header line also
  shows junction temperature when the driver exposes `temp2_input`.
- **Network section** (ᚨ Ansuz) — default-route interface (Wi-Fi,
  MediaTek mt7925): SSID, negotiated link rate and signal strength from
  `iw`, plus live up/down throughput computed from
  `/sys/class/net/<iface>/statistics` deltas and since-boot totals.
- **NPU** — an honest nameplate under the GPU section: the AMD XDNA 2 at
  `/dev/accel/accel0` is reported present/absent. There is no utilization
  gauge — no honest source exists for it without the XRT userland.
- **Header / footer** — header title reads "PURPLERAIDER" with its
  Elder Futhark spelling beneath; footer reads "purpleraider ·
  kubuntu 26.10". Window is 314 px wide — the 330 px layout scaled to
  95% so the 4-across rings fit without the footer running off the
  bottom of the screen.

## Install

```sh
mkdir -p ~/.config/eww/scripts
cp purpleraider/eww.yuck purpleraider/eww.scss ~/.config/eww/
cp purpleraider/scripts/sysinfo.py purpleraider/scripts/sysinfo.defaults.json ~/.config/eww/scripts/
chmod +x ~/.config/eww/scripts/sysinfo.py
```

Needs the `eww` binary (0.6.0, copied from purplelongship's
`~/.local/bin/eww`) and the Hack + Junicode fonts. Autostart mirrors the
laptop's desktop entry:

```ini
[Desktop Entry]
Type=Application
Name=Eww — Gungnir Gauges (purpleraider)
Exec=bash -c 'sleep 5 && /home/volmarr/.local/bin/eww open gungnir-gauges'
```
