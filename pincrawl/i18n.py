#!/usr/bin/env python3

import os
import gettext
import logging
from typing import Optional
from functools import lru_cache

# Setup logger
logger = logging.getLogger(__name__)

# Supported locales
SUPPORTED_LOCALES = ['en', 'fr']
DEFAULT_LOCALE = 'en'

# Translation directory path (shared root directory)
TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'translations')
# Ensure translations directory exists
if not os.path.exists(TRANSLATIONS_DIR):
    logger.error(f"Translations directory does not exist: {TRANSLATIONS_DIR}")
else:
    logger.debug(f"Translations directory exists: {TRANSLATIONS_DIR}")

# Cache for translation objects
_translations = {}

@lru_cache(maxsize=len(SUPPORTED_LOCALES))
def get_translation(locale: str):
    """Get translation object for a specific locale

    Args:
        locale: Language code (en, fr, etc.)
    """
    logger.debug(f"get_translation called with locale: {locale}")

    if locale not in SUPPORTED_LOCALES:
        logger.warning(f"Locale '{locale}' not supported, falling back to '{DEFAULT_LOCALE}'")
        locale = DEFAULT_LOCALE

    if locale not in _translations:
        logger.debug(f"Translation for locale '{locale}' not in cache, loading from {TRANSLATIONS_DIR}")
        try:
            translation = gettext.translation(
                'messages',
                TRANSLATIONS_DIR,
                languages=[locale],
                fallback=True
            )
            logger.info(f"Successfully loaded translation for locale '{locale}'")
        except FileNotFoundError:
            logger.error(f"Translation file not found for locale '{locale}' in {TRANSLATIONS_DIR}")
            # Fallback to default if translation not found
            try:
                translation = gettext.translation(
                    'messages',
                    TRANSLATIONS_DIR,
                    languages=[DEFAULT_LOCALE],
                    fallback=True
                )
                logger.info(f"Loaded default locale '{DEFAULT_LOCALE}' as fallback")
            except FileNotFoundError:
                logger.error(f"Default translation file not found in {TRANSLATIONS_DIR}, using NullTranslations")
                # Ultimate fallback - use NullTranslations
                translation = gettext.NullTranslations()
        _translations[locale] = translation
    else:
        logger.debug(f"Using cached translation for locale '{locale}'")

    return _translations[locale]

def validate_locale(locale: str) -> str:
    """Validate and normalize locale"""
    logger.debug(f"Validating locale: {locale}")
    if locale in SUPPORTED_LOCALES:
        logger.debug(f"Locale '{locale}' is valid")
        return locale
    logger.warning(f"Invalid locale '{locale}', returning default '{DEFAULT_LOCALE}'")
    return DEFAULT_LOCALE

def get_locale_from_request(locale: Optional[str]) -> str:
    """Get validated locale from request parameter"""
    logger.debug(f"Getting locale from request: {locale}")
    if locale is None:
        logger.debug(f"No locale provided, using default '{DEFAULT_LOCALE}'")
        return DEFAULT_LOCALE
    return validate_locale(locale)

def _(message: str, locale: str = DEFAULT_LOCALE) -> str:
    """Translation function for use in Python code

    Args:
        message: Message to translate
        locale: Target locale
    """
    translation = get_translation(locale)
    translated = translation.gettext(message)
    return translated

class I18nContext:
    """Context object for templates to access translation functions"""
    def __init__(self, locale: str):
        logger.debug(f"Creating I18nContext for locale: {locale}")
        self.locale = locale
        self.translation = get_translation(locale)

    def _(self, message: str) -> str:
        """Translation function for templates"""
        translated = self.translation.gettext(message)
        return translated