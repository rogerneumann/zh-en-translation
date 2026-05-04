"""Google Cloud Translation API (v2 Basic) engine integration."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zh_en_translator.config import Config

logger = logging.getLogger(__name__)

_API_URL = "https://translation.googleapis.com/language/translate/v2"


def translate_with_google(
    text: str,
    config: Config,
    source: str = "zh-CN",
    target: str = "en",
) -> str:
    """Translate text using the Google Cloud Translation API (v2 Basic).

    Requires a GCP API key with the Cloud Translation API enabled.
    Pricing: $20 per 1M characters (500K chars/month free tier).

    source / target default to zh-CN -> en.
    Pass source="en", target="zh-CN" for back-translation.
    """
    if not config.google_translate_enabled or not config.google_translate_api_key:
        return "\u26a0 Google Translate not configured."

    payload = {
        "q": text,
        "source": source,
        "target": target,
        "format": "text",
    }
    url = f"{_API_URL}?key={urllib.parse.quote(config.google_translate_api_key, safe='')}"
    data = json.dumps(payload).encode("utf-8")

    try:
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            translations = (
                result.get("data", {}).get("translations", [])
            )
            if translations:
                return translations[0].get("translatedText", "")
            return "\u26a0 Google Translate returned an empty result."

    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("error", {}).get("message", str(e.code))
            logger.error("Google Translate HTTP error %s: %s", e.code, msg)
            if e.code == 400:
                return f"\u26a0 Google Translate: bad request \u2014 {msg}"
            if e.code == 403:
                return "\u26a0 Google Translate API key invalid or API not enabled."
            if e.code == 429:
                return "\u26a0 Google Translate quota exceeded."
            return f"\u26a0 Google Translate error ({e.code})"
        except Exception:
            return f"\u26a0 Google Translate error ({e.code})"
    except Exception as exc:
        logger.error("Google Translate request failed: %s", exc)
        return "\u26a0 Google Translate connection failed."
