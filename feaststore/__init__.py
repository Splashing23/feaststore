"""feaststore - a lightweight feature store for online/offline ML feature serving."""

from feaststore.definitions import Entity, Feature, FeatureView, ValueType
from feaststore.exceptions import (
    EntityNotFoundError,
    FeatureStoreError,
    FeatureViewNotFoundError,
    RegistrationError,
)

__version__ = "0.4.2"

__all__ = [
    "Entity",
    "Feature",
    "FeatureView",
    "ValueType",
    "FeatureStoreError",
    "EntityNotFoundError",
    "FeatureViewNotFoundError",
    "RegistrationError",
]
