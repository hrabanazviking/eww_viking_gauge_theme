# Desktop metric collector

This folder owns the Linux JSON collector and its complete fallback data shape.
It has no database, model-control or credential-management responsibility.

- `sysinfo.py`: read CPU, memory, disk, sensors, process and optional NVIDIA metrics.
- `sysinfo.defaults.json`: paired field/slot defaults; install beside the collector.

Read [the technical manual](../TECHNICAL_MANUAL.md) before changing polling,
configured CPU/process slots or installation paths. Keep the defaults JSON,
`eww.yuck` initial data and widget indexes consistent. Preserve complete output
on individual metric failures; keep diagnostics separate from JSON stdout.
CPU delta history is disposable XDG cache, not second-brain source knowledge.
