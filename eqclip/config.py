"""Persisted settings for EqClip.

Stored as JSON under ~/Library/Application Support/EqClip/config.json so
they survive app restarts. Nothing here is secret-managed beyond normal
filesystem permissions -- the Gemini API key is stored in plain text in
that file, same as most desktop tools that ask you to paste a key once.
"""

import json
import os

APP_SUPPORT_DIR = os.path.expanduser("~/Library/Application Support/EqClip")
CONFIG_PATH = os.path.join(APP_SUPPORT_DIR, "config.json")

DEFAULTS = {
    # "gemini" (free cloud API, best quality) or "ollama" (free local, offline)
    "backend": "gemini",
    "gemini_api_key": "",
    # Alias that always resolves to Google's current free-tier Flash model.
    "gemini_model": "gemini-flash-latest",
    "ollama_host": "http://localhost:11434",
    "ollama_model": "qwen2.5vl:7b",
    # pynput hotkey format: https://pynput.readthedocs.io/en/latest/keyboard.html#global-hotkeys
    "hotkey": "<cmd>+<shift>+e",
    "enabled_at_launch": True,
    "auto_copy_result": True,
    "show_popup": True,
    # "owner/repo" on GitHub to check for newer releases. Left as a
    # placeholder until you actually publish the repo -- the update
    # checker no-ops rather than querying a repo that may not exist.
    "update_repo": "YOUR_GITHUB_USERNAME/EqClip",
    "check_updates_on_launch": True,
}


def load():
    if not os.path.exists(CONFIG_PATH):
        cfg = dict(DEFAULTS)
        save(cfg)
        return cfg
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError):
        cfg = {}
    merged = dict(DEFAULTS)
    merged.update(cfg)
    return merged


def save(cfg):
    os.makedirs(APP_SUPPORT_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
