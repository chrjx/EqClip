"""EqClip: menu-bar app that transcribes clipboard screenshots of papers
into Markdown + LaTeX using a free LLM backend.
"""

import subprocess
import threading
import time

import requests
import rumps
from PyObjCTools import AppHelper

from . import config as configmod
from . import logging_setup
from . import updater
from .__version__ import __version__
from .clipboard import ClipboardWatcher
from .hotkey import HotkeyListener
from .llm import KNOWN_GEMINI_MODELS, NOT_A_PAPER, TranscriptionError, build_transcriber
from .popup import show_transcript_window

log = logging_setup.get_logger("app")

_UPDATE_REPO_PLACEHOLDER = "YOUR_GITHUB_USERNAME/EqClip"

ICON_ON = "🧮🟢"
ICON_OFF = "🧮🔴"

# (label shown in menu, pynput hotkey string)
HOTKEY_PRESETS = [
    ("⌘⇧E (default)", "<cmd>+<shift>+e"),
    ("⌘⇧C", "<cmd>+<shift>+c"),
    ("⌘⌥E", "<cmd>+<alt>+e"),
    ("⌃⌥E", "<ctrl>+<alt>+e"),
]


class EqClipApp(rumps.App):
    def __init__(self):
        super().__init__("EqClip", title=ICON_ON, quit_button=None)

        self.cfg = configmod.load()
        self.enabled = bool(self.cfg.get("enabled_at_launch", True))

        self.toggle_item = rumps.MenuItem(
            "Disable" if self.enabled else "Enable", callback=self.toggle
        )
        self.backend_gemini_item = rumps.MenuItem(
            "Backend: Gemini (free, cloud)", callback=self.set_backend_gemini
        )
        self.backend_ollama_item = rumps.MenuItem(
            "Backend: Ollama (free, local)", callback=self.set_backend_ollama
        )

        self.gemini_model_menu = rumps.MenuItem("Gemini Model")
        self.ollama_model_menu = rumps.MenuItem("Ollama Model")
        self.hotkey_menu = rumps.MenuItem("Hotkey")
        self._gemini_model_items = {}
        self._ollama_model_items = {}
        self._hotkey_items = {}
        self._rebuild_gemini_model_menu()
        self._rebuild_ollama_model_menu()
        self._rebuild_hotkey_menu()

        self.menu = [
            self.toggle_item,
            None,
            self.backend_gemini_item,
            self.backend_ollama_item,
            None,
            rumps.MenuItem("Set Gemini API Key...", callback=self.set_api_key),
            self.gemini_model_menu,
            self.ollama_model_menu,
            self.hotkey_menu,
            None,
            rumps.MenuItem("Open Log File", callback=self.open_log_file),
            rumps.MenuItem("Check for Updates...", callback=self.check_for_updates),
            rumps.MenuItem("About EqClip", callback=self.show_about),
            rumps.MenuItem("Quit EqClip", callback=self.quit),
        ]
        self._refresh_backend_checks()

        log.info(
            "EqClip starting: backend=%s enabled=%s hotkey=%s",
            self.cfg["backend"],
            self.enabled,
            self.cfg["hotkey"],
        )

        self.watcher = ClipboardWatcher(on_image=self._handle_image)
        self.watcher.set_enabled(self.enabled)
        self.watcher.start()

        self.hotkey = HotkeyListener(self.cfg["hotkey"], self._hotkey_pressed)
        try:
            self.hotkey.start()
        except Exception as exc:  # noqa: BLE001
            log.warning("Hotkey listener failed to start: %s", exc)
            rumps.notification(
                "EqClip",
                "Hotkey not active",
                f"{exc}. Grant Accessibility permission and restart.",
            )

        self.update_title()

        if self.cfg.get("check_updates_on_launch", True):
            threading.Thread(
                target=self._check_for_updates_worker, args=(True,), daemon=True
            ).start()

    # --- menu callbacks --------------------------------------------------

    def update_title(self):
        self.title = ICON_ON if self.enabled else ICON_OFF
        self.toggle_item.title = "Disable" if self.enabled else "Enable"

    @staticmethod
    def _clear_submenu(parent):
        # rumps.MenuItem.clear() assumes its backing NSMenu already exists,
        # but that's only created lazily on first add() -- calling clear()
        # on a still-empty submenu (e.g. the very first build) raises.
        if parent._menu is not None:
            parent.clear()

    def toggle(self, _sender=None):
        self.enabled = not self.enabled
        self.watcher.set_enabled(self.enabled)
        self.update_title()
        log.info("Watching %s", "enabled" if self.enabled else "paused")
        rumps.notification(
            "EqClip", None, "Watching clipboard" if self.enabled else "Paused"
        )

    def open_log_file(self, _sender=None):
        subprocess.run(["open", "-a", "Console", logging_setup.LOG_PATH], check=False)

    def check_for_updates(self, _sender=None):
        threading.Thread(
            target=self._check_for_updates_worker, args=(False,), daemon=True
        ).start()

    def _check_for_updates_worker(self, silent):
        repo = self.cfg.get("update_repo", _UPDATE_REPO_PLACEHOLDER)
        if repo == _UPDATE_REPO_PLACEHOLDER:
            if not silent:
                AppHelper.callAfter(
                    rumps.alert,
                    "EqClip",
                    "No GitHub repo configured for update checks yet. Set "
                    "\"update_repo\" in "
                    "~/Library/Application Support/EqClip/config.json to "
                    "\"owner/repo\".",
                )
            return

        if silent:
            time.sleep(3)  # let startup finish before making a network call

        result = updater.check_for_update(repo)
        if result is None:
            if not silent:
                AppHelper.callAfter(
                    rumps.notification,
                    "EqClip",
                    None,
                    f"You're up to date (v{__version__}).",
                )
            return

        tag, html_url = result
        AppHelper.callAfter(self._show_update_available, tag, html_url)

    def _show_update_available(self, tag, html_url):
        clicked = rumps.alert(
            "EqClip Update Available",
            f"{tag} is available (you have v{__version__}).",
            ok="View Release",
            cancel="Later",
        )
        if clicked == 1:
            updater.open_release_page(html_url)

    def _hotkey_pressed(self):
        # Runs on pynput's listener thread -- hop to the main run loop.
        AppHelper.callAfter(self.toggle)

    def set_backend_gemini(self, _sender=None):
        self.cfg["backend"] = "gemini"
        configmod.save(self.cfg)
        self._refresh_backend_checks()
        log.info("Backend switched to gemini")

    def set_backend_ollama(self, _sender=None):
        self.cfg["backend"] = "ollama"
        configmod.save(self.cfg)
        self._refresh_backend_checks()
        log.info("Backend switched to ollama")

    def _refresh_backend_checks(self):
        self.backend_gemini_item.state = self.cfg["backend"] == "gemini"
        self.backend_ollama_item.state = self.cfg["backend"] == "ollama"

    def set_api_key(self, _sender=None):
        window = rumps.Window(
            message=(
                "Paste your free Gemini API key "
                "(get one at https://aistudio.google.com/apikey):"
            ),
            title="Set Gemini API Key",
            default_text=self.cfg.get("gemini_api_key", ""),
            ok="Save",
            cancel="Cancel",
            dimensions=(320, 24),
        )
        resp = window.run()
        if resp.clicked:
            self.cfg["gemini_api_key"] = resp.text.strip()
            configmod.save(self.cfg)
            log.info("Gemini API key updated")  # value itself is never logged

    # --- Gemini model picker ----------------------------------------------

    def _rebuild_gemini_model_menu(self):
        current = self.cfg.get("gemini_model", KNOWN_GEMINI_MODELS[0])
        models = list(KNOWN_GEMINI_MODELS)
        if current not in models:
            models.insert(0, current)

        self._clear_submenu(self.gemini_model_menu)
        self._gemini_model_items = {}
        for name in models:
            item = rumps.MenuItem(name, callback=self._select_gemini_model(name))
            item.state = name == current
            self._gemini_model_items[name] = item
            self.gemini_model_menu.add(item)
        self.gemini_model_menu.add(None)
        self.gemini_model_menu.add(
            rumps.MenuItem("Custom...", callback=self.set_gemini_model_custom)
        )

    def _select_gemini_model(self, name):
        def _callback(_sender=None):
            self.cfg["gemini_model"] = name
            configmod.save(self.cfg)
            for model_name, item in self._gemini_model_items.items():
                item.state = model_name == name
            log.info("Gemini model set to %s", name)

        return _callback

    def set_gemini_model_custom(self, _sender=None):
        window = rumps.Window(
            message=(
                "Gemini model to try first (still automatically falls back "
                "to the built-in list below if this one is overloaded), "
                "e.g. a preview model not in the list yet:"
            ),
            title="Set Custom Gemini Model",
            default_text=self.cfg.get("gemini_model", ""),
            ok="Save",
            cancel="Cancel",
            dimensions=(320, 24),
        )
        resp = window.run()
        if resp.clicked and resp.text.strip():
            self.cfg["gemini_model"] = resp.text.strip()
            configmod.save(self.cfg)
            log.info("Gemini model set to %s (custom)", self.cfg["gemini_model"])
            self._rebuild_gemini_model_menu()

    # --- Ollama model picker ------------------------------------------------

    def _fetch_ollama_tags(self):
        host = self.cfg.get("ollama_host", "http://localhost:11434").rstrip("/")
        try:
            resp = requests.get(f"{host}/api/tags", timeout=2)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("Could not list Ollama models: %s", exc)
            return []
        try:
            return sorted(m["name"] for m in resp.json().get("models", []))
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("Unexpected response listing Ollama models: %s", exc)
            return []

    def _rebuild_ollama_model_menu(self):
        current = self.cfg.get("ollama_model", "")
        tags = self._fetch_ollama_tags()
        if current and current not in tags:
            tags = [current] + tags

        self._clear_submenu(self.ollama_model_menu)
        self._ollama_model_items = {}
        if not tags:
            info = rumps.MenuItem("(no models found -- is Ollama running?)")
            self.ollama_model_menu.add(info)
        else:
            for name in tags:
                item = rumps.MenuItem(name, callback=self._select_ollama_model(name))
                item.state = name == current
                self._ollama_model_items[name] = item
                self.ollama_model_menu.add(item)
        self.ollama_model_menu.add(None)
        self.ollama_model_menu.add(
            rumps.MenuItem(
                "Refresh List", callback=lambda _s: self._rebuild_ollama_model_menu()
            )
        )
        self.ollama_model_menu.add(
            rumps.MenuItem("Custom...", callback=self.set_ollama_model_custom)
        )

    def _select_ollama_model(self, name):
        def _callback(_sender=None):
            self.cfg["ollama_model"] = name
            configmod.save(self.cfg)
            for model_name, item in self._ollama_model_items.items():
                item.state = model_name == name
            log.info("Ollama model set to %s", name)

        return _callback

    def set_ollama_model_custom(self, _sender=None):
        window = rumps.Window(
            message=(
                "Ollama vision model name, must already be pulled locally "
                "(e.g. qwen2.5vl:7b, llama3.2-vision):"
            ),
            title="Set Custom Ollama Model",
            default_text=self.cfg.get("ollama_model", ""),
            ok="Save",
            cancel="Cancel",
            dimensions=(320, 24),
        )
        resp = window.run()
        if resp.clicked and resp.text.strip():
            self.cfg["ollama_model"] = resp.text.strip()
            configmod.save(self.cfg)
            log.info("Ollama model set to %s (custom)", self.cfg["ollama_model"])
            self._rebuild_ollama_model_menu()

    # --- hotkey picker ------------------------------------------------------

    def _rebuild_hotkey_menu(self):
        current = self.cfg.get("hotkey", HOTKEY_PRESETS[0][1])
        presets = list(HOTKEY_PRESETS)
        if current not in (combo for _label, combo in presets):
            presets = [(current, current)] + presets

        self._clear_submenu(self.hotkey_menu)
        self._hotkey_items = {}
        for label, combo in presets:
            item = rumps.MenuItem(label, callback=self._select_hotkey(combo))
            item.state = combo == current
            self._hotkey_items[combo] = item
            self.hotkey_menu.add(item)
        self.hotkey_menu.add(None)
        self.hotkey_menu.add(
            rumps.MenuItem("Custom...", callback=self.set_hotkey_custom)
        )

    def _select_hotkey(self, combo):
        def _callback(_sender=None):
            try:
                self.hotkey.restart(combo)
            except Exception as exc:  # noqa: BLE001
                rumps.alert("EqClip", f"Could not set hotkey: {exc}")
                return
            self.cfg["hotkey"] = combo
            configmod.save(self.cfg)
            for hk, item in self._hotkey_items.items():
                item.state = hk == combo
            log.info("Hotkey set to %s", combo)

        return _callback

    def set_hotkey_custom(self, _sender=None):
        window = rumps.Window(
            message=(
                "Global hotkey to enable/disable EqClip, in pynput format "
                "(e.g. <cmd>+<shift>+e):"
            ),
            title="Set Custom Hotkey",
            default_text=self.cfg.get("hotkey", "<cmd>+<shift>+e"),
            ok="Save",
            cancel="Cancel",
            dimensions=(320, 24),
        )
        resp = window.run()
        if resp.clicked and resp.text.strip():
            new_combo = resp.text.strip()
            try:
                self.hotkey.restart(new_combo)
            except Exception as exc:  # noqa: BLE001
                rumps.alert("EqClip", f"Could not set hotkey: {exc}")
                return
            self.cfg["hotkey"] = new_combo
            configmod.save(self.cfg)
            log.info("Hotkey set to %s (custom)", new_combo)
            self._rebuild_hotkey_menu()

    def show_about(self, _sender=None):
        rumps.alert(
            f"EqClip v{__version__}",
            "Watches your clipboard for screenshots of scientific papers "
            "and transcribes them to Markdown + LaTeX using a free LLM "
            f"backend.\n\nCurrent backend: {self.cfg['backend']}\n"
            f"Hotkey: {self.cfg['hotkey']}\n\n"
            "Toggle from this menu or with the hotkey.",
        )

    def quit(self, _sender=None):
        log.info("EqClip quitting")
        self.hotkey.stop()
        self.watcher.stop()
        rumps.quit_application()

    # --- core pipeline -----------------------------------------------------

    def _handle_image(self, png_bytes):
        # Runs on the clipboard-poll thread -- do the (slow) network call on
        # its own thread so we never block polling or the main run loop.
        threading.Thread(
            target=self._process_image, args=(png_bytes,), daemon=True
        ).start()

    def _show_failure_alert(self, message):
        # A notification banner alone is too easy to miss (auto-dismisses,
        # gets buried under Focus mode, etc.) -- a modal alert forces you
        # to see that a transcription actually failed.
        rumps.notification("EqClip - Error", None, message)
        rumps.alert("EqClip - Transcription Failed", message)

    def _process_image(self, png_bytes):
        t0 = time.monotonic()
        AppHelper.callAfter(
            rumps.notification, "EqClip", None, "Screenshot detected, transcribing..."
        )
        try:
            transcriber = build_transcriber(self.cfg)
            text = transcriber.transcribe(png_bytes)
        except TranscriptionError as exc:
            log.warning(
                "Pipeline failed after %.2fs: %s", time.monotonic() - t0, exc
            )
            AppHelper.callAfter(self._show_failure_alert, str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            log.exception(
                "Pipeline hit an unexpected error after %.2fs", time.monotonic() - t0
            )
            AppHelper.callAfter(self._show_failure_alert, f"Unexpected error: {exc}")
            return

        elapsed = time.monotonic() - t0
        if text.strip() == NOT_A_PAPER:
            log.info("Skipped (not recognized as a paper) - %.2fs total", elapsed)
            AppHelper.callAfter(
                rumps.notification,
                "EqClip",
                None,
                "Clipboard image doesn't look like a paper -- skipped.",
            )
            return

        log.info(
            "Pipeline complete in %.2fs total (backend=%s)", elapsed, self.cfg["backend"]
        )

        if self.cfg.get("auto_copy_result", True):
            AppHelper.callAfter(self._copy_to_clipboard, text)

        AppHelper.callAfter(
            rumps.notification,
            "EqClip",
            None,
            "Transcription ready" + (
                " (copied to clipboard)." if self.cfg.get("auto_copy_result", True) else "."
            ),
        )

        if self.cfg.get("show_popup", True):
            AppHelper.callAfter(show_transcript_window, "EqClip Transcript", text)

    def _copy_to_clipboard(self, text):
        from AppKit import NSPasteboard, NSPasteboardTypeString

        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(text, NSPasteboardTypeString)
        # This bumps changeCount, but since it's plain text (not an image),
        # the watcher's _extract_png() finds nothing and simply ignores it
        # on its next poll -- no extra bookkeeping needed here.
