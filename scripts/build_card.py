#!/usr/bin/env python3
"""Render the profile card (dark_mode.svg, light_mode.svg) with live GitHub stats.

Standard library only, so the GitHub Action needs no installs.
Requires GITHUB_TOKEN in the environment.
"""
import datetime as dt
import json
from pathlib import Path
from xml.sax.saxutils import escape

from github_api import graphql, token_from_env

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

PANEL_COLS = 58
ART_FONT, ART_LINE = 13, 15.6
PANEL_FONT, PANEL_LINE = 15, 19.5
CHAR_W = 0.6  # monospace advance width as a fraction of font size
PAD, GAP = 30, 36
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"

THEMES = {
    "dark": {"bg": "#161b22", "border": "#30363d", "art": "#c9d1d9", "text": "#c9d1d9",
             "key": "#ffa657", "value": "#a5d6ff", "dots": "#484f58", "rule": "#484f58"},
    "light": {"bg": "#f6f8fa", "border": "#d0d7de", "art": "#24292f", "text": "#24292f",
              "key": "#953800", "value": "#0a3069", "dots": "#afb8c1", "rule": "#afb8c1"},
}

QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) { totalCount }
    contributionsCollection { contributionCalendar { totalContributions } }
  }
}
"""


def fetch_stats(login: str, token: str) -> dict:
    user = graphql(QUERY, {"login": login}, token)["user"]
    return {
        "since": user["createdAt"][:4],
        "followers": user["followers"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "contributions": user["contributionsCollection"]["contributionCalendar"]["totalContributions"],
    }


def leader_row(key: str, value: str) -> list:
    """'. Key: ....... value' padded to PANEL_COLS, as (text, role) spans."""
    head = f". {key}: "
    dots = PANEL_COLS - len(head) - len(value) - 1
    if dots < 2:
        raise ValueError(f"row too long for panel: {key}: {value}")
    return [(". ", "dots"), (f"{key}:", "key"), (" " + "." * dots + " ", "dots"), (value, "value")]


def rule_row(title: str) -> list:
    text = f"- {title} "
    return [("- ", "rule"), (title, "key"), (" " + "-" * (PANEL_COLS - len(text) - 1), "rule")]


def panel_lines(profile: dict, stats: dict, today: dt.date) -> list:
    years = today.year - profile["coding_since"]
    fills = {"{uptime}": f"{years} years, coding since {profile['coding_since']}"}
    prompt = profile["prompt"]
    lines = [[(prompt, "key"), (" " + "-" * (PANEL_COLS - len(prompt) - 1), "rule")]]
    for section in profile["sections"]:
        if section["title"]:
            lines.append([])
            lines.append(rule_row(section["title"]))
        elif len(lines) > 1:
            lines.append([(".", "dots")])
        for key, value in section["rows"]:
            lines.append(leader_row(key, fills.get(value, value)))
    lines.append([])
    lines.append(rule_row("GitHub Stats"))
    lines.append(leader_row("Contributions (past year)", f"{stats['contributions']:,}"))
    lines.append(leader_row("Public repos", str(stats["repos"])))
    lines.append(leader_row("Followers", str(stats["followers"])))
    lines.append(leader_row("On GitHub since", stats["since"]))
    lines.append(leader_row("Updated", today.isoformat()))
    return [line for i, line in enumerate(lines) if i == 0 or line or lines[i - 1]]


def render(theme: dict, art: list, panel: list) -> str:
    art_w = max(len(l) for l in art) * ART_FONT * CHAR_W
    panel_w = PANEL_COLS * PANEL_FONT * CHAR_W
    art_h, panel_h = len(art) * ART_LINE, len(panel) * PANEL_LINE
    width = round(PAD * 2 + art_w + GAP + panel_w)
    height = round(PAD * 2 + max(art_h, panel_h))
    art_y0 = PAD + (max(art_h, panel_h) - art_h) / 2 + ART_FONT
    panel_x = PAD + art_w + GAP
    panel_y0 = PAD + (max(art_h, panel_h) - panel_h) / 2 + PANEL_FONT
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="Xdashio profile card">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" '
        f'fill="{theme["bg"]}" stroke="{theme["border"]}"/>',
        f'<text font-family="{FONT}" font-size="{ART_FONT}" fill="{theme["art"]}" xml:space="preserve">',
    ]
    for i, line in enumerate(art):
        out.append(f'<tspan x="{PAD}" y="{art_y0 + i * ART_LINE:.1f}">{escape(line)}</tspan>')
    out.append("</text>")
    out.append(f'<text font-family="{FONT}" font-size="{PANEL_FONT}" fill="{theme["text"]}" xml:space="preserve">')
    for i, spans in enumerate(panel):
        if not spans:
            continue
        inner = "".join(f'<tspan fill="{theme[role]}">{escape(text)}</tspan>' for text, role in spans)
        out.append(f'<tspan x="{panel_x:.1f}" y="{panel_y0 + i * PANEL_LINE:.1f}">{inner}</tspan>')
    out.append("</text></svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    token = token_from_env()
    profile = json.loads((DATA / "profile.json").read_text())
    stats = fetch_stats(profile["login"], token)
    panel = panel_lines(profile, stats, dt.date.today())
    for name, theme in THEMES.items():
        art = (DATA / f"portrait_{name}.txt").read_text().rstrip("\n").split("\n")
        (ROOT / f"{name}_mode.svg").write_text(render(theme, art, panel))
    print(f"rendered card: {stats}")


if __name__ == "__main__":
    main()
