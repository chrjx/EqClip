# EqClip

A macOS menu-bar app that watches your clipboard. When you copy a
screenshot of a scientific paper (a page, an equation, a figure caption,
etc.), it sends it to a free LLM backend and replaces/shows the content as
Markdown with LaTeX math (`$...$` / `$$...$$`), ready to paste into notes,
Overleaf, Obsidian, etc. Non-paper screenshots (memes, UI, chat) are
silently ignored.

## Features

- Lives in the menu bar only (no Dock icon).
- Global hotkey to pause/resume watching (default `Cmd+Shift+E`).
- Two free LLM backends, switchable from the tray menu:
  - **Gemini** (cloud) — free API key from Google AI Studio, best quality.
  - **Ollama** (local) — fully offline, no account, no key, needs a vision
    model pulled locally.
- Detection + transcription happen in one LLM call: the model is told to
  reply with a sentinel if the image isn't a paper, so junk screenshots
  don't get "transcribed."
- Auto-copies the result back to the clipboard, and opens a small floating
  window with the transcript (with its own Copy button) so you can review
  it before it clobbers whatever else you meant to paste.
- Gemini requests automatically retry on a different free-tier model
  (`gemini-flash-latest` → `gemini-flash-lite-latest` → `gemini-2.5-flash`)
  if one is temporarily overloaded (503 "high demand"), and each attempt is
  capped at 30s so a stuck request fails fast instead of hanging.
- A failed transcription pops up a modal alert (not just a notification
  banner) so it can't be missed/dismissed without noticing.

## 1. Install

```bash
cd EqClip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Pick a free LLM backend

### Option A — Gemini (recommended, best transcription quality)

1. Go to <https://aistudio.google.com/apikey> and create a free API key
   (no credit card needed for the free tier).
2. Run the app (see step 3), then in the tray menu click
   **Set Gemini API Key...** and paste it in.
3. Free tier covers the Flash model EqClip uses by default
   (`gemini-flash-latest`), with a daily/per-minute request cap. If you hit
   the cap or the model is briefly overloaded, EqClip automatically retries
   on other free-tier models before giving up; a real failure shows a modal
   alert — wait a bit or switch to Ollama.
4. To try a different model first (e.g. if `gemini-flash-latest` is
   consistently slow/overloaded for you), pick one from the **Gemini
   Model** submenu in the tray menu (or **Custom...** at the bottom of it
   for a model not in the list).

### Option B — Ollama (fully local & offline, no key, no account)

1. Install Ollama: <https://ollama.com/download>
2. Pull a vision-capable model, e.g.:
   ```bash
   ollama pull qwen2.5vl:7b
   ```
   (`llama3.2-vision` also works; bigger models transcribe more
   accurately but run slower on your Mac.)
3. Make sure Ollama is running (`ollama serve`, or just open the Ollama
   app — it runs a background server on `localhost:11434`).
4. In EqClip's tray menu, select **Backend: Ollama (free, local)**. The
   **Ollama Model** submenu lists whatever you've actually pulled (queried
   live from Ollama) — pick one, or use **Refresh List** after pulling a
   new one, or **Custom...** to type a name that isn't pulled yet.

You can switch backends anytime from the tray menu; nothing else needs to
change.

## 3. Run it

```bash
python3 main.py
```

A calculator icon with a colored dot (🧮🟢) appears in your menu bar —
green means watching, red means paused. Copy a screenshot of a paper (e.g.
`Cmd+Ctrl+Shift+4` to select a region straight to the clipboard) and
within a few seconds you'll get a notification and a transcript window.

## 4. Grant permissions (needed for the global hotkey)

The hotkey listener uses macOS's Accessibility API to catch key combos
system-wide. Whatever process runs the app needs that permission:

- Running via `python3 main.py` from Terminal: grant **Terminal** (or
  iTerm, etc.) access in **System Settings -> Privacy & Security ->
  Accessibility**.
- Running the bundled `.app` (see below): grant **EqClip.app** access in
  that same pane.

Without this, everything else works — you can still toggle from the tray
menu — the hotkey just won't fire.

No Screen Recording permission is needed: EqClip only reads whatever
image is already on the clipboard, it never captures the screen itself.

## 5. Install as a real app (recommended)

A proper double-clickable `.app` in `/Applications` is easier to manage
Accessibility permissions for, and can start automatically at login:

```bash
./install.sh                # build + install to /Applications
./install.sh --login-item   # ...and start EqClip automatically at login
```

Re-run anytime to rebuild from source and replace the installed copy.
`./uninstall.sh` removes it (`--purge` also deletes your saved config/API
key/logs). Since EqClip isn't code-signed or notarized (no Apple
Developer account), the first launch will warn "unidentified developer" —
right-click the app -> **Open** once to bypass Gatekeeper, then grant
Accessibility permission to `EqClip.app` as in step 4.

To hand a build to someone else instead of installing it yourself, use
`./package.sh` — builds the same `.app` and wraps it in a proper
`EqClip.dmg` (the double-click-and-drag-to-Applications installer real
Mac apps ship as), using [`create-dmg`](https://github.com/create-dmg/create-dmg)
if installed (`brew install create-dmg`) for the nice drag-to-Applications
layout, or a plain disk image otherwise.

## Configuration

Settings persist in
`~/Library/Application Support/EqClip/config.json` and are all editable
from the tray menu:

| Setting | Meaning |
|---|---|
| Backend | `gemini` or `ollama` |
| Gemini API key / model | for the cloud backend |
| Ollama host / model | for the local backend |
| Hotkey | pick a preset from the **Hotkey** submenu, or **Custom...** using pynput format (e.g. `<cmd>+<shift>+e` — see [pynput docs](https://pynput.readthedocs.io/en/latest/keyboard.html#global-hotkeys)) |

`auto_copy_result` and `show_popup` (both default `true`) can be toggled
directly in the JSON file if you want silent clipboard-only behavior.

## Releases & updates

Tagged commits are built and published automatically by
`.github/workflows/release.yml` (see Development below) — grab the
`.dmg` from the repo's GitHub Releases page, open it, and drag `EqClip.app`
onto the Applications shortcut (same Gatekeeper right-click-Open step as
installing locally, since these builds aren't signed either).

EqClip checks for a newer release on launch and via **Check for
Updates...** in the tray menu. It only compares version numbers against
GitHub — it never silently downloads or replaces itself (again, no code
signing means a swapped-in update would just get blocked by Gatekeeper
anyway), so a "newer version available" alert just offers to open the
release page for you to grab it manually. Point it at your repo by
setting `"update_repo": "owner/repo"` in config.json (defaults to a
placeholder that no-ops rather than querying a repo that may not exist).
Disable the on-launch check with `"check_updates_on_launch": false`.

## Logs

EqClip logs every stage of the pipeline — clipboard detection, which
backend/model handled the request, image size, and how long each step
took — to `~/Library/Logs/EqClip/eqclip.log` (rotated at 2MB, 3 backups
kept). The same lines also print live to Terminal while `python3 main.py`
is running. Open it quickly via the tray menu's **Open Log File** (opens
in Console.app, which can tail it live), or:

```bash
tail -f ~/Library/Logs/EqClip/eqclip.log
```

If transcription feels slow, this is where to look — each backend logs
its own request/response timing (e.g. `Gemini response in 6.42s
(1830 chars)`), and the app logs the end-to-end pipeline time separately,
so you can tell whether the delay is the LLM call itself (usually is) or
something else. The transcribed text and your API key are never written
to the log, only sizes/timings/metadata.

## How it works

- `eqclip/clipboard.py` polls `NSPasteboard.changeCount()` on a background
  thread (there's no native "clipboard changed" push event on macOS) and
  pulls out PNG/TIFF image data when it changes.
- `eqclip/llm.py` sends the image + a transcription prompt to whichever
  backend is active and returns Markdown+LaTeX text, or the `NOT_A_PAPER`
  sentinel to be skipped.
- `eqclip/hotkey.py` wraps `pynput.keyboard.GlobalHotKeys` to toggle
  watching on/off.
- `eqclip/popup.py` shows the result in a plain AppKit window (not
  Tkinter, to avoid clashing with `rumps`' own Cocoa run loop).
- `eqclip/app.py` is the `rumps.App` that ties it all together and drives
  the tray menu/icon.
- `eqclip/updater.py` checks GitHub Releases for a newer version.
- `eqclip/__version__.py` is the single source of truth for the version
  number, read by `setup.py` (bundle version) and the updater.

## Development

- `.github/workflows/ci.yml` runs on every push/PR to `main`: byte-compiles
  the project, then runs `./package.sh` as a full packaging smoke test
  (this is the step that would have caught the google-genai
  namespace-package issue below before it ever reached a release).
- `.github/workflows/release.yml` runs when a tag matching `vX.Y.Z` is
  pushed: runs the same `./package.sh` to produce `EqClip.dmg`, then
  publishes it as a GitHub Release with auto-generated notes.

To cut a release:
```bash
# 1. bump the version
$EDITOR eqclip/__version__.py   # __version__ = "0.2.0"
git commit -am "Bump version to 0.2.0"

# 2. tag and push -- CI does the rest
git tag v0.2.0
git push origin main v0.2.0
```
The release workflow refuses to run if the tag doesn't match
`eqclip/__version__.py`, to catch a forgotten version bump.

**Notes on `google-genai` + py2app** (a real dependency that's caused
several py2app-specific bugs, all fixed in `setup.py`'s `packages`/
`includes`, none reproducible in dev mode since that uses the venv's
site-packages directly):
- The `google` package it installs under is a PEP 420 namespace package
  (no `__init__.py`), which py2app's bootstrap resolver can't handle
  directly (`ImportError: No module named 'google'`). `install.sh` and
  `package.sh` work around this by touching an empty `__init__.py` into
  the installed `google/` directory before building, which is safe since
  `google.genai`/`google.auth`/`google.oauth2` keep their own real
  `__init__.py` files and resolve as subpackages exactly the same way
  either way.
- `google.auth` pulls in `cryptography` -> `cffi` even for plain API-key
  auth, but modulegraph never traces `cffi`'s compiled `_cffi_backend`
  extension, so it silently never made it into early builds -- crashing
  with `No module named '_cffi_backend'` the instant `genai.Client()` was
  constructed. Fixed by forcing `_cffi_backend` into `includes` and
  bundling `cffi` as a full package.
- `httpx` (used internally for the API calls) loads its TLS CA bundle via
  `certifi.where()`, which returns a real filesystem path -- but py2app
  zips any package not listed in `packages` into `python*.zip` by
  default, and a path *inside* a zip archive can't be opened by normal
  file APIs. This silently broke certificate verification, which
  manifested as every single Gemini request hanging for the full
  client-side timeout with no response at all, rather than a clear error.
  Fixed by bundling `certifi` as a full package too.

## Troubleshooting

- **Hotkey does nothing**: check Accessibility permission (step 4).
- **"No Gemini API key set"**: set one via the tray menu, or switch to
  Ollama.
- **"Could not reach Ollama..."**: make sure `ollama serve` / the Ollama
  app is running and the model name matches one you've pulled
  (`ollama list`).
- **Notifications don't appear but it still works**: macOS notification
  center can be finicky for plain (non-bundled) Python scripts. The
  transcript popup window is the reliable indicator; building the `.app`
  bundle (step 5) tends to fix notifications too.
- **Nothing happens when I copy a screenshot**: confirm the tray icon
  shows the green dot (🧮🟢, enabled) not the red one (🧮🔴, paused), and
  that what you copied actually contains image data (not just a file
  reference).
