# Viking desktop gauges technical manual

Verified against the theme and collector on 2026-10-01. This component displays
CPU, memory, root disk, process and NVIDIA statistics. It does not store knowledge,
manage the database or control AI permissions. Bifröst's browser GPU gauge is a
separate implementation.

## 1. Requirements and files

The installed configuration targets Linux/KDE Wayland with an eww build that
supports Wayland. It uses `/proc`, filesystem/sensor information and optional
`nvidia-smi`. It is not a cross-platform collector for Windows/macOS.

| File | Responsibility |
|---|---|
| `eww.yuck` | Widgets, two-second poll and `gungnir-gauges` window |
| `eww.scss` | Colors, spacing, fonts and visual style |
| `scripts/sysinfo.py` | Produce one complete JSON snapshot on stdout |
| `scripts/sysinfo.defaults.json` | Valid fallback fields/slots when a metric is unavailable |
| `tests/test_sysinfo.py` | Collector resilience regressions |

Install eww and the fonts for your distribution using the upstream
[eww documentation](https://github.com/elkowar/eww). The theme uses Hack and Junicode;
the latter gives appropriate rune metrics. A functioning NVIDIA module/userspace
driver is needed for real GPU statistics, but missing GPU information does not
prevent the remaining gauges from rendering.

## 2. Install or update the desktop copy

Preserve any custom eww configuration before copying these files over it. The
repository checkout and `~/.config/eww` are separate on this installation, so a
Git pull alone does not update the active desktop theme.

```bash
cd "$HOME/code/eww_viking_gauge_theme"
mkdir -p "$HOME/.config/eww/scripts"
cp eww.yuck eww.scss "$HOME/.config/eww/"
cp scripts/sysinfo.py scripts/sysinfo.defaults.json "$HOME/.config/eww/scripts/"
chmod +x "$HOME/.config/eww/scripts/sysinfo.py"
eww --config "$HOME/.config/eww" reload
eww --config "$HOME/.config/eww" open gungnir-gauges
```

Always copy the defaults JSON alongside the Python collector. The poll command
resolves `scripts/sysinfo.py` relative to eww's configuration directory. No database
or SMTP credentials belong in this folder.

## 3. Routine commands

```bash
eww --config "$HOME/.config/eww" ping
eww --config "$HOME/.config/eww" active-windows
eww --config "$HOME/.config/eww" open gungnir-gauges
eww --config "$HOME/.config/eww" close gungnir-gauges
eww --config "$HOME/.config/eww" reload
eww --config "$HOME/.config/eww" logs
eww --config "$HOME/.config/eww" inspector
```

`logs` is a live stream; stop it with Ctrl-C when finished. `inspector` is for GTK
layout debugging. These commands do not restart Bifröst, Ollama or PostgreSQL.

Test the data source independently:

```bash
python3 "$HOME/.config/eww/scripts/sysinfo.py" | python3 -m json.tool
nvidia-smi
```

The first snapshot may show zero CPU percentages because no prior sample exists;
the next poll computes a delta. Zero GPU utilization can mean an idle GPU; check
`gpu_available` and the name before calling it a driver failure.

## 4. What the values mean

| Section | Metrics and interpretation |
|---|---|
| CPU | First configured logical CPU indices from `/proc/stat`, plus frequency/temp/uptime |
| RAM / swap | Used/total and percentage; defaults remain structurally valid if collection fails |
| ROOT | Usage of the root filesystem, not all mounted drives |
| GPU | NVIDIA name, utilization, VRAM, temperature and power when available |
| Processes | Five CPU and five memory slots; unavailable entries are padded with defaults |

The shipped layout has eight CPU rings. They correspond to `cpu0` through `cpu7`,
not a guaranteed physical-core topology. `cpu_avg` averages the configured slots.
GPU availability refers to the collector's NVIDIA query, not proof that Ollama
offloaded a particular model. Check Ollama separately during actual work.

CPU history is an atomic cache under `$XDG_CACHE_HOME/eww-viking`, normally
`~/.cache/eww-viking/cpu-prev.json`. Corrupt/unreadable history resets to fresh
samples automatically. Missing metric collectors preserve valid defaults; the
defaults file itself must exist and remain valid JSON. This cache is disposable,
not a knowledge backup.

## 5. Customize for another machine

- **Name/runes/footer:** edit static labels in `eww.yuck`. These are visual labels,
  not automatic hostname discovery or an access-control setting.
- **Position/size:** edit the final `defwindow` geometry, monitor, anchor, x/y and width.
- **Colors/fonts:** edit variables/styles near the top of `eww.scss`.
- **CPU count:** adjust the `cpu` array in `sysinfo.defaults.json`, the initial JSON
  in `defpoll`, and the ring widgets together. The collector uses the defaults
  array length, so changing only one layer creates mismatched/missing slots.
- **Process slots:** keep array lengths and indexed rows consistent with the
  collector/default shape.
- **Spacing:** retain `:space-evenly false` on boxes that should use natural height.
  Otherwise eww can distribute empty vertical space between children.

Reload after editing the installed config. Test JSON before debugging CSS when
the entire widget is empty. A slower poll interval can reduce monitoring overhead;
it does not change model/database performance limits.

## 6. Startup and portability

The theme does not install a system service. Run `eww open gungnir-gauges` in your
desktop session, or use KDE/GNOME's application autostart configuration to start
eww from its full installed binary path. A `.desktop` Exec field is not a shell
unless you explicitly invoke one; do not assume `$HOME` expands there. The eww
daemon needs the correct graphical-session environment.

Back up `~/.config/eww`, any autostart entry and your source revision before moving
or replacing a customized installation. The CPU sample cache need not be restored.
Install the correct Wayland/X11 eww build and fonts for the target desktop;
changing hosts may require monitor/geometry edits and NVIDIA/sensor setup.

## 7. Troubleshooting and verification

| Symptom | First checks |
|---|---|
| eww command missing | Installed binary/path and correct desktop build |
| Window does not appear | `active-windows`, selected monitor/geometry and `logs` |
| Poll fails or fields are absent | Collector path and accompanying defaults JSON |
| CPU initially zero | Allow another two-second delta sample |
| GPU unavailable | `nvidia-smi`, loaded module and userspace driver version |
| GPU idle during model work | Intended Ollama server, model placement and `ollama ps` |
| Rune spacing wrong | Junicode installation/font selection and box spacing |
| Changes do not show | You edited the checkout but not the installed config, or forgot reload |

Driver repair belongs to the system, not the theme. Check kernel/userspace versions
and use distribution-supported packages; reboot after a driver/kernel update when
needed. See [Ubuntu's NVIDIA procedure](https://documentation.ubuntu.com/server/how-to/graphics/install-nvidia-drivers/)
and [Ollama GPU guidance](https://docs.ollama.com/gpu).

```bash
cd "$HOME/code/eww_viking_gauge_theme"
python3 -m unittest discover -s tests -v
python3 scripts/sysinfo.py | python3 -m json.tool
```

The first checks resilience; the second checks current metric output. Neither
changes source knowledge. For the rest of the system, see the
[second-brain manual](https://github.com/hrabanazviking/bifrost-viewer/blob/main/SECOND_BRAIN_MANUAL.md).
