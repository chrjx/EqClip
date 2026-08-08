"""Global (system-wide) hotkey to toggle EqClip on/off.

Uses pynput's GlobalHotKeys, which relies on macOS's Quartz Event Taps.
The process running this (Terminal, or the packaged .app once bundled)
must be granted Accessibility permission in System Settings -> Privacy &
Security -> Accessibility, or the hotkey simply won't fire.
"""

from pynput import keyboard


class HotkeyListener:
    def __init__(self, combo, callback):
        self._combo = combo
        self._callback = callback
        self._listener = None

    def start(self):
        self._listener = keyboard.GlobalHotKeys({self._combo: self._callback})
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            # GlobalHotKeys.stop() only requests a stop -- the underlying
            # Quartz event-tap thread shuts down asynchronously. Starting a
            # new listener before the old one has actually exited can crash
            # (two native event taps briefly racing), so wait for it here.
            self._listener.join(timeout=2)
            self._listener = None

    def restart(self, new_combo=None):
        self.stop()
        if new_combo:
            self._combo = new_combo
        self.start()
