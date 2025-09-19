# Operational Scripts

Collection of helper scripts for seeding databases, running maintenance tasks, and supporting developer workflows.

Initial scope:
- `seed_local.py` — bootstrap tenants, policies, and API keys
- `dump_events.py` — export telemetry snapshots for debugging
- `check_services.sh` — health-check convenience wrapper for local stack
- `generate_openapi.py` — build collector OpenAPI schema from shared JSON event definitions
