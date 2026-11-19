"""Live profile images on Vercel (plain WSGI, standard library only).

GET /api/card?theme=dark|light     profile card with live GitHub stats
GET /api/contrib?theme=dark|light  3D contribution calendar

If live rendering fails (no token, GitHub down, rate limit), the last committed
SVG from the public profile repo is served instead, so the README never shows a
broken image.
"""
import os
import sys
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_calendar  # noqa: E402
import build_card  # noqa: E402

SNAPSHOT_BASE = "https://raw.githubusercontent.com/Xdashio/Xdashio/main/"
THEMES = ("dark", "light")
LIVE_CACHE = "public, max-age=1800, s-maxage=3600, stale-while-revalidate=86400"
FALLBACK_CACHE = "public, max-age=300, s-maxage=300"
ROUTES = {
    "/api/card": (build_card.render_theme, "{}_mode.svg"),
    "/api/contrib": (build_calendar.render_theme, "calendar_{}.svg"),
}


def _snapshot(name: str) -> str:
    with urllib.request.urlopen(SNAPSHOT_BASE + name, timeout=10) as resp:
        return resp.read().decode()


def _render(route: tuple, theme: str) -> tuple:
    render_theme, snapshot_name = route
    try:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN is not configured")
        return render_theme(theme, token), LIVE_CACHE, "live"
    except Exception as exc:  # serve the snapshot rather than a broken image
        print(f"live render failed, serving snapshot: {exc!r}", file=sys.stderr)
        return _snapshot(snapshot_name.format(theme)), FALLBACK_CACHE, "snapshot"


def app(environ, start_response):
    route = ROUTES.get(environ.get("PATH_INFO", "/").rstrip("/"))
    if route is None:
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not found. Try /api/card or /api/contrib\n"]
    theme = parse_qs(environ.get("QUERY_STRING", "")).get("theme", ["dark"])[0]
    if theme not in THEMES:
        theme = "dark"
    try:
        svg, cache, source = _render(route, theme)
    except Exception as exc:  # even the snapshot failed
        print(f"snapshot failed: {exc!r}", file=sys.stderr)
        start_response("503 Service Unavailable", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Temporarily unavailable\n"]
    body = svg.encode()
    start_response("200 OK", [
        ("Content-Type", "image/svg+xml; charset=utf-8"),
        ("Cache-Control", cache),
        ("X-Render-Source", source),
        ("Content-Length", str(len(body))),
    ])
    return [body]
