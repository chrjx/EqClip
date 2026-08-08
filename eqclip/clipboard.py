"""Polls the macOS general pasteboard for newly copied images.

There is no native "clipboard changed" push notification on macOS outside
of sandboxed apps with special entitlements, so like every other clipboard
utility we poll NSPasteboard.changeCount(), which is cheap (no data is
copied unless the count actually moved).
"""

import threading
import time

from AppKit import (
    NSBitmapImageRep,
    NSPasteboard,
    NSPasteboardTypePNG,
    NSPasteboardTypeTIFF,
)

try:
    from AppKit import NSBitmapImageFileTypePNG as _PNG_FILE_TYPE
except ImportError:  # older/renamed pyobjc constant
    from AppKit import NSPNGFileType as _PNG_FILE_TYPE

from . import logging_setup

log = logging_setup.get_logger("clipboard")


class ClipboardWatcher:
    """Background poller that reports newly copied images.

    ``on_image`` is called with raw PNG bytes whenever a new image lands on
    the clipboard while the watcher is enabled. It always runs on its own
    daemon thread, off the main run loop.
    """

    def __init__(self, on_image, poll_interval=0.6):
        self._on_image = on_image
        self._poll_interval = poll_interval
        self._pb = NSPasteboard.generalPasteboard()
        self._last_change_count = self._pb.changeCount()
        self._enabled = False
        self._stop_flag = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_flag = True

    def set_enabled(self, enabled):
        self._enabled = enabled
        if enabled:
            # Don't reprocess whatever was already sitting on the clipboard
            # from before EqClip was turned on.
            self._last_change_count = self._pb.changeCount()

    def _run(self):
        while not self._stop_flag:
            time.sleep(self._poll_interval)
            count = self._pb.changeCount()
            if count == self._last_change_count:
                continue
            self._last_change_count = count
            if not self._enabled:
                continue
            png_bytes = self._extract_png()
            if png_bytes:
                log.info(
                    "New clipboard image detected (%.1fKB)", len(png_bytes) / 1024
                )
                self._on_image(png_bytes)

    def _extract_png(self):
        data = self._pb.dataForType_(NSPasteboardTypePNG)
        if data is not None:
            return bytes(data)

        # Screen captures copied with Cmd+Ctrl+Shift+4 land as TIFF, not PNG.
        tiff = self._pb.dataForType_(NSPasteboardTypeTIFF)
        if tiff is None:
            return None
        rep = NSBitmapImageRep.imageRepWithData_(tiff)
        if rep is None:
            return None
        png = rep.representationUsingType_properties_(_PNG_FILE_TYPE, None)
        if png is None:
            return None
        return bytes(png)
