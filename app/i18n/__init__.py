import json
from pathlib import Path
from functools import lru_cache

BASE_DIR = Path(__file__).parent.parent
LANG_DIR = BASE_DIR / "i18n"

# Supported languages
SUPPORTED_LANGS = ["en", "pt"]
DEFAULT_LANG = "pt"


@lru_cache(maxsize=None)
def load_translations(lang: str) -> dict:
    """Load translations for a given language."""
    lang_file = LANG_DIR / f"{lang}.json"
    if lang_file.exists():
        with open(lang_file, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback to English
    return load_translations("en")


def get_translations(lang: str = None) -> dict:
    """Get translations for the given language."""
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    return load_translations(lang)


def t(key: str, lang: str = "pt") -> str:
    """
    Get translated string by dot-separated key.
    Example: t("dashboard.cpu", "pt") -> "CPU"
    """
    translations = load_translations(lang)
    keys = key.split(".")
    current = translations
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return key  # Return key if not found
    return str(current)


def detect_language(request) -> str:
    """
    Detect language from:
    1. Cookie 'lang'
    2. Query parameter 'lang'
    3. Form data (POST) 'lang'
    4. Accept-Language header
    5. Default (Portuguese)
    """
    # Check cookie
    lang_cookie = ""
    for cookie in request.cookies.items():
        if cookie[0] == "lang":
            lang_cookie = cookie[1]
            break

    if lang_cookie in SUPPORTED_LANGS:
        return lang_cookie

    # Check query parameter
    lang_query = request.query_params.get("lang")
    if lang_query in SUPPORTED_LANGS:
        return lang_query

    # Check form data (POST)
    lang_form = ""
    try:
        if hasattr(request, 'form') and request.method == "POST":
            lang_form = request.form.get("lang", "")
    except:
        pass
    
    if lang_form in SUPPORTED_LANGS:
        return lang_form

    # Check Accept-Language header
    accept_lang = request.headers.get("accept-language", "").lower()
    if "pt" in accept_lang:
        return "pt"
    if "en" in accept_lang:
        return "en"

    return DEFAULT_LANG
