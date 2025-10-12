#!/usr/bin/env python3

import os
import gettext
from typing import Optional
from functools import lru_cache

# Supported locales
SUPPORTED_LOCALES = ['en', 'fr']
DEFAULT_LOCALE = 'en'

# Translation directory path
TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), 'translations')

# Cache for translation objects
_translations = {}

@lru_cache(maxsize=len(SUPPORTED_LOCALES))
def get_translation(locale: str):
    """Get translation object for a specific locale"""
    if locale not in SUPPORTED_LOCALES:
        locale = DEFAULT_LOCALE

    if locale not in _translations:
        try:
            translation = gettext.translation(
                'messages',
                TRANSLATIONS_DIR,
                languages=[locale],
                fallback=True
            )
        except FileNotFoundError:
            # Fallback to default if translation not found
            translation = gettext.translation(
                'messages',
                TRANSLATIONS_DIR,
                languages=[DEFAULT_LOCALE],
                fallback=True
            )
        _translations[locale] = translation

    return _translations[locale]

def validate_locale(locale: str) -> str:
    """Validate and normalize locale"""
    if locale in SUPPORTED_LOCALES:
        return locale
    return DEFAULT_LOCALE

def get_locale_from_request(locale: Optional[str]) -> str:
    """Get validated locale from request parameter"""
    if locale is None:
        return DEFAULT_LOCALE
    return validate_locale(locale)

def _(message: str, locale: str = DEFAULT_LOCALE) -> str:
    """Translation function for use in Python code"""
    translation = get_translation(locale)
    return translation.gettext(message)

def ngettext(singular: str, plural: str, n: int, locale: str = DEFAULT_LOCALE) -> str:
    """Plural translation function"""
    translation = get_translation(locale)
    return translation.ngettext(singular, plural, n)

class I18nContext:
    """Context object for templates to access translation functions"""
    def __init__(self, locale: str):
        self.locale = locale
        self.translation = get_translation(locale)

    def _(self, message: str) -> str:
        """Translation function for templates"""
        return self.translation.gettext(message)

    def ngettext(self, singular: str, plural: str, n: int) -> str:
        """Plural translation function for templates"""
        return self.translation.ngettext(singular, plural, n)