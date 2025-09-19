"""Persistence layer for telemetry events."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

try:  # Optional dependency enabled via MINIO_ENABLED
    from minio import Minio  # type: ignore
    from minio.error import S3Error  # type: ignore
except ImportError:  # pragma: no cover - handled via feature flag
    Minio = None  # type: ignore
    S3Error = Exception

logger = logging.getLogger(__name__)


@dataclass
class PersistenceSettings:
    postgres_dsn: str
    minio_enabled: bool = False
    minio_endpoint: Optional[str] = None
    minio_access_key: Optional[str] = None
    minio_secret_key: Optional[str] = None
    minio_bucket: Optional[str] = None
    minio_secure: bool = False
    minio_region: Optional[str] = None
    minio_prefix: str = "events"
    pii_scrub_enabled: bool = True
    pii_tenant_allowlist: tuple[str, ...] = ()
    pii_redaction_token: str = "[REDACTED]"

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
            minio_secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
            minio_region=os.environ.get("MINIO_REGION"),
            minio_prefix=os.environ.get("MINIO_PREFIX", "events"),
            pii_scrub_enabled=os.environ.get("COLLECTOR_PII_SCRUB", "true").lower() == "true",
            pii_tenant_allowlist=tuple(
                t.strip() for t in os.environ.get("COLLECTOR_PII_ALLOWLIST", "").split(",") if t.strip()
            ),
            pii_redaction_token=os.environ.get("COLLECTOR_PII_REDACTION", "[REDACTED]"),
        )


class PersistenceLayer:
    def __init__(self, settings: PersistenceSettings) -> None:
        self._settings = settings
        self._pool = ConnectionPool(
            conninfo=settings.postgres_dsn,
            kwargs={"autocommit": True},
            open=False,
        )
        self._minio = self._init_minio_client(settings) if settings.minio_enabled else None
        logger.info(
            "PersistenceLayer initialized (minio_enabled=%s, minio_bucket=%s, prefix=%s)",
            settings.minio_enabled,
            settings.minio_bucket,
            settings.minio_prefix,
        )

    def _init_minio_client(self, settings: PersistenceSettings) -> Optional[Minio]:
        if Minio is None:  # pragma: no cover - import guarded by flag
            logger.warning("MinIO support requested but python-minio package is not installed")
            return None
        if not settings.minio_endpoint or not settings.minio_bucket:
            logger.warning("MinIO enabled but endpoint/bucket not configured; disabling staging")
            return None

        client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            region=settings.minio_region,
        )
        try:
            if not client.bucket_exists(settings.minio_bucket):
                client.make_bucket(settings.minio_bucket, location=settings.minio_region)
        except S3Error as exc:  # pragma: no cover - network side effects
            logger.error("Failed to ensure MinIO bucket %s: %s", settings.minio_bucket, exc)
            return None
        logger.info("MinIO staging enabled bucket=%s prefix=%s", settings.minio_bucket, settings.minio_prefix)
        return client

    def write_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        tenant_id = payload.get("tenant_id")
        policy_id = payload.get("version", {}).get("policy_id")
        skill = payload.get("skill")
        occurred_at = self._coerce_datetime(payload.get("created_at"))

        if self._pool.closed:
            self._pool.open()

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

        if self._settings.minio_enabled and self._minio:
            self._stage_to_minio(event_type=event_type, payload=payload)

    def _stage_to_minio(self, event_type: str, payload: Dict[str, Any]) -> None:
        assert self._minio is not None  # for type checking
        partition = datetime.utcnow().strftime("dt=%Y-%m-%d")
        object_name = (
            f"{self._settings.minio_prefix}/staging/{event_type}/{partition}/"
            f"{uuid4().hex}.jsonl"
        )
        staged_payload = {
            "event_type": event_type,
            "ingested_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "payload": payload,
        }
        body = (json.dumps(staged_payload, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            self._minio.put_object(
                bucket_name=self._settings.minio_bucket,
                object_name=object_name,
                data=BytesIO(body),
                length=len(body),
                content_type="application/json",
            )
            logger.debug("Staged event to MinIO object=%s", object_name)
        except S3Error as exc:  # pragma: no cover - network side effects
            logger.error("Failed to stage event to MinIO: %s", exc)

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
