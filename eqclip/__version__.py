"""Single source of truth for EqClip's version.

Read by setup.py (py2app bundle version), eqclip/app.py (About dialog),
and eqclip/updater.py (compared against the latest GitHub release tag).
Bump this and tag the matching commit `vX.Y.Z` to cut a release.
"""

__version__ = "0.1.0"
