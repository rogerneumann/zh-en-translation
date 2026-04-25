"""Domain selector UI widget for multi-domain glossary management.

Provides a QWidget that lets the user pick which domain glossaries are active.
Intended to be embedded in the Preferences dialog (preferences.py).

This is a skeleton implementation - the full Qt integration will be completed
when Qt is available in the environment.
"""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

# Domain display names and descriptions
DOMAIN_DISPLAY_NAMES: dict[str, str] = {
    "manufacturing": "Manufacturing",
    "medical": "Medical / Pharmaceutical",
    "legal": "Legal / Contract",
    "electronics": "Electronics / Hardware",
}

DOMAIN_DESCRIPTIONS: dict[str, str] = {
    "manufacturing": "Materials, processes, components, quality control (149 terms)",
    "medical": "Anatomy, diseases, treatments, medications, lab tests (500+ terms)",
    "legal": "Contracts, court procedures, IP, corporate law (400+ terms)",
    "electronics": "Components, PCB design, semiconductors, testing (450+ terms)",
}

# Priority order: higher index = loaded first (lower priority, overwritten by lower index)
DOMAIN_DEFAULT_ORDER = ["manufacturing", "medical", "legal", "electronics"]


class DomainSelectorModel:
    """Non-GUI model backing the domain selector.

    Manages which domains are enabled and their priority order.
    Can be used independently of Qt for testing.
    """

    def __init__(
        self,
        enabled_domains: list[str] | None = None,
        on_change: Callable[[list[str]], None] | None = None,
    ) -> None:
        """Initialise with optionally pre-selected domains.

        Args:
            enabled_domains: Initially enabled domains. ``None`` or empty list
                means all available domains are enabled.
            on_change: Optional callback invoked with the new domain list
                whenever the selection changes.
        """
        self._on_change = on_change

        # Discover available domains
        try:
            from zh_en_translator.engines.glossary import discover_available_domains
            self._available = discover_available_domains()
        except Exception as exc:
            logger.warning("Could not discover domains: %s", exc)
            self._available = list(DOMAIN_DEFAULT_ORDER)

        # Default: all enabled if not specified
        if not enabled_domains:
            self._enabled: list[str] = list(self._available)
        else:
            self._enabled = [d for d in enabled_domains if d in self._available]

    # ------------------------------------------------------------------
    # Read accessors
    # ------------------------------------------------------------------

    @property
    def available_domains(self) -> list[str]:
        """All domains that have glossary data (sorted)."""
        return list(self._available)

    @property
    def enabled_domains(self) -> list[str]:
        """Currently enabled domains in priority order (manufacturing first)."""
        return list(self._enabled)

    def is_enabled(self, domain: str) -> bool:
        """Return True if *domain* is currently enabled."""
        return domain in self._enabled

    def get_display_name(self, domain: str) -> str:
        """Return human-readable display name for a domain."""
        return DOMAIN_DISPLAY_NAMES.get(domain, domain.title())

    def get_description(self, domain: str) -> str:
        """Return short description / term count for a domain."""
        return DOMAIN_DESCRIPTIONS.get(domain, f"Domain: {domain}")

    def get_term_count(self, domain: str) -> int:
        """Return number of loaded terms for *domain* (0 if unavailable)."""
        try:
            from zh_en_translator.engines.glossary import load_domain_glossary
            return len(load_domain_glossary(domain))
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def set_enabled(self, domain: str, enabled: bool) -> None:
        """Enable or disable *domain*.

        Args:
            domain: Domain name to toggle.
            enabled: True to enable, False to disable.
        """
        if enabled and domain not in self._enabled and domain in self._available:
            self._enabled.append(domain)
            self._sort_enabled()
            self._notify()
        elif not enabled and domain in self._enabled:
            self._enabled.remove(domain)
            self._notify()

    def enable_all(self) -> None:
        """Enable all available domains."""
        self._enabled = list(self._available)
        self._notify()

    def disable_all(self) -> None:
        """Disable all domains."""
        self._enabled = []
        self._notify()

    def set_enabled_domains(self, domains: list[str]) -> None:
        """Set the complete list of enabled domains.

        Args:
            domains: New list of enabled domain names. Unknown domains are ignored.
        """
        self._enabled = [d for d in domains if d in self._available]
        self._notify()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sort_enabled(self) -> None:
        """Keep enabled domains sorted by DOMAIN_DEFAULT_ORDER, then alphabetically."""
        def _sort_key(d: str) -> tuple[int, str]:
            try:
                return (DOMAIN_DEFAULT_ORDER.index(d), d)
            except ValueError:
                return (len(DOMAIN_DEFAULT_ORDER), d)

        self._enabled.sort(key=_sort_key)

    def _notify(self) -> None:
        """Invoke the on_change callback if set."""
        if self._on_change is not None:
            try:
                self._on_change(list(self._enabled))
            except Exception as exc:
                logger.warning("DomainSelectorModel on_change callback failed: %s", exc)


def try_create_qt_widget(model: DomainSelectorModel):  # type: ignore[return]
    """Attempt to create a Qt widget for domain selection.

    Returns a QWidget instance if PyQt5/PySide2 is available, else None.
    The widget contains:
    - A QGroupBox titled "Active Glossary Domains"
    - A QComboBox for single-domain mode
    - Checkboxes for multi-domain mode
    - A label showing total loaded terms

    Args:
        model: :class:`DomainSelectorModel` backing the widget state.

    Returns:
        QWidget or None if Qt is not available.
    """
    try:
        from PyQt5.QtWidgets import (  # type: ignore[import]
            QCheckBox,
            QGroupBox,
            QLabel,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        try:
            from PyQt6.QtWidgets import (  # type: ignore[import]
                QCheckBox,
                QGroupBox,
                QLabel,
                QVBoxLayout,
                QWidget,
            )
        except ImportError:
            logger.debug("Qt not available; domain selector widget not created")
            return None

    container = QWidget()
    outer_layout = QVBoxLayout(container)
    outer_layout.setContentsMargins(0, 0, 0, 0)

    group = QGroupBox("Active Glossary Domains")
    layout = QVBoxLayout(group)

    checkboxes: dict[str, object] = {}

    def _refresh_label():
        total = sum(
            model.get_term_count(d)
            for d in model.enabled_domains
        )
        count_label.setText(f"Total loaded terms: {total:,}")

    for domain in model.available_domains:
        cb = QCheckBox(
            f"{model.get_display_name(domain)}"
            f"  —  {model.get_description(domain)}"
        )
        cb.setChecked(model.is_enabled(domain))

        # Capture domain in closure
        def _make_handler(d):
            def _on_toggle(checked, _domain=d):
                model.set_enabled(_domain, bool(checked))
                _refresh_label()
            return _on_toggle

        cb.toggled.connect(_make_handler(domain))
        layout.addWidget(cb)
        checkboxes[domain] = cb

    count_label = QLabel()
    _refresh_label()
    layout.addWidget(count_label)

    outer_layout.addWidget(group)
    return container
