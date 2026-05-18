# Eww Viking Gauge Theme

Cyber-Viking system monitor for **eww** on Linux (KDE Wayland tested).
Ice-cyan + forge-bronze rings on a deep midnight panel, with runic section
markers and a runic spelling of the host machine's name. Designed for an
ASUS Zephyrus G14 (8-physical-core Ryzen) but easily adapted.

![preview](preview.png)

## About

This widget started as an attempt to recreate the iconic Twister-OS system
gauge on Linux Wayland. Conky — the tool the Twister-OS look was built on —
struggles under modern Wayland compositors because its whole "stick to the
desktop, transparent, always-at-bottom" magic depends on X11 concepts that
don't exist in Wayland. Rather than fight that, the design was rebuilt in
[eww](https://github.com/elkowar/eww), which is Wayland-native and gives you
full SCSS control over the look.

The aesthetic settled into something the original Conky theme could never
quite reach — a *cyber-Viking* take: angular runic glyphs as section markers
(Elder Futhark, drawn in [Junicode](https://junicode.sourceforge.io/) for
clean line metrics), ice-cyan for *live* data that glows softly, forge-bronze
for the *passive* labels that hold the structure together. The runes aren't
decoration — they're the section's identity:

| Rune | Name | Meaning | What it marks |
|---|---|---|---|
| ᚲ | Kenaz | torch / illumination | CPU cores — the thinking light |
| ᛗ | Mannaz | mankind / the mind | memory + storage — what is held |
| ᚦ | Thurisaz | giant / Thor | processes — the forces at work |
| ᛏ | Tiwaz | god of justice | footer — that which is right and known |

The widget's title text reads `GUNGNIR` (Odin's spear — the one that never
misses), with the runic spelling `ᚷᚢᛝᚾᛁᚱ` below. That's the hostname of the
laptop it was built on, and the natural place to swap to whatever name your
own machine wears. The decorative footer line `ᛏ · ᛟᚱᚦᛚᚨᚷ · ᛏ` is bracket-rune
+ "orthlag" (a stylized "long ship" reference) + bracket-rune, a small
flourish tying the widget back to its host. Replace it with anything that
feels right.

If you want it dialed quieter, drop the text-shadow blurs and turn `$cyan`
down toward white — it becomes a clean minimal monitor. If you want it
louder, raise the shadow blur and the `$bg` opacity; it leans more into the
"cyber" half of the brief.

A small note about the implementation, written into the SCSS as a comment:
eww's `box` widget defaults to `:space-evenly true`, which silently puffs
every child with vertical padding. **That property is the single most common
reason eww widgets look strangely loose** — every box in this config sets
`:space-evenly false` explicitly. Keep that rule and you'll save yourself a
debugging session.

## What you get

- **Header**: hostname rendered in Latin and Elder Futhark runes, with live
  CPU frequency, package temperature, and uptime
- **8 small ring gauges** — one per physical CPU core (live %)
- **3 big ring gauges** — RAM / Swap / Root-disk
- **Top-5 process lists** by CPU and by RAM, each with a runic bullet
- **Footer**: decorative runic line + host string

All values refresh every 2 seconds via a single Python data collector.

## Requirements

### eww
Install [eww](https://github.com/elkowar/eww) (build from source with the
`wayland` feature):

```bash
git clone https://github.com/elkowar/eww.git
cd eww && cargo build --release --no-default-features --features=wayland
cp target/release/eww ~/.local/bin/
```

Build deps on Debian/Ubuntu:

```bash
sudo apt install -y rustc cargo libgtk-3-dev libgtk-layer-shell-dev \
                    libpango1.0-dev librsvg2-dev libdbusmenu-gtk3-dev pkg-config
```

### Fonts
The widget uses **Hack** for the main monospace text and **Junicode** for the
runes (Junicode has tight, normal line metrics for Elder Futhark — Noto Sans
Runic has very tall ascenders and won't look right).

```bash
sudo apt install -y fonts-hack fonts-junicode fonts-firacode \
                    fonts-jetbrains-mono fonts-symbola
```

## Install

```bash
mkdir -p ~/.config/eww/scripts
cp eww.yuck ~/.config/eww/
cp eww.scss ~/.config/eww/
cp scripts/sysinfo.py ~/.config/eww/scripts/
chmod +x ~/.config/eww/scripts/sysinfo.py
```

Test launch:

```bash
eww open gungnir-gauges
```

Hide / reload / debug:

```bash
eww close gungnir-gauges
eww reload
eww inspector              # opens GTK Inspector for layout debugging
```

## Autostart with KDE / GNOME

Create `~/.config/autostart/eww-gauges.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Eww Viking Gauges
Exec=bash -c 'sleep 5 && /home/YOUR_USER/.local/bin/eww open gungnir-gauges'
Terminal=false
X-KDE-AutostartScript=true
X-GNOME-Autostart-enabled=true
```

## Adapting to your machine

Edit `eww.yuck`:

- **Number of CPU cores** — the included config wires 8 cores. If you have
  more/fewer physical cores, duplicate or remove `(ring :value {sys.cpu[N]} :label "...")`
  lines and update `cpu_percentages(cores=...)` in `scripts/sysinfo.py`.
- **Hostname** — replace `GUNGNIR` (Latin), `ᚷᚢᛝᚾᛁᚱ` (runic spelling), and
  the footer's `purplelongship · kubuntu 26.04` with your own.
- **Section runes** — `ᚲ` Kenaz for CPU, `ᛗ` Mannaz for memory, `ᚦ` Thurisaz
  for processes. Swap to whichever Elder Futhark glyphs fit your machine's
  identity.
- **Position / size** — bottom of `eww.yuck`, the `defwindow` block:
  - `:width "260px"` — overall widget width
  - `:x "30px"` — distance from the right edge (with `:anchor "top right"`)
  - `:y "48px"` — distance from the top
- **Colors** — top of `eww.scss`, the `$cyan` / `$bronze` / `$bg` SCSS vars
  control the entire palette.

## Why the layout works

A long-standing eww gotcha: the `box` widget defaults to `:space-evenly true`,
which distributes children across the box's full allocated height. On a
desktop-anchored widget that fills the right side of the screen, this puffs
every child with massive vertical padding ("3 blank lines under every text").

This config sets **`:space-evenly false` on every box**, which is the actual
fix — children take their natural height instead of being distributed. If
you fork this and add new boxes, keep that rule.

## License

MIT — see `LICENSE`.
