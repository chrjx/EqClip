"""Entry point: run with `python3 main.py`."""

from eqclip import logging_setup
from eqclip.app import EqClipApp


def main():
    logging_setup.setup()
    EqClipApp().run()


if __name__ == "__main__":
    main()
