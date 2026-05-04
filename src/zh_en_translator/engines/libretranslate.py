"""LibreTranslate engine integration.

LibreTranslate is a free, open-source machine translation API.
Self-host or use a public instance -- no Google/Microsoft account required.

Public instances (reliability varies):
  https://libretranslate.com          (official; free tier needs API key)
  https://translate.argosopentech.com (no key, rate-limited)
  https://libretranslate.de           (no key required)

API docs: https://libretranslate.com/docs/
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zh_en_translator.config import Config

logger = logging.getLogger(__name__)


def translate_with_libretranslate(
    text: str,
    config: Config,
    source: str = "zh",
    target: str = "en",
) -> str:
    """Translate text using a LibreTranslate instance.

    source / target default to zh -> en.
    Pass source="en", target="zh" for back-translation.
    """
    if not config.libretranslate_enabled:
        return "\u26a0 LibreTranslate not enabled."

    base_url = (config.libretranslate_url or "https://libretranslate.com").rstrip("/")
    endpoint = f"{base_url}/translate"

    payload: dict = {
        "q": text,
        "source": source,
        "target": target,
        "format": "text",
    }
    if config.libretranslate_api_key:
        payload["api_key"] = config.libretranslate_api_key

    data = json.dumps(payload).encode("utf-8")

    try:
        req = urllib.request.Request(
            endpoint, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            translated = result.get("translatedText")
            if translated:
                return translated
            # Some instances return error inside a 200 response
            error = result.get("error", "empty result")
            logger.warning("LibreTranslate returned no text: %s", error)
            return f"\u26a0 LibreTranslate: {error}"

    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("error", str(e.code))
        except Exception:
            msg = str(e.code)
        logger.error("LibreTranslate HTTP error %s: %s", e.code, msg)
        if e.code == 403:
            return "\u26a0 LibreTranslate: API key required or invalid."
        if e.code == 429:
            return "\u26a0 LibreTranslate: rate limit reached."
        return f"\u26a0 LibreTranslate error ({e.code}): {msg}"
    except Exception as exc:
        logger.error("LibreTranslate request failed: %s", exc)
        return "\u26a0 LibreTranslate connection failed."
