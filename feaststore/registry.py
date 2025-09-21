"""The registry: the source of truth for which feature views exist.

We persist the serialized `FeatureView.to_dict()` payload as JSON in a single
table. That keeps the schema stable as definitions evolve -- adding a field to a
FeatureView doesn't require a migration, only a bump to the (de)serializer. The
tradeoff is that we can't query *inside* a definition in SQL, which we've never
needed; listing and point-lookup by name cover every access pattern so far.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    String,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from feaststore.config import Settings, get_settings
from feaststore.definitions import FeatureView
from feaststore.exceptions import FeatureViewNotFoundError, RegistrationError


class Base(DeclarativeBase):
    pass


class FeatureViewRow(Base):
    __tablename__ = "feature_views"
    __table_args__ = (UniqueConstraint("project", "name", name="uq_project_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    spec: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Registry:
    """Thin persistence layer over the ``feature_views`` table."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._engine = create_engine(self._settings.offline_dsn, future=True, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    def init_schema(self) -> None:
        """Create tables if they do not exist. Idempotent."""
        Base.metadata.create_all(self._engine)

    @property
    def project(self) -> str:
        return self._settings.project

    def apply(self, view: FeatureView) -> None:
        """Register or update a feature view (upsert on (project, name))."""
        if not isinstance(view, FeatureView):
            raise RegistrationError(f"expected a FeatureView, got {type(view).__name__}")

        spec = view.to_dict()
        now = _utcnow()
        with self._session_factory.begin() as session:
            existing = self._get_row(session, view.name)
            if existing is None:
                session.add(
                    FeatureViewRow(
                        project=self.project,
                        name=view.name,
                        spec=spec,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                existing.spec = spec
                existing.updated_at = now

    def apply_all(self, views: list[FeatureView]) -> None:
        for v in views:
            self.apply(v)

    def get_feature_view(self, name: str) -> FeatureView:
        with self._session_factory() as session:
            row = self._get_row(session, name)
            if row is None:
                raise FeatureViewNotFoundError(name)
            return FeatureView.from_dict(row.spec)

    def list_feature_views(self) -> list[FeatureView]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(FeatureViewRow)
                .where(FeatureViewRow.project == self.project)
                .order_by(FeatureViewRow.name)
            ).all()
            return [FeatureView.from_dict(r.spec) for r in rows]

    def delete_feature_view(self, name: str) -> None:
        with self._session_factory.begin() as session:
            row = self._get_row(session, name)
            if row is None:
                raise FeatureViewNotFoundError(name)
            session.delete(row)

    def _get_row(self, session: Session, name: str) -> FeatureViewRow | None:
        return session.scalars(
            select(FeatureViewRow).where(
                FeatureViewRow.project == self.project,
                FeatureViewRow.name == name,
            )
        ).one_or_none()

    def dump(self) -> str:
        """Serialize the whole registry to a JSON string (used by `feaststore export`)."""
        return json.dumps(
            [v.to_dict() for v in self.list_feature_views()],
            indent=2,
            sort_keys=True,
        )
