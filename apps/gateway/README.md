# Gateway Service

FastAPI-based inference gateway that fronts policy routing, handles request tracing, and orchestrates shadow/AB deployments.

## Planned components
- `/v1/infer` endpoint with OpenTelemetry span emission
- Policy registry integration for routing decisions
- Connectors to model backends (vLLM, TGI, external APIs)
- Bandit hooks for exploration vs exploitation control
