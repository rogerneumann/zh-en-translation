"""DeepL translation engine integration."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zh_en_translator.config import Config

logger = logging.getLogger(__name__)

def translate_with_deepl(text: str, config: Config) -> str:
    """Translate text using DeepL API."""
    if not config.deepl_enabled or not config.deepl_api_key:
        return "⚠ DeepL not configured."

    api_key = config.deepl_api_key
    is_pro = config.deepl_pro
    
    # Pro use 'api.deepl.com', Free use 'api-free.deepl.com'
    domain = "api.deepl.com" if is_pro else "api-free.deepl.com"
    url = f"https://{domain}/v2/translate"

    params = {
        "auth_key": api_key,
        "text": text,
        "source_lang": "ZH",
        "target_lang": "EN-US"
    }
    
    data = urllib.parse.urlencode(params).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if "translations" in result and len(result["translations"]) > 0:
                return result["translations"][0]["text"]
            return "⚠ DeepL returned an empty result."
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            logger.error("DeepL HTTP error: %s - %s", e.code, err_body)
            if e.code == 403:
                return "⚠ DeepL API key invalid or expired."
            if e.code == 456:
                return "⚠ DeepL quota exceeded."
            return f"⚠ DeepL error ({e.code})"
        except Exception:
            return f"⚠ DeepL error ({e.code})"
    except Exception as e:
        logger.error("DeepL translation failed: %s", e)
        return "⚠ DeepL connection failed."
