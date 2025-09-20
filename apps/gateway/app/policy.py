"""Policy store backed by Postgres."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import GatewaySettings
from .models import Policy

logger = logging.getLogger(__name__)


@dataclass
class PolicyStore:
    settings: GatewaySettings

    def __post_init__(self) -> None:
        self._pool = ConnectionPool(
            conninfo=self.settings.postgres_dsn,
            kwargs={"autocommit": True},
            open=False,
        )

    def open(self) -> None:
        if self._pool.closed:
            self._pool.open()

    def close(self) -> None:
        self._pool.close()

    def list_policies(self, tenant_id: str, skill: Optional[str] = None) -> List[Policy]:
        self.open()
        query = (
            "SELECT policy_id, status, base_model, prompt_version, adapter_ref "
            "FROM policies "
            "WHERE tenant_id = (SELECT id FROM tenants WHERE tenant_slug = %s) "
            "AND status = ANY(%s)"
        )
        params = [tenant_id, list(self.settings.default_statuses)]
        if skill:
            query += " AND policy_id LIKE %s"
            params.append(f"{skill}%")

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        if not rows and skill:
            logger.info(
                "No policies found for tenant=%s skill=%s; falling back to tenant-wide policies",
                tenant_id,
                skill,
            )
            return self.list_policies(tenant_id, skill=None)

        policies = [Policy(**row) for row in rows]
        logger.info("Fetched %s policies for tenant=%s skill=%s", len(policies), tenant_id, skill)
        return policies

    def get_active_policy(self, tenant_id: str, skill: Optional[str] = None) -> Optional[Policy]:
        policies = self.list_policies(tenant_id, skill)
        for policy in policies:
            if policy.status == "active":
                return policy
        return policies[0] if policies else None


__all__ = ["PolicyStore"]
