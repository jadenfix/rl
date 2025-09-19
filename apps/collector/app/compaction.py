"""Utilities for compacting staged MinIO JSONL blobs into Parquet batches."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from io import BytesIO
from typing import Iterable, List

import pyarrow as pa
import pyarrow.parquet as pq

from .storage import PersistenceSettings

try:  # pragma: no cover - optional dependency
    from minio import Minio  # type: ignore
    from minio.error import S3Error  # type: ignore
except ImportError as exc:  # pragma: no cover - handled by CLI
    raise SystemExit("python-minio is required for compaction") from exc

logger = logging.getLogger("collector.compaction")
logging.basicConfig(level=logging.INFO)


def _build_client(settings: PersistenceSettings) -> Minio:
    if not settings.minio_endpoint or not settings.minio_bucket:
        raise ValueError("MinIO endpoint and bucket must be configured")
    client = Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
        region=settings.minio_region,
    )
    return client


def _iter_staged_events(client: Minio, settings: PersistenceSettings, target_date: str) -> Iterable[dict]:
    prefix = f"{settings.minio_prefix}/staging/"
    for obj in client.list_objects(settings.minio_bucket, prefix=prefix, recursive=True):
        if f"dt={target_date}" not in obj.object_name:
            continue
        response = client.get_object(settings.minio_bucket, obj.object_name)
        try:
            for line in response.stream(32 * 1024):
                if not line:
                    continue
                event = json.loads(line)
                yield event
        finally:
            response.close()
            response.release_conn()


def _events_to_table(events: Iterable[dict]) -> pa.Table:
    rows: List[dict] = []
    for record in events:
        payload = record.get("payload", {})
        rows.append(
            {
                "event_type": record.get("event_type"),
                "ingested_at": record.get("ingested_at"),
                "tenant_id": payload.get("tenant_id"),
                "skill": payload.get("skill"),
                "policy_id": payload.get("version", {}).get("policy_id"),
                "raw_payload": json.dumps(payload, separators=(",", ":")),
            }
        )
    if not rows:
        return pa.table({})
    return pa.Table.from_pylist(rows)


def _upload_parquet(client: Minio, settings: PersistenceSettings, table: pa.Table, target_date: str) -> str:
    if table.num_rows == 0:
        raise ValueError("No events to compact")
    buffer = BytesIO()
    pq.write_table(table, buffer, compression="snappy")
    object_name = (
        f"{settings.minio_prefix}/parquet/dt={target_date}/"
        f"events-{datetime.utcnow().strftime('%H%M%S')}.parquet"
    )
    buffer.seek(0)
    client.put_object(
        bucket_name=settings.minio_bucket,
        object_name=object_name,
        data=buffer,
        length=buffer.getbuffer().nbytes,
        content_type="application/octet-stream",
    )
    return object_name


def compact(target_date: str) -> str:
    settings = PersistenceSettings.from_env()
    client = _build_client(settings)
    events = list(_iter_staged_events(client, settings, target_date))
    table = _events_to_table(events)
    object_name = _upload_parquet(client, settings, table, target_date)
    logger.info("Compacted %s rows into %s", table.num_rows, object_name)
    return object_name


def main() -> None:  # pragma: no cover - CLI wiring
    parser = argparse.ArgumentParser(description="Compact staged collector events into Parquet")
    parser.add_argument("--date", dest="date", help="ISO date (YYYY-MM-DD)", default=datetime.utcnow().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    try:
        compact(args.date)
    except (ValueError, S3Error) as exc:
        logger.error("Compaction failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":  # pragma: no cover
    main()
