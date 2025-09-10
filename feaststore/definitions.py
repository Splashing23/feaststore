"""User-facing definition objects: Entity, Feature, FeatureView.

These are the building blocks a data scientist writes in a feature repo. They are
deliberately plain dataclasses (not SQLAlchemy models) so that a feature repo can
be imported and validated without any database connection. The registry is
responsible for persisting a serialized form of these objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any

from feaststore.exceptions import RegistrationError

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class ValueType(str, Enum):
    """Supported feature value types.

    Kept intentionally small. Anything richer (embeddings, lists) is stored as
    JSON via `ValueType.STRING` at the online layer for now -- see docs/concepts.md
    for the rationale and the planned typed-array work.
    """

    INT64 = "int64"
    FLOAT = "float"
    STRING = "string"
    BOOL = "bool"
    BYTES = "bytes"
    UNIX_TIMESTAMP = "unix_timestamp"


def _validate_name(name: str, kind: str) -> None:
    if not _NAME_RE.match(name):
        raise RegistrationError(
            f"{kind} name {name!r} is invalid: must be snake_case, start with a "
            "letter, and be at most 63 characters"
        )


@dataclass(frozen=True, slots=True)
class Entity:
    """A domain object that features are attached to (e.g. a user or a merchant).

    `join_key` is the column used to join feature tables and the key used to look
    up rows in the online store. It defaults to the entity name.
    """

    name: str
    join_key: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        _validate_name(self.name, "entity")
        # frozen dataclass: mutate through object.__setattr__ for the derived default
        if not self.join_key:
            object.__setattr__(self, "join_key", self.name)
        _validate_name(self.join_key, "join_key")


@dataclass(frozen=True, slots=True)
class Feature:
    """A single named, typed value within a feature view."""

    name: str
    dtype: ValueType
    description: str = ""

    def __post_init__(self) -> None:
        _validate_name(self.name, "feature")
        if not isinstance(self.dtype, ValueType):
            raise RegistrationError(
                f"feature {self.name!r} has dtype {self.dtype!r}; expected a ValueType"
            )


@dataclass(frozen=True, slots=True)
class FeatureView:
    """A group of features computed from one source, keyed by one or more entities.

    `ttl` bounds how long a materialized value is considered fresh in the online
    store. A `None` ttl means values never expire (use with care -- appropriate for
    slowly-changing dimensions like a user's signup country).

    `source_table` names the offline table/relation the materialization engine
    reads from. It must expose the entity join keys, every feature column, and an
    event-timestamp column (`event_timestamp` by default).
    """

    name: str
    entities: list[Entity]
    features: list[Feature]
    source_table: str
    ttl: timedelta | None = timedelta(days=1)
    timestamp_field: str = "event_timestamp"
    tags: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_name(self.name, "feature_view")
        if not self.entities:
            raise RegistrationError(f"feature view {self.name!r} must have >= 1 entity")
        if not self.features:
            raise RegistrationError(f"feature view {self.name!r} must have >= 1 feature")
        if not self.source_table:
            raise RegistrationError(f"feature view {self.name!r} needs a source_table")

        names = [f.name for f in self.features]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise RegistrationError(
                f"feature view {self.name!r} has duplicate feature names: {sorted(dupes)}"
            )

    @property
    def join_keys(self) -> list[str]:
        return [e.join_key for e in self.entities]

    def feature_names(self) -> list[str]:
        return [f.name for f in self.features]

    def get_feature(self, name: str) -> Feature:
        for f in self.features:
            if f.name == name:
                return f
        raise KeyError(f"feature {name!r} not in view {self.name!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "entities": [
                {"name": e.name, "join_key": e.join_key, "description": e.description}
                for e in self.entities
            ],
            "features": [
                {"name": f.name, "dtype": f.dtype.value, "description": f.description}
                for f in self.features
            ],
            "source_table": self.source_table,
            "ttl_seconds": int(self.ttl.total_seconds()) if self.ttl else None,
            "timestamp_field": self.timestamp_field,
            "tags": dict(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureView:
        entities = [
            Entity(name=e["name"], join_key=e["join_key"], description=e.get("description", ""))
            for e in data["entities"]
        ]
        features = [
            Feature(
                name=f["name"],
                dtype=ValueType(f["dtype"]),
                description=f.get("description", ""),
            )
            for f in data["features"]
        ]
        ttl_seconds = data.get("ttl_seconds")
        return cls(
            name=data["name"],
            entities=entities,
            features=features,
            source_table=data["source_table"],
            ttl=timedelta(seconds=ttl_seconds) if ttl_seconds is not None else None,
            timestamp_field=data.get("timestamp_field", "event_timestamp"),
            tags=data.get("tags", {}),
        )
