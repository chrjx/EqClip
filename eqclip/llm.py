"""LLM backends that turn a paper screenshot into Markdown + LaTeX.

Two free backends are supported:

- Gemini (cloud, free tier): needs a free API key from
  https://aistudio.google.com/apikey. Google's free tier currently covers
  the Flash / Flash-Lite models; ``gemini-flash-latest`` always points at
  the current free-tier Flash release so this doesn't go stale.
- Ollama (local, offline, no key): needs https://ollama.com installed and
  a vision-capable model pulled, e.g. ``ollama pull qwen2.5vl:7b``.

Both backends are asked to do detection *and* transcription in one shot:
if the image isn't a scientific/technical document, the model is told to
reply with the NOT_A_PAPER sentinel instead of transcribing garbage.
"""

import base64
import time

import requests

from . import logging_setup

log = logging_setup.get_logger("llm")

NOT_A_PAPER = "NOT_A_PAPER"

TRANSCRIBE_PROMPT = """You are an expert scientific-document transcriber.

Look closely at the attached image.

If it shows any part of a scientific/academic paper, textbook, lecture \
note, or technical document (body text, headings, equations, tables, \
figure captions, references, etc.), transcribe its visible content \
faithfully into GitHub-flavored Markdown:
- Render ALL mathematical notation as LaTeX, using $...$ for inline math \
and $$...$$ for display/block equations.
- Preserve structure you can see: headings, paragraphs, bullet/numbered \
lists, tables (as Markdown tables), bold/italic emphasis.
- Transcribe text exactly as written; do not summarize, explain, or add \
commentary.
- If part of the image is cut off or illegible, transcribe what you can \
and use "..." for the illegible part rather than guessing.
- Output ONLY the transcription, nothing else (no preamble like "Here is \
the transcription").

If the image clearly does NOT depict a scientific/academic or technical \
document (e.g. it's a photo, meme, chat screenshot, app UI, unrelated \
picture), respond with exactly this single token and nothing else:
NOT_A_PAPER
"""


class TranscriptionError(Exception):
    """Raised for any backend failure that should surface to the user."""


# Known-good free-tier models, also offered as tray-menu choices. Tried in
# order after the configured model, so a temporary "high demand" 503 on one
# doesn't stall the whole pipeline.
KNOWN_GEMINI_MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash"]

_REQUEST_TIMEOUT_MS = 30_000  # bound a single attempt so we fail fast, not after minutes


class GeminiTranscriber:
    def __init__(self, api_key, model):
        if not api_key:
            raise TranscriptionError(
                "No Gemini API key set. Use the tray menu -> 'Set Gemini "
                "API Key...'. Get a free key at "
                "https://aistudio.google.com/apikey"
            )
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS),
        )
        # Configured model first, then fall back to other free-tier models.
        self._models = [model] + [m for m in KNOWN_GEMINI_MODELS if m != model]

    def transcribe(self, png_bytes):
        last_exc = None
        for attempt, model in enumerate(self._models):
            log.info(
                "Gemini request: model=%s image=%.1fKB%s",
                model,
                len(png_bytes) / 1024,
                " (fallback)" if attempt else "",
            )
            t0 = time.monotonic()
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=[
                        TRANSCRIBE_PROMPT,
                        self._types.Part.from_bytes(
                            data=png_bytes, mime_type="image/png"
                        ),
                    ],
                )
            except Exception as exc:  # noqa: BLE001 - surface any SDK error
                elapsed = time.monotonic() - t0
                log.warning(
                    "Gemini model %s failed after %.2fs: %s", model, elapsed, exc
                )
                last_exc = exc
                continue

            elapsed = time.monotonic() - t0
            text = (getattr(response, "text", None) or "").strip()
            if not text:
                log.warning(
                    "Gemini model %s returned an empty response after %.2fs",
                    model,
                    elapsed,
                )
                last_exc = TranscriptionError(f"{model} returned an empty response.")
                continue

            log.info(
                "Gemini response in %.2fs (%d chars) via %s", elapsed, len(text), model
            )
            return text

        raise TranscriptionError(
            f"All Gemini models failed (tried {', '.join(self._models)}). "
            f"Last error: {last_exc}"
        )


class OllamaTranscriber:
    def __init__(self, host, model):
        self._host = host.rstrip("/")
        self._model = model

    def transcribe(self, png_bytes):
        log.info(
            "Ollama request: host=%s model=%s image=%.1fKB",
            self._host,
            self._model,
            len(png_bytes) / 1024,
        )
        b64 = base64.b64encode(png_bytes).decode("ascii")
        t0 = time.monotonic()
        try:
            resp = requests.post(
                f"{self._host}/api/generate",
                json={
                    "model": self._model,
                    "prompt": TRANSCRIBE_PROMPT,
                    "images": [b64],
                    "stream": False,
                },
                timeout=120,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.error(
                "Ollama request failed after %.2fs: %s",
                time.monotonic() - t0,
                exc,
            )
            raise TranscriptionError(
                f"Could not reach Ollama at {self._host} ({exc}). Is Ollama "
                f"running, and is '{self._model}' pulled? "
                f"Try: ollama pull {self._model}"
            ) from exc

        elapsed = time.monotonic() - t0
        data = resp.json()
        text = (data.get("response") or "").strip()
        if not text:
            log.error("Ollama returned an empty response after %.2fs", elapsed)
            raise TranscriptionError("Ollama returned an empty response.")

        log.info("Ollama response in %.2fs (%d chars)", elapsed, len(text))
        return text


def build_transcriber(cfg):
    if cfg["backend"] == "ollama":
        return OllamaTranscriber(cfg["ollama_host"], cfg["ollama_model"])
    return GeminiTranscriber(cfg["gemini_api_key"], cfg["gemini_model"])
