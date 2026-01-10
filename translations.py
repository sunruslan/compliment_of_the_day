"""
Translation system for the compliment bot.
Loads translations from YAML files and provides a simple interface.
"""

import yaml
from pathlib import Path
from typing import Dict, Any
from setup import get_logger

logger = get_logger(__name__)

# Cache for loaded translations
_translations_cache: Dict[str, Dict[str, Any]] = {}


def load_translations(language: str = "en") -> Dict[str, Any]:
    """
    Load translations for a specific language.

    Args:
        language: Language code ('en' or 'ru')

    Returns:
        Dictionary with translations
    """
    if language not in ("en", "ru"):
        logger.warning(f"Unknown language {language}, falling back to 'en'")
        language = "en"

    # Return cached translations if available
    if language in _translations_cache:
        return _translations_cache[language]

    # Load translations from file
    translations_dir = Path(__file__).parent / "translations"
    translation_file = translations_dir / f"{language}.yaml"

    if not translation_file.exists():
        logger.error(f"Translation file not found: {translation_file}")
        # Fallback to English if file doesn't exist
        if language != "en":
            return load_translations("en")
        return {}

    try:
        with open(translation_file, "r", encoding="utf-8") as f:
            translations = yaml.safe_load(f)
            _translations_cache[language] = translations
            return translations
    except Exception as e:
        logger.error(f"Error loading translations for {language}: {e}")
        # Fallback to English on error
        if language != "en":
            return load_translations("en")
        return {}


def get_translation(key: str, language: str = "en", default: str = None) -> str:
    """
    Get a translation by key path (e.g., 'messages.start').

    Args:
        key: Translation key path (dot notation)
        language: Language code ('en' or 'ru')
        default: Default value if key not found

    Returns:
        Translated string
    """
    translations = load_translations(language)

    if not translations:
        return default or key

    # Navigate through nested dictionary
    keys = key.split(".")
    value = translations

    try:
        for k in keys:
            value = value[k]
        return value
    except (KeyError, TypeError):
        logger.warning(f"Translation key not found: {key} for language {language}")
        return default or key


def format_translation(
    key: str, language: str = "en", default: str = None, **kwargs
) -> str:
    """
    Get a translation and format it with provided arguments.

    Args:
        key: Translation key path (dot notation)
        language: Language code ('en' or 'ru')
        default: Default value if key not found
        **kwargs: Arguments to format into the translation

    Returns:
        Formatted translated string
    """
    translation = get_translation(key, language, default)
    try:
        return translation.format(**kwargs)
    except (KeyError, ValueError) as e:
        logger.warning(f"Error formatting translation {key}: {e}")
        return translation
