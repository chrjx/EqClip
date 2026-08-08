"""Checks GitHub Releases for a newer EqClip version.

EqClip isn't code-signed or notarized, so silently downloading and
swapping the running .app would still hit Gatekeeper on next launch --
there's no safe fully-automatic update path without paying for an Apple
Developer ID. Instead this only checks version numbers and, if something
newer exists, offers to open the release page in your browser so you can
grab and re-install it yourself (see install.sh).
"""

import subprocess

import requests

from . import logging_setup
from .__version__ import __version__

log = logging_setup.get_logger("updater")


def _parse_version(v):
    v = v.strip().lstrip("v")
    parts = []
    for piece in v.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def check_for_update(repo, timeout=5):
    """Return (tag, html_url) if a newer release exists on GitHub, else
    None. Never raises -- any network/parsing failure just means "no
    update info available right now", which is not worth interrupting the
    user over.
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        resp = requests.get(
            url, headers={"Accept": "application/vnd.github+json"}, timeout=timeout
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.info("Update check failed (non-fatal): %s", exc)
        return None

    tag = data.get("tag_name", "")
    if not tag:
        return None

    latest = _parse_version(tag)
    current = _parse_version(__version__)
    if latest > current:
        html_url = data.get("html_url", f"https://github.com/{repo}/releases")
        log.info("Update available: %s (current: v%s)", tag, __version__)
        return tag, html_url

    log.info("Up to date (current: v%s, latest tag: %s)", __version__, tag)
    return None


def open_release_page(url):
    subprocess.run(["open", url], check=False)
