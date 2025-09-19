"""Persistence layer for telemetry events."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)


@dataclass
class PersistenceSettings:
    postgres_dsn: str
    minio_enabled: bool = False
    minio_endpoint: Optional[str] = None
    minio_access_key: Optional[str] = None
    minio_secret_key: Optional[str] = None
    minio_bucket: Optional[str] = None

    @classmethod
    def from_env(cls) -> "PersistenceSettings":
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            host = os.environ.get("POSTGRES_HOST", "localhost")
            port = os.environ.get("POSTGRES_PORT", "5432")
            user = os.environ.get("POSTGRES_USER", "postgres")
            password = os.environ.get("POSTGRES_PASSWORD", "postgres")
            db = os.environ.get("POSTGRES_DB", "postgres")
            options = os.environ.get("POSTGRES_OPTIONS")
            sslmode = os.environ.get("POSTGRES_SSLMODE")

            parts = [f"postgresql://{user}:{password}@{host}:{port}/{db}"]
            params: list[str] = []
            if options:
                params.append(options)
            if sslmode:
                params.append(f"sslmode={sslmode}")
            if params:
                parts[0] += "?" + "&".join(params)
            dsn = parts[0]

        minio_enabled = os.environ.get("MINIO_ENABLED", "false").lower() == "true"
        return cls(
            postgres_dsn=dsn,
            minio_enabled=minio_enabled,
            minio_endpoint=os.environ.get("MINIO_ENDPOINT"),
            minio_access_key=os.environ.get("MINIO_ACCESS_KEY"),
            minio_secret_key=os.environ.get("MINIO_SECRET_KEY"),
            minio_bucket=os.environ.get("MINIO_BUCKET"),
        )


class PersistenceLayer:
    def __init__(self, settings: PersistenceSettings) -> None:
        self._settings = settings
        self._pool = ConnectionPool(
            conninfo=settings.postgres_dsn,
            kwargs={"autocommit": True},
        )
        logger.info("PersistenceLayer initialized (minio_enabled=%s)", settings.minio_enabled)

    def write_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        tenant_id = payload.get("tenant_id")
        policy_id = payload.get("version", {}).get("policy_id")
        skill = payload.get("skill")
        occurred_at = self._coerce_datetime(payload.get("created_at"))

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO events (tenant_id, event_type, payload, policy_id, skill, occurred_at)
                    VALUES (%s, %s, %s::jsonb, %s, %s, %s)
                    """,
                    (
                        tenant_id,
                        event_type,
                        json.dumps(payload),
                        policy_id,
                        skill,
                        occurred_at,
                    ),
                )
        logger.info("Persisted event type=%s tenant=%s", event_type, tenant_id)

        if self._settings.minio_enabled:
            self._stage_to_minio(event_type=event_type, payload=payload)

    def _stage_to_minio(self, event_type: str, payload: Dict[str, Any]) -> None:
        # TODO: implement MinIO staging (Phase 1 extension). For now we log.
        logger.info("[minio] staging event type=%s payload_keys=%s", event_type, list(payload.keys()))

    def close(self) -> None:
        self._pool.close()

    @staticmethod
    def _coerce_datetime(value: Optional[str]) -> datetime:
        if not value:
            return datetime.utcnow()
        candidate = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            logger.warning("Failed to parse datetime '%s'; defaulting to utcnow", value)
            return datetime.utcnow()


__all__ = ["PersistenceLayer", "PersistenceSettings"]
