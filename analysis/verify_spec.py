"""Проверка параметров и экспорт схемы в SVG из исходника Mermaid."""
import json
import math
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT / "config/baseline.json").read_text(encoding="utf-8"))
assert cfg["horizon_hours"] == cfg["hours_per_day"] * 90
assert cfg["terminal_limit"] == 10_000
assert math.isclose(sum(cfg["route_probabilities"].values()), 1)
assert cfg["fraud_probability"] == .02 and cfg["pareto_shape"] > 2
assert cfg["target_kopecks_min"] <= cfg["target_kopecks_max"]
assert set(cfg["resources"]) == {f"R{i}" for i in range(1, 9)}
for capacity, queue, mean, price in cfg["resources"].values():
    assert capacity > 0 and queue >= 0 and mean > 0 and price > 0

source = (ROOT / "figures/platform.mmd").read_text(encoding="utf-8")
names = dict(re.findall(r'(\w+)\["([^"]+)"\]', source))
names.update(re.findall(r'(\w+)\(\[([^\]]+)\]\)', source))
names.update(re.findall(r'(\w+)\{"([^"]+)"\}', source))
edges = re.findall(r'(\w+)\s+(-->|-\.->)(?:\|([^|]+)\|)?\s+(\w+)', source)
positions = {
    "in": (5, 11), "R1": (5, 10), "R2": (3, 9), "R3": (8, 9),
    "rej": (11.6, 8), "R5a": (5, 7.8), "live": (5, 6.8),
    "R4": (3, 5.5), "R5b": (3, 4.2), "R6": (11.4, 5.5),
    "check": (6.5, 3.2), "R7": (10, 2), "R8": (5.2, 1.1),
    "refund": (10.8, .5), "paid": (5.2, 0),
}
assert set(names) == set(positions)
assert set(cfg["resources"]) <= {n.split()[0] for n in names.values()}
plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none",
                     "svg.hashsalt": "platform-flow"})
fig, ax = plt.subplots(figsize=(15, 12))
fig.subplots_adjust(left=.03, right=.97, top=.94, bottom=.04)
ax.set(xlim=(0, 14), ylim=(-.5, 11.6))
ax.axis("off")
ax.set_title("Платформа краудфандинга · ресурсы, очереди и исходы",
             fontsize=18, loc="left", color="#0F172A", pad=18)
curves = {("R6", "R4"): -.16, ("R4", "R6"): -.17, ("R6", "R3"): .2,
          ("live", "check"): -.15}
labels = {
    ("R1", "R3"): (6.9, 9.64), ("R2", "R3"): (5.5, 9.27),
    ("R2", "R5a"): (3.8, 8.37), ("R3", "R5a"): (6.8, 8.35),
    ("R3", "rej"): (10.5, 8.72), ("rej", "R6"): (11.8, 6.7),
    ("R6", "R3"): (10.15, 7.1), ("live", "R4"): (3.2, 6.2),
    ("R4", "R5b"): (3.6, 4.87), ("R4", "R6"): (7.3, 6.0),
    ("R5b", "R6"): (8.6, 4.55), ("R6", "R4"): (7.2, 5.02),
    ("live", "check"): (6.6, 5.7), ("check", "R8"): (4.95, 2.12),
    ("check", "R7"): (8.6, 2.85), ("R7", "R8"): (7.8, 1.76),
    ("R7", "refund"): (11.2, 1.39), ("check", "refund"): (8.1, 1.08),
}
for start, style, label, end in edges:
    dashed = style == "-.->"
    color = "#7C3AED" if dashed else "#475569"
    ax.add_patch(FancyArrowPatch(positions[start], positions[end], arrowstyle="-|>",
                                mutation_scale=13, color=color, linewidth=1.25,
                                linestyle="--" if dashed else "-", shrinkA=20,
                                shrinkB=23, connectionstyle=f"arc3,rad={curves.get((start,end),0)}"))
    if label:
        ax.text(*labels[(start, end)], label, ha="center", fontsize=8, color=color,
                bbox={"boxstyle": "square,pad=.12", "fc": "white", "ec": "none"})
for key, name in names.items():
    rid = name.split()[0]
    if rid in cfg["resources"]:
        channels, limit, _, _ = cfg["resources"][rid]
        name += f"\nКаналы: {channels} · очередь: {limit}"
    ax.text(*positions[key], name, ha="center", va="center", fontsize=9, zorder=4,
            color="#0F172A", bbox={"boxstyle": "round,pad=.56",
                   "fc": "#DBEAFE" if rid in cfg["resources"] else "#F1F5F9",
                   "ec": "#3B82F6" if rid in cfg["resources"] else "#94A3B8"})
fig.savefig(ROOT / "figures/platform.svg", metadata={"Date": None})
svg = ROOT / 'figures/platform.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
print("Параметры согласованы, схема R1–R8 сохранена.")
