#!/usr/bin/env python3
"""Render the past year of contributions as an isometric 3D calendar.

Writes calendar_dark.svg and calendar_light.svg. Standard library only.
Requires GITHUB_TOKEN in the environment.
"""
import datetime as dt
import json
import math
from pathlib import Path

from github_api import graphql, token_from_env

ROOT = Path(__file__).resolve().parent.parent
LOGIN = json.loads((ROOT / "data" / "profile.json").read_text())["login"]

CELL_X, CELL_Y = 9.0, 5.2  # half-width and half-height of one isometric tile
MAX_HEIGHT = 46.0  # pixels for the busiest day
PAD = 28
CAPTION_H = 44
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}
"""

# Five levels, from empty to busiest. Each level: (top, left side, right side).
THEMES = {
    "dark": {
        "bg": "#161b22", "border": "#30363d", "text": "#c9d1d9", "muted": "#8b949e", "accent": "#ffa657",
        "levels": [("#21262d", "#161b22", "#1b2027"), ("#1f4f7a", "#163a5a", "#1a4468"),
                   ("#2f78b8", "#225787", "#28679f"), ("#58a6ff", "#3f78ba", "#4b8fdc"),
                   ("#a5d6ff", "#77a0c4", "#8ebce3")],
    },
    "light": {
        "bg": "#f6f8fa", "border": "#d0d7de", "text": "#24292f", "muted": "#57606a", "accent": "#953800",
        "levels": [("#ebeef1", "#d0d7de", "#dde2e7"), ("#b6d7f7", "#8db7e0", "#a2c7ec"),
                   ("#6aaae8", "#4a88c7", "#5a99d7"), ("#2f7bd0", "#215a9b", "#286ab6"),
                   ("#0a3069", "#06204a", "#082859")],
    },
}


def fetch_days(token: str) -> tuple:
    cal = graphql(QUERY, {"login": LOGIN}, token)["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(wi, d["weekday"], d["contributionCount"], d["date"])
            for wi, week in enumerate(cal["weeks"]) for d in week["contributionDays"]]
    return cal["totalContributions"], days


def level(count: int, peak: int) -> int:
    if count == 0:
        return 0
    return min(4, 1 + int(3 * math.sqrt(count / peak) + 0.25))


def prism(x: float, y: float, h: float, colors: tuple) -> str:
    top, left, right = colors
    t = [(x, y - h), (x + CELL_X, y + CELL_Y - h), (x, y + 2 * CELL_Y - h), (x - CELL_X, y + CELL_Y - h)]
    pts = lambda ps: " ".join(f"{a:.1f},{b:.1f}" for a, b in ps)
    parts = []
    if h > 0:
        parts.append(f'<polygon points="{pts([t[3], t[2], (x, y + 2 * CELL_Y), (x - CELL_X, y + CELL_Y)])}" fill="{left}"/>')
        parts.append(f'<polygon points="{pts([t[2], t[1], (x + CELL_X, y + CELL_Y), (x, y + 2 * CELL_Y)])}" fill="{right}"/>')
    parts.append(f'<polygon points="{pts(t)}" fill="{top}"/>')
    return "".join(parts)


def render(theme: dict, total: int, days: list) -> str:
    weeks = max(w for w, *_ in days) + 1
    peak = max(c for _, _, c, _ in days) or 1
    origin_x = PAD + 7 * CELL_X
    origin_y = PAD + MAX_HEIGHT + CAPTION_H
    width = round(origin_x + weeks * CELL_X + PAD)
    height = round(origin_y + (weeks + 7) * CELL_Y + PAD)
    first, last = days[0][3], days[-1][3]
    busiest = max(days, key=lambda d: d[2])
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" role="img" aria-label="{total} contributions from {first} to {last}">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" '
        f'fill="{theme["bg"]}" stroke="{theme["border"]}"/>',
        f'<text x="{PAD}" y="{PAD + 14}" font-family="{FONT}" font-size="15" fill="{theme["text"]}">'
        f'<tspan fill="{theme["accent"]}">{total:,}</tspan> contributions in the past year</text>',
        f'<text x="{PAD}" y="{PAD + 34}" font-family="{FONT}" font-size="12" fill="{theme["muted"]}">'
        f'{first} to {last} · busiest day {busiest[3]} ({busiest[2]})</text>',
    ]
    # Paint back to front so nearer prisms overlap farther ones.
    for w, d, count, _ in sorted(days, key=lambda t: (t[0] + t[1], t[0])):
        x = origin_x + (w - d) * CELL_X
        y = origin_y + (w + d) * CELL_Y
        h = 0 if count == 0 else 3 + MAX_HEIGHT * math.sqrt(count / peak)
        out.append(prism(x, y, h, theme["levels"][level(count, peak)]))
    out.append("</svg>")
    return "\n".join(out) + "\n"


def render_theme(name: str, token: str) -> str:
    """Fetch the live calendar and return the SVG for one theme ("dark" or "light")."""
    total, days = fetch_days(token)
    return render(THEMES[name], total, days)


def main() -> None:
    total, days = fetch_days(token_from_env())
    for name, theme in THEMES.items():
        (ROOT / f"calendar_{name}.svg").write_text(render(theme, total, days))
    print(f"rendered calendar: {total} contributions, {len(days)} days, generated {dt.date.today()}")


if __name__ == "__main__":
    main()
