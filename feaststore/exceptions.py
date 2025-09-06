"""Exception hierarchy for feaststore.

Keeping a single base (`FeatureStoreError`) lets callers catch everything the
library throws with one `except`, while the specific subclasses map cleanly to
HTTP status codes in the serving layer (see `serving/api.py`).
"""

from __future__ import annotations


class FeatureStoreError(Exception):
    """Base class for all feaststore errors."""


class RegistrationError(FeatureStoreError):
    """Raised when a definition fails validation during registration."""


class EntityNotFoundError(FeatureStoreError):
    """Raised when an entity referenced by name is not in the registry."""

    def __init__(self, name: str) -> None:
        super().__init__(f"entity {name!r} is not registered")
        self.name = name


class FeatureViewNotFoundError(FeatureStoreError):
    """Raised when a feature view referenced by name is not in the registry."""

    def __init__(self, name: str) -> None:
        super().__init__(f"feature view {name!r} is not registered")
        self.name = name


class MaterializationError(FeatureStoreError):
    """Raised when a materialization job cannot complete."""
