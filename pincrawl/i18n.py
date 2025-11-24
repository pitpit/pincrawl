import os
import gettext
import logging
from typing import Optional
from functools import lru_cache
from pathlib import Path

# Setup logger
logger = logging.getLogger(__name__)

class I18n:
    """I18n handler that can be initialized with a custom translation directory"""

    SUPPORTED_LOCALES = ['en', 'fr']
    DEFAULT_LOCALE = 'en'


    def __init__(self, translation_directory: Path):
        """Initialize I18n with a translation directory

        Args:
            translation_directory: Path to the directory containing translation files
        """
        self.translation_directory = Path(translation_directory)
        self._translations = {}
        logger.info(f"Initialized I18n with translation directory: {self.translation_directory}")

        if not self.translation_directory.exists():
            logger.warning(f"Translation directory does not exist: {self.translation_directory}")

    def get_translation(self, locale: str):
        """Get translation object for a specific locale

        Args:
            locale: Language code (en, fr, etc.)
        """
        logger.debug(f"get_translation called with locale: {locale}")

        if locale not in self.SUPPORTED_LOCALES:
            logger.warning(f"Locale '{locale}' not supported, falling back to '{self.DEFAULT_LOCALE}'")
            locale = self.DEFAULT_LOCALE

        if locale not in self._translations:
            logger.debug(f"Translation for locale '{locale}' not in cache, loading from {self.translation_directory}")
            try:
                if not self.translation_directory.exists():
                    raise FileNotFoundError(f"Translation directory does not exist: {self.translation_directory}")

                translation = gettext.translation(
                    'messages',
                    self.translation_directory,
                    languages=[locale] if locale == self.DEFAULT_LOCALE else [locale, self.DEFAULT_LOCALE],
                    fallback=True
                )
                logger.info(f"Successfully loaded translation for locale '{locale}'")
            except FileNotFoundError:
                logger.error(f"Default translation file not found in {self.translation_directory}, using NullTranslations")
                translation = gettext.NullTranslations()

            self._translations[locale] = translation
        else:
            logger.debug(f"Using cached translation for locale '{locale}'")

        return self._translations[locale]

    def normalize_locale(self, locale: str|None) -> str:
        """Validate and normalize locale"""
        logger.debug(f"Validating locale: {locale}")

        if locale is None:
            logger.debug(f"No locale provided, using default '{self.DEFAULT_LOCALE}'")
            return self.DEFAULT_LOCALE

        if locale in self.SUPPORTED_LOCALES:
            logger.debug(f"Locale '{locale}' is valid")
            return locale

        logger.warning(f"Invalid locale '{locale}', returning default '{self.DEFAULT_LOCALE}'")
        return self.DEFAULT_LOCALE

    def get_locale_from_accept_language(self, accept_language: str|None) -> str:
        """Extract preferred language from browser's Accept-Language header.

        Args:
            request: The request object containing headers

        Returns:
            str: The preferred locale code (e.g., 'en', 'fr') or DEFAULT_LOCALE if none found
        """
        if accept_language:
            try:
                # Parse Accept-Language header (format: "en-US,en;q=0.9,fr;q=0.8")
                languages = accept_language.split(',')
                for lang in languages:
                    # Remove quality factor (;q=0.9) if present
                    lang_code = lang.split(';')[0].strip().lower()

                    # Extract just the language part (before any country code)
                    primary_lang = lang_code.split('-')[0]

                    # Check if this language is supported
                    if primary_lang in self.SUPPORTED_LOCALES:
                        return primary_lang
            except:
                # If parsing fails, use default
                pass

        return self.DEFAULT_LOCALE

    def get_supported_locales_pattern(self) -> str:
        """Get regex pattern string for supported locales"""
        return f"^({'|'.join(self.SUPPORTED_LOCALES)})$"

    def translate(self, message: str, locale: str = None) -> str:
        """Translation function for use in Python code

        Args:
            message: Message to translate
            locale: Target locale
        """

        if locale is None:
            locale = self.DEFAULT_LOCALE

        translation = self.get_translation(locale)
        translated = translation.gettext(message)
        return translated

    def create_context(self, locale: str) -> 'I18nContext':
        """Create an I18nContext for the given locale

        Args:
            locale: Target locale
        """
        return I18nContext(locale, self)


class I18nContext:
    """Context object for templates to access translation functions"""

    locale: str

    def __init__(self, locale: str, i18n_instance: I18n):
        logger.debug(f"Creating I18nContext for locale: {locale}")
        self.i18n = i18n_instance
        self.locale = i18n_instance.normalize_locale(locale)
        self.translation = i18n_instance.get_translation(locale)

    def _(self, message: str) -> str:
        """Translation function for templates"""
        translated = self.translation.gettext(message)
        return translated
