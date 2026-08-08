"""Optional: bundle EqClip as a proper double-clickable .app.

    python3 setup.py py2app

produces dist/EqClip.app. Bundling isn't required to use EqClip (you can
just run `python3 main.py`), but a real .app is what you grant
Accessibility permission to for the global hotkey, and it can be added to
Login Items to start automatically.
"""

from setuptools import setup

from eqclip.__version__ import __version__

APP = ["main.py"]
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        # Menu-bar-only app: no Dock icon, no app switcher entry.
        "LSUIElement": True,
        "CFBundleName": "EqClip",
        "CFBundleDisplayName": "EqClip",
        "CFBundleIdentifier": "com.eqclip.app",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
    },
    # NOTE: "google" itself is a PEP 420 namespace package (no __init__.py)
    # -- py2app's bootstrap resolver can't handle that directly, so list
    # the real subpackages under it instead.
    "packages": [
        "rumps",
        "pynput",
        "google.genai",
        "google.auth",
        "google.oauth2",
        "requests",
        "eqclip",
        "cffi",
    ],
    # google.auth pulls in cryptography -> cffi at runtime (client-auth
    # setup, not just OAuth flows), but modulegraph's static analysis
    # never traces cffi's compiled _cffi_backend extension, so the built
    # app crashes with "No module named '_cffi_backend'" the moment
    # genai.Client() is constructed. Force it in explicitly.
    "includes": ["_cffi_backend"],
}

setup(
    app=APP,
    name="EqClip",
    version=__version__,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
