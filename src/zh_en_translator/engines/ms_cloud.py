"""Optional Microsoft Azure Translator integration for zh-en-translator.

Only makes network requests when the user has explicitly enabled cloud
translation AND provided an API key. With ms_translator_enabled = false
(the default), this module is imported but never touches the network.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
import uuid

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.cognitive.microsofttranslator.com/translate"
_API_VERSION = "3.0"


def is_configured(api_key: str) -> bool:
    """Return True if a non-empty API key has been provided."""
    return bool(api_key and api_key.strip())


def translate_sentence(
    text: str,
    api_key: str,
    region: str = "",
    from_lang: str = "zh-Hans",
    to_lang: str = "en",
) -> str | None:
    """
    Translate text via Azure Cognitive Services.

    Returns the translated string, or None on any failure.
    This function is only called when the user has explicitly enabled cloud
    translation -- the caller is responsible for the enabled/key checks.

    from_lang / to_lang default to zh-Hans -> en.
    Pass from_lang="en", to_lang="zh-Hans" for back-translation.
    """
    if not text.strip():
        return None

    if not is_configured(api_key):
        logger.warning("Azure Translator called without an API key -- skipping")
        return None

    url = f"{_ENDPOINT}?api-version={_API_VERSION}&from={from_lang}&to={to_lang}"
    body = json.dumps([{"text": text}]).encode("utf-8")

    headers = {
        "Ocp-Apim-Subscription-Key": api_key.strip(),
        "Content-Type": "application/json; charset=UTF-8",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    if region and region.strip():
        headers["Ocp-Apim-Subscription-Region"] = region.strip()

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        translation = payload[0]["translations"][0]["text"]
        logger.debug("Azure Translator successful (result length: %d chars)", len(translation))
        return translation if translation else None
    except urllib.error.HTTPError as exc:
        logger.warning("Azure Translator HTTP %s: %s", exc.code, exc.reason)
        return None
    except urllib.error.URLError as exc:
        logger.warning("Azure Translator network error: %s", exc.reason)
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("Azure Translator unexpected response: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Azure Translator error: %s", exc)
        return None
