"""Shared browser-cache policy for Homework Magic static assets.

Character assets deliberately keep stable URLs. This lets the avatar renderer,
customiser and styles change without editing every HTML page merely to alter a
query-string version. The short fresh window keeps navigation fast; supported
browsers can serve the cached copy while revalidating it in the background.
"""
from __future__ import annotations


CHARACTER_ASSET_PATHS = frozenset(
    {
        "/static/css/avatar-character.css",
        "/static/css/character-customise.css",
        "/static/js/auth-nav.js",
        "/static/js/avatar-character.js",
        "/static/js/avatar-data.js",
        "/static/js/avatar-pet.js",
        "/static/js/character-customise.js",
    }
)

CHARACTER_ASSET_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=3600"
DEFAULT_STATIC_CACHE_CONTROL = "public, max-age=3600, stale-while-revalidate=86400"


def cache_control_for_static_asset(path: str) -> str | None:
    """Return the cache policy for a non-HTML static asset path."""
    safe_path = str(path or "").split("?", 1)[0].lower()
    if safe_path in CHARACTER_ASSET_PATHS:
        return CHARACTER_ASSET_CACHE_CONTROL
    if safe_path.endswith(
        (
            ".css",
            ".js",
            ".svg",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".ico",
            ".woff",
            ".woff2",
        )
    ):
        return DEFAULT_STATIC_CACHE_CONTROL
    return None
