"""Gateway re-exports shared settings (single source of truth)."""

from shared.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
